"""Cover-before-read: SAM 3.1 outlines what a short phrase names in a photo; the person decides what gets covered.

The image is checked here, sent once and dropped. Only boxes come back (source pixels); the browser paints them black
on its own copy, so the reading model never sees the covered regions. SAM can miss a region, so the screen says
so and the person looks at the preview before anything is sent.
"""
import re

import muse
import vision

MAX_PHRASE = 40
MAX_REGIONS = 20
MIN_CONFIDENCE = 0.3
BOX = re.compile(r"<\|box;x1=(\d+);y1=(\d+);x2=(\d+);y2=(\d+);w=(\d+);h=(\d+)(?:;c=([0-9.]+))?\|>")


def parse_regions(text):
    """Boxes from SAM's token text, clipped to the image, most confident first. Masks are ignored."""
    regions = []
    for x1, y1, x2, y2, w, h, c in BOX.findall(text or ""):
        x1, y1, x2, y2, w, h = (int(v) for v in (x1, y1, x2, y2, w, h))
        confidence = float(c) if c else 1.0
        x2, y2 = min(x2, w - 1), min(y2, h - 1)
        if w <= 0 or h <= 0 or x1 >= x2 or y1 >= y2 or confidence < MIN_CONFIDENCE:
            continue
        regions.append({"x1": x1, "y1": y1, "x2": x2, "y2": y2, "w": w, "h": h, "confidence": round(confidence, 2)})
    regions.sort(key=lambda r: -r["confidence"])
    return regions[:MAX_REGIONS]


def find_regions(data_url, phrase, blocked):
    """Returns {regions, demo_mode, demo_reason}. A phrase is a short noun phrase such as 'signature'."""
    vision.check_image(data_url)
    phrase = phrase.strip() if isinstance(phrase, str) else ""
    if not phrase or len(phrase) > MAX_PHRASE:
        raise ValueError(f"Describe what to cover in 1 to {MAX_PHRASE} characters, for example: signature.")
    reason = blocked()
    if reason:
        return {"regions": [], "demo_mode": True, "demo_reason": reason}
    call = muse.segment(phrase, data_url)
    if call["demo_mode"]:
        return {"regions": [], "demo_mode": True, "demo_reason": call["demo_reason"]}
    return {"regions": parse_regions(call["text"]), "demo_mode": False, "demo_reason": None}
