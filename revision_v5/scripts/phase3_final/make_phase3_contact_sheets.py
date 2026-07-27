from pathlib import Path
from PIL import Image, ImageDraw

directory = Path(r"D:\贝叶斯优化\revision_v5\reviewer_revision_v4\phase3\rendered_pdf_pages")
pages = sorted(directory.glob("main-*.png")) + sorted(directory.glob("supp-*.png"))
sheet_dir = directory / "contact_sheets"
sheet_dir.mkdir(exist_ok=True)

for start in range(0, len(pages), 4):
    group = pages[start:start + 4]
    thumbs = []
    for page in group:
        image = Image.open(page).convert("RGB")
        image.thumbnail((700, 920))
        canvas = Image.new("RGB", (720, 970), "white")
        canvas.paste(image, ((720 - image.width) // 2, 30))
        ImageDraw.Draw(canvas).text((20, 8), page.stem, fill="black")
        thumbs.append(canvas)
    sheet = Image.new("RGB", (1440, 1940), "#d9dde2")
    for index, image in enumerate(thumbs):
        sheet.paste(image, ((index % 2) * 720, (index // 2) * 970))
    path = sheet_dir / f"contact_{start // 4 + 1:02d}.png"
    sheet.save(path)
    print(path)
