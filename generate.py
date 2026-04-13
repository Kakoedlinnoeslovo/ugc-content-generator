#!/usr/bin/env python3
"""
UGC Feed Generator — describe + regenerate images with UGC style via Nano Banana.

Usage:
    python generate.py --ugc-feed -N 2 --workers 2 --verbose
"""

import argparse
import logging
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

from lib.utils import setup_logging, download_file
from lib.image_gen import (
    ensure_fal_key,
    _generate_single_image,
    describe_image_ugc,
    extract_style_from_image,
)
from lib.nanobanana_ugc_prompt import ugc_style_modifier, merge_scene_with_style

logger = logging.getLogger("bloggers_factory")


def _load_gallery(gallery_dir: Path) -> list[Path]:
    """Return all image files in the gallery directory."""
    if not gallery_dir.is_dir():
        return []
    return sorted(
        f for f in gallery_dir.iterdir()
        if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
    )


def _pick_and_extract_style(gallery_images: list[Path], idx: int, total: int) -> dict | None:
    """Pick a random gallery image, upload it, and extract style elements."""
    if not gallery_images:
        return None

    inspo = random.choice(gallery_images)
    logger.info("  [%d/%d] Inspiration image: %s", idx, total, inspo.name)

    try:
        import fal_client as _fal
        inspo_url = _fal.upload_file(str(inspo))
    except Exception as e:
        logger.warning("  [%d/%d] Gallery upload failed for %s: %s", idx, total, inspo.name, e)
        return None

    style = extract_style_from_image(inspo_url)
    if style:
        logger.info("  [%d/%d] Extracted style — clothing: %.40s…", idx, total,
                     style.get("clothing", "")[:40])
    return style


def _process_single_ugc_image(
    image_path: Path,
    output_dir: Path,
    aspect_ratio: str,
    idx: int,
    total: int,
    gallery_images: list[Path] | None = None,
) -> bool:
    """Process one image through the describe-then-generate UGC pipeline.

    If *gallery_images* is provided, a random gallery image is picked and its
    style (clothing, makeup, lighting, items, look) is merged into the prompt.
    """
    stem = image_path.stem
    dest = output_dir / f"{stem}.png"
    if dest.exists():
        logger.info("  [%d/%d] Skipping %s (already exists)", idx, total, stem)
        return True

    try:
        import fal_client as _fal
        image_url = _fal.upload_file(str(image_path))
    except Exception as e:
        logger.error("  [%d/%d] Upload failed for %s: %s", idx, total, stem, e)
        return False

    scene_prompt = describe_image_ugc(image_url)
    if not scene_prompt:
        logger.error("  [%d/%d] GPT-4o description failed for %s", idx, total, stem)
        return False

    # --- gallery style injection ---
    if gallery_images:
        style = _pick_and_extract_style(gallery_images, idx, total)
        if style:
            scene_prompt = merge_scene_with_style(scene_prompt, style)

    ugc_prompt = ugc_style_modifier(scene_prompt)
    logger.info("  [%d/%d] Generating UGC image for %s...", idx, total, stem)

    _, result = _generate_single_image(0, ugc_prompt, [image_url], aspect_ratio, stem)
    images = result.get("images", [])
    if not images:
        logger.error("  [%d/%d] Nano Banana returned no image for %s", idx, total, stem)
        return False

    if not download_file(images[0]["url"], dest):
        logger.error("  [%d/%d] Download failed for %s", idx, total, stem)
        return False

    logger.info("  [%d/%d] Saved %s", idx, total, dest.name)
    return True


def run_ugc_feed(args: argparse.Namespace) -> None:
    """Process a folder of images through the UGC pipeline."""
    ensure_fal_key()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_dir.is_dir():
        logger.error("Input directory does not exist: %s", input_dir)
        return

    all_images = sorted(
        f for f in input_dir.iterdir()
        if f.suffix.lower() in (".jpg", ".jpeg", ".png")
    )

    if not all_images:
        logger.error("No images found in %s", input_dir)
        return

    if args.num_images and args.num_images < len(all_images):
        selected = random.sample(all_images, args.num_images)
    else:
        selected = all_images

    gallery_dir = Path(args.gallery_dir)
    gallery_images = _load_gallery(gallery_dir) if gallery_dir.is_dir() else []
    if gallery_images:
        logger.info("Loaded %d gallery inspiration images from %s",
                     len(gallery_images), gallery_dir)
    else:
        logger.info("No gallery dir or no images — running without style inspiration")

    total = len(selected)
    workers = args.workers
    aspect_ratio = getattr(args, "aspect_ratio", "1:1")

    logger.info("=" * 60)
    logger.info("UGC FEED | %d images | %d workers | gallery: %d | output: %s",
                total, workers, len(gallery_images), output_dir)
    logger.info("=" * 60)

    success = 0
    failed = 0

    if workers <= 1:
        for i, img in enumerate(selected, 1):
            if _process_single_ugc_image(img, output_dir, aspect_ratio, i, total,
                                         gallery_images or None):
                success += 1
            else:
                failed += 1
    else:
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="ugc") as ex:
            futures = {
                ex.submit(
                    _process_single_ugc_image, img, output_dir, aspect_ratio, i, total,
                    gallery_images or None,
                ): img
                for i, img in enumerate(selected, 1)
            }
            for future in as_completed(futures):
                if future.result():
                    success += 1
                else:
                    failed += 1

    logger.info("=" * 60)
    logger.info("UGC FEED DONE | success: %d | failed: %d / %d", success, failed, total)
    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="UGC Feed Generator — AI image regeneration with UGC style",
    )

    parser.add_argument("--ugc-feed", action="store_true",
                        help="Process a folder of images through the UGC pipeline")
    parser.add_argument("--input-dir", default="for_feed_preview",
                        help="Input directory with source images (default: for_feed_preview)")
    parser.add_argument("-N", "--num-images", type=int, default=None,
                        help="Number of images to process (default: all)")
    parser.add_argument("--workers", type=int, default=4,
                        help="Number of parallel workers (default: 4)")
    parser.add_argument("--gallery-dir", default="higgsfield_gallery",
                        help="Gallery of inspiration images for style transfer (default: higgsfield_gallery)")
    parser.add_argument("--output-dir", default="ugc_output",
                        help="Output directory for UGC images (default: ugc_output)")
    parser.add_argument("--aspect-ratio", default="9:16",
                        help="Aspect ratio for generated images (default: 9:16)")
    parser.add_argument("--verbose", action="store_true")

    args = parser.parse_args()

    if args.ugc_feed:
        setup_logging(verbose=args.verbose, parallel=args.workers > 1)
        run_ugc_feed(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
