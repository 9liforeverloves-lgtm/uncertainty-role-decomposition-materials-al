#!/usr/bin/env python3
"""Create labeled contact sheets from rendered PDF page PNGs."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "logs_v5" / "pdf_review"


def build(name, columns=3, thumb_width=500):
    paths = sorted((BASE / name).glob("page-*.png"))
    thumbs = []
    font = ImageFont.load_default()
    for page_number, path in enumerate(paths, 1):
        image = Image.open(path).convert("RGB")
        height = round(image.height * thumb_width / image.width)
        image = image.resize((thumb_width, height))
        canvas = Image.new("RGB", (thumb_width, height + 28), "white")
        canvas.paste(image, (0, 28))
        ImageDraw.Draw(canvas).text((8, 7), f"{name} page {page_number}", fill="black", font=font)
        thumbs.append(canvas)
    rows = (len(thumbs) + columns - 1) // columns
    cell_height = max(image.height for image in thumbs)
    sheet = Image.new("RGB", (columns * thumb_width, rows * cell_height), "#dddddd")
    for index, image in enumerate(thumbs):
        x = (index % columns) * thumb_width
        y = (index // columns) * cell_height
        sheet.paste(image, (x, y))
    output = BASE / f"{name}_contact_sheet.png"
    sheet.save(output)
    return output


if __name__ == "__main__":
    print(build("main"))
    print(build("supplement"))
