#!/usr/bin/env python3
"""Remove low-resolution images from a folder.

Usage:
    python remove_lowres.py [folder] [--min-size 512] [--dry-run]

Arguments:
    folder      Path to the image folder (default: higgsfield_gallery)
    --min-size  Minimum pixel value for the shortest side (default: 512)
    --dry-run   Preview what would be deleted without actually removing files
"""

import argparse
import os
import sys
from pathlib import Path

from typing import Optional, Tuple

from PIL import Image

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}


def get_image_size(filepath: Path) -> Optional[Tuple[int, int]]:
    try:
        with Image.open(filepath) as img:
            return img.size
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="Remove low-resolution images from a folder")
    parser.add_argument("folder", nargs="?", default="higgsfield_gallery", help="Target folder")
    parser.add_argument("--min-size", type=int, default=512,
                        help="Min pixels on shortest side (default: 512)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Only show what would be deleted")
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"Error: '{folder}' is not a directory")
        sys.exit(1)

    files = sorted(
        f for f in folder.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    )

    to_delete = []
    to_keep = []
    errors = []

    for f in files:
        size = get_image_size(f)
        if size is None:
            errors.append(f)
            continue
        w, h = size
        if min(w, h) < args.min_size:
            to_delete.append((f, w, h))
        else:
            to_keep.append((f, w, h))

    print(f"Folder: {folder}")
    print(f"Threshold: shortest side < {args.min_size}px")
    print(f"Total images scanned: {len(files)}")
    print(f"  Keep:   {len(to_keep)}")
    print(f"  Delete: {len(to_delete)}")
    if errors:
        print(f"  Errors: {len(errors)}")
    print()

    if not to_delete:
        print("Nothing to delete.")
        return

    if args.dry_run:
        print("Files that WOULD be deleted (dry run):")
        for f, w, h in to_delete:
            print(f"  {f.name}  ({w}x{h})")
        print(f"\nRe-run without --dry-run to actually delete.")
    else:
        deleted_bytes = 0
        for f, w, h in to_delete:
            size_bytes = f.stat().st_size
            f.unlink()
            deleted_bytes += size_bytes
        mb = deleted_bytes / (1024 * 1024)
        print(f"Deleted {len(to_delete)} low-res images ({mb:.1f} MB freed)")


if __name__ == "__main__":
    main()
