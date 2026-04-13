import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("bloggers_factory")


def setup_logging(verbose: bool = False, parallel: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    tag = "parallel" if parallel else "bulk"
    fmt = "%(asctime)s [%(levelname)s] "
    if parallel:
        fmt += "[%(threadName)s] "
    fmt += "%(message)s"

    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / f"{tag}_{datetime.now():%Y-%m-%d_%H%M%S}.log"),
    ]
    logging.basicConfig(level=level, format=fmt, handlers=handlers)

    for noisy in ("httpx", "httpcore", "openai", "fal_client"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def download_file(url: str, dest: Path, timeout: int = 60) -> bool:
    """Download a URL to a local file path. Returns True on success."""
    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            return True
        except Exception as e:
            logger.warning("Download failed (attempt %d/3): %s", attempt + 1, e)
            if attempt < 2:
                time.sleep(3)
    return False
