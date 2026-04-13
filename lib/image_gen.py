import logging
import os
import time

import fal_client
from openai import OpenAI

from .nanobanana_ugc_prompt import (
    UGC_SYSTEM_PROMPT,
    UGC_USER_SUFFIX,
    STYLE_EXTRACT_SYSTEM_PROMPT,
    STYLE_EXTRACT_USER_SUFFIX,
)

logger = logging.getLogger("bloggers_factory")


def ensure_fal_key():
    key = os.getenv("FAL_AI_API_KEY", "")
    if not key:
        raise RuntimeError("FAL_AI_API_KEY not set in .env")
    os.environ["FAL_KEY"] = key


def _generate_single_image(
    prompt_idx: int,
    prompt: str,
    ref_image_urls: list[str],
    aspect_ratio: str,
    model_name: str,
) -> tuple[int, dict]:
    for attempt in range(3):
        try:
            result = fal_client.subscribe(
                "fal-ai/nano-banana-2/edit",
                arguments={
                    "prompt": prompt,
                    "image_urls": ref_image_urls,
                    "num_images": 1,
                    "aspect_ratio": aspect_ratio,
                    "output_format": "png",
                    "resolution": "1K",
                    "safety_tolerance": "6",
                },
                with_logs=False,
            )
            images = result.get("images", [])
            if images:
                logger.info("  [%s] Image %d generated", model_name, prompt_idx + 1)
            else:
                logger.warning("  [%s] Image %d: no image returned", model_name, prompt_idx + 1)
            return (prompt_idx, result)

        except Exception as e:
            logger.warning("  [%s] Image %d failed (attempt %d/3): %s",
                           model_name, prompt_idx + 1, attempt + 1, e)
            if attempt < 2:
                time.sleep(10 * (attempt + 1))

    return (prompt_idx, {"images": [], "error": "all attempts failed"})


def describe_image_ugc(image_url: str) -> str | None:
    """Describe an image via GPT-4o Vision with UGC-style instructions.

    *image_url* must be an HTTPS URL (e.g. a fal.ai upload URL).
    Returns the raw scene description string, or None on failure.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set in .env")

    client = OpenAI(api_key=api_key)

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": UGC_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": UGC_USER_SUFFIX,
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": image_url, "detail": "high"},
                            },
                        ],
                    },
                ],
                temperature=0.7,
                max_tokens=500,
            )
            prompt = response.choices[0].message.content.strip()
            logger.info("Scene prompt generated (%d chars)", len(prompt))
            return prompt

        except Exception as e:
            logger.warning("Scene prompt generation failed (attempt %d/3): %s", attempt + 1, e)
            if attempt < 2:
                time.sleep(5 * (attempt + 1))

    return None


def extract_style_from_image(image_url: str) -> dict | None:
    """Extract style elements (clothing, makeup, lighting, items, mood) via GPT-4o.

    Returns a parsed dict with keys: clothing, makeup_styling, lighting,
    items_props, look_mood — or None on failure.
    """
    import json as _json

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set in .env")

    client = OpenAI(api_key=api_key)

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": STYLE_EXTRACT_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": STYLE_EXTRACT_USER_SUFFIX},
                            {
                                "type": "image_url",
                                "image_url": {"url": image_url, "detail": "high"},
                            },
                        ],
                    },
                ],
                temperature=0.4,
                max_tokens=500,
            )
            raw = response.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
            style = _json.loads(raw)
            logger.info("Style extracted (%d keys)", len(style))
            return style

        except Exception as e:
            logger.warning("Style extraction failed (attempt %d/3): %s", attempt + 1, e)
            if attempt < 2:
                time.sleep(5 * (attempt + 1))

    return None
