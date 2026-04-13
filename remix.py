#!/usr/bin/env python3
"""
UGC Remix Pipeline — generate minor-variation image remixes via Nano Banana.

Takes a folder of source images, optionally pulls creative inspiration from
a Higgsfield gallery via GPT-4o, then produces subtle one-axis remixes
(cloth / item / item-on-background / background) using fal-ai/nano-banana-2/edit.

Each remix changes ONE thing — the result looks like a sibling photo from
the same shoot with a strange/unexpected swap. iPhone snapshot aesthetic.

Usage:
    python remix.py --input ./my_photos --N 5
    python remix.py --input ./my_photos --gallery ./higgsfield_gallery --N 10
    python remix.py --input ./my_photos --output ./remixed --N 3 --aspect-ratio 1:1
"""

import argparse
import json
import logging
import os
import random
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

from lib.image_gen import _generate_single_image, ensure_fal_key
from lib.nanobanana_ugc_prompt import (
    GALLERY_IDEA_SYSTEM_PROMPT,
    GALLERY_IDEA_USER_SUFFIX,
    REMIX_USER_SUFFIX,
    build_remix_system_prompt,
    wrap_remix_prompt,
)
from lib.utils import download_file, setup_logging

logger = logging.getLogger("bloggers_factory")

SCRIPT_DIR = Path(__file__).resolve().parent
REMIX_GUIDE_PATH = SCRIPT_DIR / "remix_guide.md"
NUM_REMIXES = 2

_AXIS_KEYWORDS = {
    "CLOTH": ["outfit", "wearing", "suit", "armor", "chainmail", "foil", "wrap",
              "hazmat", "wetsuit", "scrubs", "bodysuit", "jacket", "coat", "dress"],
    "ITEM": ["holding", "holds", "clutch", "grip", "carry", "carried", "held",
             "glasses", "sunglasses", "goggles", "sword", "phone", "bouquet"],
    "ITEM_ON_BG": ["background", "behind", "placed", "wall of", "pile of",
                    "mountain of", "filling the background", "floor behind"],
    "BACKGROUND": ["move to", "transplant", "change background", "location",
                    "laundromat", "parking", "gas station", "bathroom", "elevator"],
}


def _extract_remix_summary(remix_text: str) -> str:
    """Extract a compact axis:key_material summary for dedup tracking."""
    lower = remix_text.lower()
    axis = "UNKNOWN"
    for ax, keywords in _AXIS_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            axis = ax
            break

    key_materials = []
    material_words = [
        "tinfoil", "aluminum foil", "chainmail", "bubble wrap", "hazmat",
        "wetsuit", "trash bag", "cling film", "armor", "leather", "vinyl",
        "cardboard", "neoprene", "surgical", "fur coat", "flamingo",
        "teddy bear", "disco ball", "pizza boxes", "christmas tree",
        "neon sign", "horse", "oranges", "lemons", "shoes", "flowers",
        "balloons", "rubber duck", "guitar", "baguette", "fish", "salmon",
        "sunflower", "protea", "dahlia", "television", "CRT",
        "laundromat", "parking garage", "gas station", "bathroom",
        "grocery", "elevator", "stairwell", "swimming pool", "cemetery",
        "subway", "construction", "thrift store",
    ]
    for mat in material_words:
        if mat in lower:
            key_materials.append(mat)

    mats = ", ".join(key_materials[:3]) if key_materials else "unidentified"
    return f"{axis}: {mats}"


def _load_remix_guide() -> str:
    if not REMIX_GUIDE_PATH.exists():
        raise FileNotFoundError(f"remix_guide.md not found at {REMIX_GUIDE_PATH}")
    return REMIX_GUIDE_PATH.read_text(encoding="utf-8")


def _upload_image(image_path: Path) -> str:
    """Upload a local image to fal.ai and return its HTTPS URL."""
    import fal_client

    return fal_client.upload_file(str(image_path))


def _load_gallery(gallery_dir: Path) -> list[Path]:
    """Return all image files in the gallery directory."""
    if not gallery_dir.is_dir():
        return []
    return sorted(
        f
        for f in gallery_dir.iterdir()
        if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
    )


def _generate_gallery_idea(
    gallery_images: list[Path],
    used_gallery_indices: set[int] | None = None,
) -> str | None:
    """Pick a random gallery image and ask GPT-4o for a strange creative idea.

    *used_gallery_indices* tracks which gallery images have already been used
    in this batch to avoid picking the same one twice.
    """
    if not gallery_images:
        return None

    import fal_client
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    available = [
        i for i in range(len(gallery_images))
        if used_gallery_indices is None or i not in used_gallery_indices
    ]
    if not available:
        available = list(range(len(gallery_images)))
    pick = random.choice(available)
    if used_gallery_indices is not None:
        used_gallery_indices.add(pick)

    inspo = gallery_images[pick]
    logger.info("  Gallery inspiration: %s", inspo.name)

    try:
        inspo_url = fal_client.upload_file(str(inspo))
    except Exception as e:
        logger.warning("  Gallery upload failed for %s: %s", inspo.name, e)
        return None

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": GALLERY_IDEA_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": GALLERY_IDEA_USER_SUFFIX},
                        {
                            "type": "image_url",
                            "image_url": {"url": inspo_url, "detail": "low"},
                        },
                    ],
                },
            ],
            temperature=1.0,
            max_tokens=200,
        )
        idea = response.choices[0].message.content.strip()
        logger.info("  Gallery idea: %s", idea)
        return idea
    except Exception as e:
        logger.warning("  Gallery idea generation failed: %s", e)
        return None


def _generate_remix_instructions(
    image_url: str,
    remix_guide_text: str,
    num_remixes: int = NUM_REMIXES,
    gallery_idea: str | None = None,
    already_used: list[str] | None = None,
) -> list[str] | None:
    """Call GPT-4o Vision to produce remix edit instructions for an image.

    *gallery_idea*  — creative seed from gallery image.
    *already_used*  — remix descriptions from previous images in the batch.

    Returns a list of remix prompt strings, or None on failure.
    """
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set in .env")

    client = OpenAI(api_key=api_key)
    system_prompt = build_remix_system_prompt(
        remix_guide_text, num_remixes,
        gallery_idea=gallery_idea, already_used=already_used,
    )

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": REMIX_USER_SUFFIX},
                            {
                                "type": "image_url",
                                "image_url": {"url": image_url, "detail": "high"},
                            },
                        ],
                    },
                ],
                temperature=1.0,
                max_tokens=1500,
            )

            raw = response.choices[0].message.content.strip()

            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1]
                if raw.endswith("```"):
                    raw = raw[:-3]
                raw = raw.strip()

            parsed = json.loads(raw)
            remixes = parsed.get("remixes", [])

            if not remixes or len(remixes) < num_remixes:
                logger.warning(
                    "GPT-4o returned %d remixes (expected %d), attempt %d/3",
                    len(remixes),
                    num_remixes,
                    attempt + 1,
                )
                if attempt < 2:
                    time.sleep(5 * (attempt + 1))
                    continue

            logger.info("Generated %d remix instructions", len(remixes))
            return remixes[:num_remixes]

        except json.JSONDecodeError as e:
            logger.warning(
                "GPT-4o response not valid JSON (attempt %d/3): %s\nRaw: %s",
                attempt + 1,
                e,
                raw[:300] if raw else "(empty)",
            )
            if attempt < 2:
                time.sleep(5 * (attempt + 1))

        except Exception as e:
            logger.warning(
                "Remix instruction generation failed (attempt %d/3): %s",
                attempt + 1,
                e,
            )
            if attempt < 2:
                time.sleep(5 * (attempt + 1))

    return None


def _plan_single_image(
    image_path: Path,
    output_root: Path,
    remix_guide_text: str,
    idx: int,
    total: int,
    gallery_images: list[Path] | None = None,
    batch_used: list[str] | None = None,
    used_gallery_indices: set[int] | None = None,
) -> dict | None:
    """Phase 1: upload image, get gallery idea, generate remix instructions.

    Returns a plan dict with everything needed for parallel rendering,
    or None if planning failed. Mutates *batch_used* in-place.
    """
    stem = image_path.stem
    image_dir = output_root / stem
    image_dir.mkdir(parents=True, exist_ok=True)

    metadata_path = image_dir / "metadata.json"
    if metadata_path.exists():
        logger.info("  [%d/%d] Skipping %s (already processed)", idx, total, stem)
        return None

    logger.info("  [%d/%d] Planning %s ...", idx, total, stem)

    original_dest = image_dir / f"original{image_path.suffix}"
    shutil.copy2(image_path, original_dest)

    try:
        image_url = _upload_image(image_path)
    except Exception as e:
        logger.error("  [%d/%d] Upload failed for %s: %s", idx, total, stem, e)
        return None

    gallery_idea = None
    if gallery_images:
        gallery_idea = _generate_gallery_idea(
            gallery_images, used_gallery_indices
        )

    remixes = _generate_remix_instructions(
        image_url, remix_guide_text,
        gallery_idea=gallery_idea,
        already_used=batch_used,
    )
    if not remixes:
        logger.error(
            "  [%d/%d] Failed to generate remix instructions for %s", idx, total, stem
        )
        return None

    if batch_used is not None:
        for r in remixes:
            summary = _extract_remix_summary(r)
            batch_used.append(summary)

    return {
        "image_path": image_path,
        "image_url": image_url,
        "image_dir": image_dir,
        "original_dest": original_dest,
        "gallery_idea": gallery_idea,
        "remixes": remixes,
        "idx": idx,
        "total": total,
    }


def _render_single_image(
    plan: dict,
    aspect_ratio: str,
) -> bool:
    """Phase 2: render all remixes for one image via Nano Banana (parallelizable)."""
    stem = plan["image_path"].stem
    image_url = plan["image_url"]
    image_dir = plan["image_dir"]
    remixes = plan["remixes"]
    idx = plan["idx"]
    total = plan["total"]

    generated_files = []
    remix_prompts_used = []

    for ri, raw_instruction in enumerate(remixes, 1):
        prompt = wrap_remix_prompt(raw_instruction)
        remix_prompts_used.append(prompt)

        logger.info("  [%d/%d] Generating remix %d for %s ...", idx, total, ri, stem)

        _, result = _generate_single_image(
            prompt_idx=ri - 1,
            prompt=prompt,
            ref_image_urls=[image_url],
            aspect_ratio=aspect_ratio,
            model_name=f"{stem}_remix{ri}",
        )

        images = result.get("images", [])
        if not images:
            logger.error(
                "  [%d/%d] Nano Banana returned no image for remix %d of %s",
                idx, total, ri, stem,
            )
            continue

        dest = image_dir / f"remix_{ri}.png"
        if download_file(images[0]["url"], dest):
            generated_files.append(dest.name)
            logger.info("  [%d/%d] Saved %s", idx, total, dest.name)
        else:
            logger.error(
                "  [%d/%d] Download failed for remix %d of %s", idx, total, ri, stem
            )

    metadata_path = image_dir / "metadata.json"
    meta = {
        "source_image": str(plan["image_path"]),
        "aspect_ratio": aspect_ratio,
        "gallery_idea": plan["gallery_idea"],
        "remix_instructions": remixes,
        "remix_prompts_full": remix_prompts_used,
        "generated_files": generated_files,
        "original_file": plan["original_dest"].name,
        "generated_at": datetime.now().isoformat(),
    }
    with open(metadata_path, "w") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    success_count = len(generated_files)
    logger.info(
        "  [%d/%d] %s done — %d/%d remixes generated",
        idx, total, stem, success_count, len(remixes),
    )
    return success_count > 0


def run_remix(args: argparse.Namespace) -> None:
    """Main entry: process input folder and generate remixes."""
    ensure_fal_key()

    input_dir = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_dir.is_dir():
        logger.error("Input directory does not exist: %s", input_dir)
        sys.exit(1)

    all_images = sorted(
        f
        for f in input_dir.iterdir()
        if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
    )

    if not all_images:
        logger.error("No images found in %s", input_dir)
        sys.exit(1)

    n = args.N
    if n and n < len(all_images):
        selected = random.sample(all_images, n)
    else:
        selected = all_images

    total = len(selected)
    aspect_ratio = args.aspect_ratio

    remix_guide_text = _load_remix_guide()

    gallery_dir = Path(args.gallery)
    gallery_images = _load_gallery(gallery_dir) if gallery_dir.is_dir() else []
    if gallery_images:
        logger.info(
            "Loaded %d gallery inspiration images from %s",
            len(gallery_images),
            gallery_dir,
        )
    else:
        logger.info("No gallery dir or no images — running without gallery inspiration")

    workers = args.workers
    batch_used: list[str] = []
    used_gallery_indices: set[int] = set()

    logger.info("=" * 60)
    logger.info(
        "REMIX | %d images | %d workers | gallery: %d | aspect: %s | output: %s",
        total,
        workers,
        len(gallery_images),
        aspect_ratio,
        output_dir,
    )
    logger.info("=" * 60)

    # ── Phase 1: plan sequentially (fast GPT calls, builds diversity) ──
    logger.info("Phase 1/2 — generating remix instructions (sequential) ...")
    plans: list[dict] = []
    for i, img in enumerate(selected, 1):
        plan = _plan_single_image(
            img,
            output_dir,
            remix_guide_text,
            i,
            total,
            gallery_images or None,
            batch_used=batch_used,
            used_gallery_indices=used_gallery_indices,
        )
        if plan:
            plans.append(plan)

    if not plans:
        logger.error("No images to render — all planning failed or skipped")
        return

    logger.info(
        "Phase 1 done — %d/%d images planned, %d remix ideas total",
        len(plans), total, sum(len(p["remixes"]) for p in plans),
    )

    # ── Phase 2: render in parallel (slow Nano Banana calls) ──
    logger.info("Phase 2/2 — rendering remixes (%d workers) ...", workers)
    success = 0
    failed = 0

    if workers <= 1:
        for plan in plans:
            if _render_single_image(plan, aspect_ratio):
                success += 1
            else:
                failed += 1
    else:
        with ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix="render"
        ) as ex:
            futures = {
                ex.submit(_render_single_image, plan, aspect_ratio): plan
                for plan in plans
            }
            for future in as_completed(futures):
                try:
                    if future.result():
                        success += 1
                    else:
                        failed += 1
                except Exception as e:
                    logger.error("Render worker exception: %s", e)
                    failed += 1

    skipped = total - len(plans)
    logger.info("=" * 60)
    logger.info(
        "REMIX DONE | success: %d | failed: %d | skipped: %d / %d",
        success, failed, skipped, total,
    )
    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="UGC Remix Pipeline — creative image remixes via Nano Banana",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Input folder with source images (jpg/png/webp)",
    )
    parser.add_argument(
        "--output",
        default="output_remixes",
        help="Root output directory (default: output_remixes)",
    )
    parser.add_argument(
        "-N",
        type=int,
        default=None,
        help="Number of images to process (randomly sampled if less than total)",
    )
    parser.add_argument(
        "--gallery",
        default="higgsfield_gallery",
        help="Gallery folder for creative inspiration (default: higgsfield_gallery)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Parallel workers (default: 1)",
    )
    parser.add_argument(
        "--aspect-ratio",
        default="9:16",
        help="Aspect ratio for generated images (default: 9:16)",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")

    args = parser.parse_args()
    setup_logging(verbose=args.verbose, parallel=args.workers > 1)
    run_remix(args)


if __name__ == "__main__":
    main()
