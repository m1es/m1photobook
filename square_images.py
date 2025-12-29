#!/usr/bin/env python3

import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import piexif

# Optional GPS → city
try:
    from geopy.geocoders import Nominatim
    geolocator = Nominatim(user_agent="photo_book")
except ImportError:
    geolocator = None

# ==================================================
# Configuration
# ==================================================

INPUT_DIR  = "images_raw"
OUTPUT_DIR = "images"

OUTPUT_SIZE = 2048        # 🔑 FIXED FINAL SIZE (all typography is based on this)

BLUR_RADIUS = 60

TEXT_SIZE   = 72 # FIXED, never changes
TEXT_MARGIN = 24
TEXT_COLOR  = (255, 255, 255, 230)
MAX_TEXT_WIDTH_RATIO = 0.7

FONT_PATH = "/System/Library/Fonts/Menlo.ttc"
# Linux alternative:
# FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"

MONTHS_NL = {
    1: "jan", 2: "feb", 3: "mrt", 4: "apr",
    5: "mei", 6: "jun", 7: "jul", 8: "aug",
    9: "sep", 10: "okt", 11: "nov", 12: "dec"
}

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Load font ONCE (important for consistency)
FONT = ImageFont.truetype(FONT_PATH, TEXT_SIZE)

# ==================================================
# Helpers
# ==================================================

def exif_date(exif):
    try:
        raw = exif["Exif"][piexif.ExifIFD.DateTimeOriginal].decode()
        dt = datetime.strptime(raw, "%Y:%m:%d %H:%M:%S")
        return f"{dt.day} {MONTHS_NL[dt.month]}"
    except Exception:
        return None

def dms_to_deg(dms, ref):
    deg = dms[0][0] / dms[0][1]
    min = dms[1][0] / dms[1][1]
    sec = dms[2][0] / dms[2][1]
    value = deg + min / 60 + sec / 3600
    return -value if ref in [b"S", b"W"] else value

def exif_city(exif):
    if geolocator is None:
        return None

    try:
        gps = exif["GPS"]
        lat = dms_to_deg(
            gps[piexif.GPSIFD.GPSLatitude],
            gps[piexif.GPSIFD.GPSLatitudeRef]
        )
        lon = dms_to_deg(
            gps[piexif.GPSIFD.GPSLongitude],
            gps[piexif.GPSIFD.GPSLongitudeRef]
        )

        location = geolocator.reverse((lat, lon), language="nl", zoom=10)
        if location and "address" in location.raw:
            addr = location.raw["address"]
            return addr.get("city") or addr.get("town") or addr.get("village")
    except Exception:
        pass

    return None

def clamp_city(draw, date, city, max_width):
    """
    Keep date intact.
    Trim city ONLY if needed.
    Font size never changes.
    """
    base = f"{date} — {city}"
    if draw.textlength(base, font=FONT) <= max_width:
        return base

    ellipsis = "…"
    trimmed = city

    while len(trimmed) > 1:
        trimmed = trimmed[:-1]
        candidate = f"{date} — {trimmed}{ellipsis}"
        if draw.textlength(candidate, font=FONT) <= max_width:
            return candidate

    return date  # last resort

# ==================================================
# Main processing
# ==================================================

def process_image(filename):
    print(f"Processing {filename}")

    img = Image.open(os.path.join(INPUT_DIR, filename)).convert("RGB")
    w, h = img.size
    square_size = max(w, h)

    # --- Build square background at source resolution ---
    bg = img.resize((square_size, square_size), Image.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(BLUR_RADIUS))
    bg.paste(img, ((square_size - w) // 2, (square_size - h) // 2))

    # 🔑 Normalize to FINAL output size BEFORE drawing text
    bg = bg.resize((OUTPUT_SIZE, OUTPUT_SIZE), Image.LANCZOS)

    # --- EXIF label ---
    label = None
    try:
        exif = piexif.load(img.info.get("exif", b""))
        date = exif_date(exif)
        city = exif_city(exif)

        if date and city:
            label = (date, city)
        elif date:
            label = (date, None)
    except Exception:
        pass

    # --- Draw label (now perfectly consistent) ---
    if label:
        draw = ImageDraw.Draw(bg)
        max_width = int(OUTPUT_SIZE * MAX_TEXT_WIDTH_RATIO)

        if label[1]:
            text = clamp_city(draw, label[0], label[1], max_width)
        else:
            text = label[0]

        ascent, descent = FONT.getmetrics()
        text_width = draw.textlength(text, font=FONT)
        text_height = ascent + descent

        draw.text(
            (
                OUTPUT_SIZE - text_width - TEXT_MARGIN,
                OUTPUT_SIZE - text_height - TEXT_MARGIN
            ),
            text,
            font=FONT,
            fill=TEXT_COLOR
        )

    bg.save(os.path.join(OUTPUT_DIR, filename), quality=95)

# ==================================================
# Run
# ==================================================

def main():
    files = sorted(
        f for f in os.listdir(INPUT_DIR)
        if f.lower().endswith(".jpg")
    )
    for f in files:
        process_image(f)

if __name__ == "__main__":
    main()


