"""
UGC-focused prompts for Nano Banana scene recreation.

The goal is to make AI-generated frames look like authentic user-generated
content (phone-camera selfie videos, casual candid moments) rather than
polished studio photography.

Also contains remix prompts — creative edit instructions for generating
Instagram-native variations of existing images.
"""

# ---------------------------------------------------------------------------
# GPT-4o system prompt — replaces the old SCENE_RECREATION_SYSTEM_PROMPT
# ---------------------------------------------------------------------------

UGC_SYSTEM_PROMPT = """\
You are an expert at describing images for AI image generation that looks like \
authentic user-generated content (UGC) — the kind of raw, lo-fi photos that \
populate real Instagram feeds and Tumblr archives.

You will receive a single frame from a short video or photo. Your task is to \
describe the scene so that an AI image model can recreate it with a different \
person while preserving the raw, imperfect UGC aesthetic of the original.

CRITICAL — the output image must look like a real photo taken on a compact \
digital camera, disposable film camera, or phone camera — NOT a professional \
photoshoot. Lean into every imperfection. \
Do NOT include any phone UI, status bars, camera buttons, or device frames.

CAMERA & LENS — pick whichever matches the source image best:
- Direct on-camera flash in a dim environment (harsh, flat light on subject, \
  hard shadow cast on wall behind, slightly blown-out skin, red-eye possible)
- Point-and-shoot compact digital camera (slight barrel distortion, auto-flash, \
  digital noise, mediocre autofocus)
- Old phone camera or webcam (low resolution feel, soft focus, color fringing)
- Disposable / cheap film camera (flash falloff, warm color cast, visible grain)
- No flash — available light only (underexposed, motion blur, color cast from \
  ambient sources like fluorescent, tungsten, neon, or mixed)

Describe:
- The subject's EXACT pose, body position, gestures, and facial expression. \
  Note if they are NOT looking at the camera — caught mid-action, looking away, \
  eyes closed, or unaware of being photographed.
- Outfit and accessories exactly as they appear (wrinkles, fit, details)
- Setting / background / location — favor mundane real-world places: parking \
  lots, sidewalks, bedrooms, doorways, stairwells, kitchens, bathrooms, cars, \
  empty rooms, streets at night. Include visible clutter and real-life mess.
- Lighting AS IT IS — direct flash, mixed color temperatures, uneven shadows, \
  neon/ambient glow, lens flare, light leaks. Specify the color temperature \
  shift if present (greenish fluorescent, warm tungsten, cool daylight).
- Camera angle and framing: note if the composition is off-center, tilted, \
  shot from below waist level, or if the subject is partially cropped out of \
  frame (head cut off, body truncated at unusual point). Describe the distance \
  — extreme close-up, medium, or far away.
- Technical flaws: motion blur, digital noise/grain, soft focus, chromatic \
  aberration, overexposure, underexposure, white balance errors
- Overall mood: spontaneous, candid, raw, caught-off-guard, nonchalant, bored, \
  mundane, intimate, voyeuristic, behind-the-scenes

Style rules for your description:
- Use phrases like "direct flash photo", "point-and-shoot camera", "candid \
  snapshot", "compact digital camera", "lo-fi", "harsh flash", "available \
  light", "caught mid-moment", "off-center framing", "partially cropped"
- NEVER use words like "editorial", "magazine", "studio", "professional \
  photography", "elegant", "Instagram-worthy", "high-fashion", "glamorous", \
  "beautifully lit", "perfectly composed"
- If the scene looks messy, dark, underexposed, or awkwardly framed — say so
- NEVER mention phone UI, status bars, camera interface, buttons, or device frames

Write a single vivid paragraph (3-5 sentences) suitable as a text-to-image prompt.
Do NOT mention any real names. Refer to the person as "a young woman" or similar.
The output MUST read like a description of a raw, imperfect snapshot — not a \
professional photo. NEVER describe any phone UI elements, device frames, or interface overlays."""

# ---------------------------------------------------------------------------
# Extra text appended to the GPT-4o user message
# ---------------------------------------------------------------------------

UGC_USER_SUFFIX = (
    "Describe this image for AI image generation. "
    "The generated image MUST look like a raw snapshot from a compact digital "
    "camera or phone — NOT a professional photoshoot. "
    "Pay close attention to: flash usage (direct on-camera flash vs available "
    "light), color temperature shifts, whether the subject is looking at the "
    "camera or caught off-guard, awkward/unconventional cropping, and any "
    "lo-fi technical artifacts (noise, blur, soft focus, overexposure). "
    "Preserve the exact pose, environment, camera angle, and all imperfections. "
    "Do NOT include any phone UI, status bars, or device frames in the description. "
    "A different person will be placed into this scene."
)

# ---------------------------------------------------------------------------
# Nano Banana prompt wrapper — applied right before the API call
# ---------------------------------------------------------------------------

_UGC_PREFIX = (
    "Raw lo-fi snapshot, compact digital camera or phone camera. "
)

_UGC_SUFFIX = (
    " Shot on point-and-shoot camera or phone, direct flash or harsh available light, "
    "visible digital noise and grain, imperfect white balance with slight color cast, "
    "off-center composition, not a studio photo, candid and unpolished, "
    "no phone UI or device frame."
)


def ugc_style_modifier(prompt: str) -> str:
    """Wrap a scene description with UGC style tags for Nano Banana."""
    return _UGC_PREFIX + prompt.strip() + _UGC_SUFFIX


# ---------------------------------------------------------------------------
# Remix: GPT-4o system prompt for generating creative edit instructions
# ---------------------------------------------------------------------------

_REMIX_SYSTEM_TEMPLATE = """\
You are a strange-UGC content generator. You create BOLD, DRAMATIC single-axis \
variations of existing photos for an AI image model (Nano Banana / fal.ai).

You will receive a photo. Propose exactly {num_remixes} remix ideas. \
Each remix changes ONE thing — but that ONE change must be VISUALLY DRAMATIC \
and IMPOSSIBLE TO MISS. The composition and pose stay the same, but the \
swapped element should hit the viewer instantly.

REMIX GUIDE (use this for inspiration and item catalogs):
---
{remix_guide}
---

{gallery_idea_section}

MANDATORY AXIS ASSIGNMENT:
{axis_assignment}

RULES:
1. Each remix MUST change exactly ONE of these four axes:
   {axes_block}
2. THE CHANGE MUST BE UNMISSABLE. If a viewer glances at original vs remix \
   for 1 second, they must instantly see what changed. Subtle = failure.
3. You MUST follow the MANDATORY AXIS ASSIGNMENT above. Each remix is \
   pre-assigned a specific axis — do NOT deviate.
4. The remix instruction MUST be a SELF-CONTAINED prompt describing the \
   FULL final image — not just the delta from the original.
5. Every remix MUST feature a DIFFERENT RANDOM PERSON — different face, \
   body type, age, gender, ethnicity. No two remixes should share the same \
   person, and none should match the original. Describe each person briefly \
   in the prompt (e.g. "a tall bearded man in his 30s", "a teenage girl \
   with short bleached hair", "an older woman with deep wrinkles"). The \
   composition and pose stay the same — only the person changes along with \
   the one dramatic element swap.
6. Every remix MUST look like it was shot on an iPhone or cheap phone camera: \
   direct flash, digital noise, off-center framing, slight overexposure. \
   NEVER say "editorial", "studio", "professional".
7. For CLOTH: always specify the exact MATERIAL (chainmail metal rings, \
   black trash bags, bubble wrap air pockets, yellow neoprene, cling film, \
   wetsuit neoprene, cardboard armor, surgical scrubs). \
   Never just say "a different top" or "a sweater". \
   NEVER USE TINFOIL / ALUMINUM FOIL — it is BANNED, overused, and boring.
8. For ITEM_ON_BG: always specify SIZE relative to the person (e.g. "taller \
   than the person", "filling the entire background wall", "covering the \
   entire floor behind them"). \
   NEVER USE INFLATABLE PINK FLAMINGO — it is BANNED, overused.
9. VARIETY IS CRITICAL. Pick DIFFERENT items/materials/locations from the \
   catalog each time. If in doubt, choose the LEAST OBVIOUS option. \
   Surprise the viewer — don't default to the first item in each list.
10. Each remix: 3-5 sentences. Write in English.

OUTPUT FORMAT — return valid JSON only, no markdown fences:
{{"remixes": ["<remix 1 prompt>", "<remix 2 prompt>"]}}
"""

REMIX_USER_SUFFIX = (
    "Analyze this photo: the outfit, pose, setting, lighting, and objects. "
    "Generate remix ideas — each one changes ONLY ONE thing but that change "
    "must be BOLD and UNMISSABLE. EVERY remix must feature a DIFFERENT RANDOM "
    "PERSON (different face, body type, age, gender, ethnicity — describe them "
    "briefly in each prompt). No two remixes share the same person. "
    "FOLLOW THE MANDATORY AXIS ASSIGNMENT exactly. "
    "For clothing: dramatic material swaps "
    "(chainmail, armor, hazmat, bubble wrap, wetsuit — NOT tinfoil, NOT just "
    "a different sweater). "
    "For items: LARGE objects that fill the frame. For background objects: "
    "MASSIVE, scene-dominating, 30-50% of background (NOT pink flamingo). "
    "iPhone snapshot aesthetic — raw, flash, imperfect."
)


_ALL_AXES = ["CLOTH", "ITEM", "ITEM_ON_BG", "BACKGROUND"]

_AXIS_DESCRIPTIONS = {
    "CLOTH": (
        "CLOTH — swap the outfit to a DRAMATICALLY different material/texture "
        "(chainmail, armor, hazmat suit, bubble wrap, wetsuit, trash bags, "
        "cling film, cardboard armor — NOT just a different color sweater. "
        "The material change must be SHOCKING. TINFOIL/ALUMINUM FOIL IS BANNED.)"
    ),
    "ITEM": (
        "ITEM — add/swap one held object (must be LARGE enough to fill a "
        "significant portion of the frame — giant flowers, whole fish, huge "
        "inflatable, oversized glasses that dominate the face, vintage phone, "
        "fire extinguisher, baguette, disco ball)"
    ),
    "ITEM_ON_BG": (
        "ITEM_ON_BG — place one MASSIVE object in the background (must fill "
        "30-50% of the background area — human-sized teddy bear, wall of TVs, "
        "mountain of shoes, giant neon sign, Christmas tree, pile of flowers. "
        "NO small objects tucked in corners. PINK FLAMINGO IS BANNED.)"
    ),
    "BACKGROUND": (
        "BACKGROUND — change the location (laundromat, gas station at night, "
        "parking garage, public bathroom, grocery store, elevator, stairwell, "
        "empty pool, construction site, subway platform). "
        "Keep person, outfit, items, pose."
    ),
}


def _pick_axes(num_remixes: int) -> list[str]:
    """Pick axes for each remix slot, ensuring maximum variety."""
    import random as _rnd

    shuffled = _ALL_AXES[:]
    _rnd.shuffle(shuffled)
    if num_remixes <= len(shuffled):
        return shuffled[:num_remixes]
    result = shuffled[:]
    while len(result) < num_remixes:
        _rnd.shuffle(shuffled)
        result.extend(shuffled[: num_remixes - len(result)])
    return result


def build_remix_system_prompt(
    remix_guide_text: str,
    num_remixes: int = 2,
    gallery_idea: str | None = None,
    already_used: list[str] | None = None,
) -> str:
    """Build the GPT-4o system prompt for remix generation.

    *gallery_idea*  — a creative seed from GPT + gallery image.
    *already_used*  — short descriptions of remix ideas already generated
                      for OTHER images in this batch (forces diversity).
    """
    import random as _rnd

    parts: list[str] = []

    if gallery_idea:
        parts.append(
            "GALLERY INSPIRATION — a creative idea generated from a reference image. "
            "You MUST use this as the basis for at least ONE of your remixes "
            "(adapt it to fit the source photo):\n"
            f'"{gallery_idea}"'
        )

    if already_used:
        avoid_list = "\n".join(f"- {item}" for item in already_used[-20:])
        parts.append(
            "ALREADY USED IN THIS BATCH — the following axis:material/item combos "
            "were already generated for other images. DO NOT repeat ANY of them. "
            "Pick completely DIFFERENT items, materials, objects, and locations. "
            "If you see tinfoil, chainmail, flamingo, teddy bear below — those "
            "are ESPECIALLY off-limits:\n"
            f"{avoid_list}"
        )

    idea_section = "\n\n".join(parts)

    assigned_axes = _pick_axes(num_remixes)
    axis_assignment = "\n".join(
        f"- Remix {i + 1}: use axis {ax}"
        for i, ax in enumerate(assigned_axes)
    )

    shuffled_descs = [_AXIS_DESCRIPTIONS[ax] for ax in _ALL_AXES]
    _rnd.shuffle(shuffled_descs)
    axes_block = "\n   ".join(f"- {d}" for d in shuffled_descs)

    return _REMIX_SYSTEM_TEMPLATE.format(
        remix_guide=remix_guide_text,
        num_remixes=num_remixes,
        gallery_idea_section=idea_section,
        axis_assignment=axis_assignment,
        axes_block=axes_block,
    )


_SCENE_PREAMBLE = (
    "Use the uploaded photo as scene/composition reference only. "
    "Keep the same pose, camera angle, and framing. "
    "Generate a COMPLETELY DIFFERENT RANDOM PERSON — different face, body type, "
    "age, gender, and ethnicity from the original. Do NOT replicate the original "
    "person's appearance. The scene stays nearly identical with one element swapped. "
    "iPhone snapshot aesthetic: direct flash, digital noise, "
    "off-center framing, candid, unpolished. "
)


def wrap_remix_prompt(edit_instruction: str) -> str:
    """Prepend scene-preservation preamble to a remix edit instruction."""
    return _SCENE_PREAMBLE + edit_instruction.strip()


# ---------------------------------------------------------------------------
# Style extraction: pull cloth / makeup / lighting / items / look from a
# gallery inspiration image and merge into a scene prompt
# ---------------------------------------------------------------------------

STYLE_EXTRACT_SYSTEM_PROMPT = """\
You are an expert fashion and photography stylist. You will receive a single \
reference photo. Your job is to extract ONLY the visual style elements from it \
— NOT the person's identity or face.

Extract these five categories as SHORT, concrete phrases (each 1-2 sentences):

1. CLOTHING — describe every garment: type, color, fabric, fit, layering, \
   visible brands/logos, and how it's worn (unbuttoned, rolled sleeves, etc.)
2. MAKEUP & STYLING — hair styling, makeup look (lip color, eye makeup, blush), \
   nails, jewelry, piercings, accessories (hats, glasses, bags, belts, scarves)
3. LIGHTING — the lighting setup in the photo: flash, natural, golden hour, \
   neon, fluorescent, mixed, hard/soft shadows, color temperature, direction
4. ITEMS & PROPS — any objects the person is holding or interacting with: \
   drinks, food, phone, cigarette, flowers, bags, books, etc. Also notable \
   background objects that contribute to the vibe.
5. LOOK & MOOD — the overall vibe/energy: attitude, gaze direction, body \
   language, facial expression, and the general aesthetic (e.g. streetwear \
   casual, night-out glam, minimalist, grunge, Y2K, cottagecore, etc.)

OUTPUT FORMAT — return valid JSON only, no markdown fences:
{{"clothing": "...", "makeup_styling": "...", "lighting": "...", \
"items_props": "...", "look_mood": "..."}}"""

STYLE_EXTRACT_USER_SUFFIX = (
    "Extract the visual style elements from this reference photo. "
    "Focus on clothing, makeup/styling, lighting, items/props, and overall "
    "look/mood. Do NOT describe the person's face or identity."
)


GALLERY_IDEA_SYSTEM_PROMPT = """\
You are a strange-creative-director for iPhone-aesthetic UGC content.

You will receive a single reference photo from a curated gallery. \
Your job is to extract ONE weird, specific, Pinterest-strange creative idea \
inspired by this image — something that could be used as a minor tweak to \
an existing photo.

The idea should fit ONE of these categories:
- A specific strange CLOTHING item (e.g. "chainmail vest over white t-shirt")
- A specific strange HELD ITEM (e.g. "clutching a raw salmon like a bouquet")
- A specific strange BACKGROUND OBJECT (e.g. "giant inflatable pink flower behind them")
- A specific strange BACKGROUND LOCATION (e.g. "laundromat with fluorescent lights")

The idea should be:
- Oddly specific (not generic like "flowers" — say "single giant protea flower")
- iPhone-aesthetic compatible (raw, candid, flash, imperfect)
- Strange but visually catchy (scroll-stopping weird, not ugly-weird)
- One sentence, concrete and actionable

OUTPUT: return a single sentence — the creative idea. No JSON, no formatting."""

GALLERY_IDEA_USER_SUFFIX = (
    "Look at this reference image. Extract ONE strange, specific, "
    "Pinterest-weird creative idea inspired by what you see — an unusual "
    "clothing piece, a weird held object, a strange background item, or "
    "an unexpected location. One sentence, oddly specific."
)


def merge_scene_with_style(scene_prompt: str, style_json: dict) -> str:
    """Combine a scene description with extracted style elements.

    *scene_prompt* is the GPT-4o scene description of the source image.
    *style_json* is the parsed dict from style extraction.
    Returns a merged prompt ready for ugc_style_modifier().
    """
    parts = [scene_prompt.strip()]

    clothing = style_json.get("clothing", "").strip()
    makeup = style_json.get("makeup_styling", "").strip()
    items = style_json.get("items_props", "").strip()
    look = style_json.get("look_mood", "").strip()

    style_overrides = []
    if clothing:
        style_overrides.append(f"Wearing: {clothing}")
    if makeup:
        style_overrides.append(f"Styling: {makeup}")
    if items:
        style_overrides.append(f"Props: {items}")
    if look:
        style_overrides.append(f"Vibe: {look}")

    if style_overrides:
        parts.append("STYLE OVERRIDE from reference — " + ". ".join(style_overrides) + ".")

    lighting = style_json.get("lighting", "").strip()
    if lighting:
        parts.append(f"Lighting: {lighting}.")

    return " ".join(parts)
