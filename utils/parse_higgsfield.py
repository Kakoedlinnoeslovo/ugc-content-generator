#!/usr/bin/env python3
"""
Higgsfield Soul Community gallery parser.
Scrapes all images from https://higgsfield.ai/soul-community using Playwright,
then downloads them into a local folder.

Usage:
    python parse_higgsfield.py [--output-dir higgsfield_gallery] [--max-scrolls 50] [--headed]
"""

import argparse
import hashlib
import json
import logging
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import requests

sys.path.insert(0, str(Path(__file__).parent / ".pylibs"))

from playwright.sync_api import sync_playwright

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("higgsfield_parser")

GALLERY_URL = "https://higgsfield.ai/soul-community"


def _scroll_and_collect(page, max_scrolls: int, scroll_pause: float = 2.0) -> list[str]:
    """Scroll the page and collect all unique image URLs from the gallery."""
    collected: set[str] = set()

    def _harvest():
        imgs = page.query_selector_all("img")
        for img in imgs:
            src = img.get_attribute("src") or ""
            srcset = img.get_attribute("srcset") or ""
            for candidate in [src] + srcset.split(","):
                url = candidate.strip().split(" ")[0]
                if not url:
                    continue
                if any(skip in url for skip in [
                    "data:image", "svg+xml", "/favicon", "/logo",
                    "avatar", "icon", "/static/", "/_next/static",
                ]):
                    continue
                if url.startswith("//"):
                    url = "https:" + url
                if url.startswith("/"):
                    url = "https://higgsfield.ai" + url
                if re.search(r"\.(jpe?g|png|webp|avif)", url, re.IGNORECASE) or "image" in url:
                    collected.add(url)

        bg_urls = page.evaluate("""
            () => {
                const urls = [];
                document.querySelectorAll('[style*="background"]').forEach(el => {
                    const style = el.getAttribute('style') || '';
                    const match = style.match(/url\\(["']?([^"')]+)["']?\\)/);
                    if (match) urls.push(match[1]);
                });
                return urls;
            }
        """)
        for url in bg_urls:
            if url and not url.startswith("data:"):
                if url.startswith("/"):
                    url = "https://higgsfield.ai" + url
                collected.add(url)

    _harvest()
    prev_count = 0
    stale_rounds = 0

    for scroll_idx in range(max_scrolls):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(scroll_pause)
        _harvest()

        new_count = len(collected)
        logger.info(
            "Scroll %d/%d — found %d images so far", scroll_idx + 1, max_scrolls, new_count
        )

        if new_count == prev_count:
            stale_rounds += 1
            if stale_rounds >= 3:
                logger.info("No new images after 3 scrolls, stopping.")
                break
        else:
            stale_rounds = 0
        prev_count = new_count

    # Also try to capture images from network requests intercepted data
    return sorted(collected)


def _intercept_api_images(page) -> list[str]:
    """Collect image URLs from intercepted XHR/fetch responses."""
    urls: list[str] = []

    def handle_response(response):
        try:
            if response.status == 200 and "json" in (response.headers.get("content-type") or ""):
                body = response.text()
                found = re.findall(r'https?://[^\s"\'<>]+?\.(?:jpe?g|png|webp|avif)[^\s"\'<>]*', body)
                urls.extend(found)
        except Exception:
            pass

    page.on("response", handle_response)
    return urls


def _download_image(url: str, output_dir: Path, idx: int, total: int) -> bool:
    """Download a single image URL to the output directory."""
    try:
        parsed = urlparse(url)
        path_part = parsed.path.rstrip("/")
        ext_match = re.search(r"\.(jpe?g|png|webp|avif)", path_part, re.IGNORECASE)
        ext = f".{ext_match.group(1)}" if ext_match else ".jpg"

        name_base = Path(path_part).stem or hashlib.md5(url.encode()).hexdigest()[:12]
        name_base = re.sub(r"[^\w\-.]", "_", name_base)[:80]
        dest = output_dir / f"{name_base}{ext}"

        if dest.exists():
            logger.debug("[%d/%d] Skip (exists): %s", idx, total, dest.name)
            return True

        resp = requests.get(url, timeout=30, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Referer": GALLERY_URL,
        })
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "html" in content_type or len(resp.content) < 1000:
            logger.debug("[%d/%d] Skip (not image): %s", idx, total, url[:80])
            return False

        dest.write_bytes(resp.content)
        logger.info("[%d/%d] Saved: %s (%.1f KB)", idx, total, dest.name, len(resp.content) / 1024)
        return True

    except Exception as e:
        logger.warning("[%d/%d] Failed: %s — %s", idx, total, url[:80], e)
        return False


def run(output_dir: str, max_scrolls: int, headed: bool, workers: int):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    logger.info("Starting Higgsfield Soul Community parser...")
    logger.info("Output: %s | Max scrolls: %d | Workers: %d", out, max_scrolls, workers)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not headed)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        page = context.new_page()

        api_urls = _intercept_api_images(page)

        logger.info("Loading %s ...", GALLERY_URL)
        page.goto(GALLERY_URL, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(5_000)
        try:
            page.wait_for_selector("img", timeout=15_000)
        except Exception:
            logger.warning("No <img> tags appeared after 15s, continuing anyway...")

        img_urls = _scroll_and_collect(page, max_scrolls)
        img_urls = list(set(img_urls + api_urls))

        browser.close()

    if not img_urls:
        logger.warning("No images found! The page structure may have changed.")
        return

    logger.info("=" * 60)
    logger.info("Found %d unique image URLs. Downloading...", len(img_urls))
    logger.info("=" * 60)

    (out / "urls.json").write_text(json.dumps(img_urls, indent=2))

    success = 0
    total = len(img_urls)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_download_image, url, out, i, total): url
            for i, url in enumerate(img_urls, 1)
        }
        for f in as_completed(futures):
            if f.result():
                success += 1

    logger.info("=" * 60)
    logger.info("DONE — %d/%d images saved to %s", success, total, out)
    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Higgsfield Soul Community gallery parser")
    parser.add_argument("--output-dir", default="higgsfield_gallery",
                        help="Folder to save images (default: higgsfield_gallery)")
    parser.add_argument("--max-scrolls", type=int, default=50,
                        help="Max scroll iterations to load gallery (default: 50)")
    parser.add_argument("--headed", action="store_true",
                        help="Run browser in headed mode (visible)")
    parser.add_argument("--workers", type=int, default=8,
                        help="Parallel download workers (default: 8)")
    args = parser.parse_args()

    run(args.output_dir, args.max_scrolls, args.headed, args.workers)


if __name__ == "__main__":
    main()
