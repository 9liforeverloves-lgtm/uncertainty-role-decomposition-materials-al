from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


root = Path(__file__).resolve().parents[2]
review = root / "reviewer_revision_v4" / "final_r1"


def make_set(source: Path, prefix: str, out_prefix: str, per_sheet: int = 8):
    files = sorted(source.glob(f"{prefix}-*.png"))
    font = ImageFont.load_default()
    for sheet_index in range(0, len(files), per_sheet):
        chunk = files[sheet_index : sheet_index + per_sheet]
        thumb_w = 500
        prepared = []
        for path in chunk:
            image = Image.open(path).convert("RGB")
            ratio = thumb_w / image.width
            thumb = image.resize((thumb_w, int(image.height * ratio)))
            prepared.append((path, thumb))
        cell_h = max(item.height for _, item in prepared) + 32
        cols = 2
        rows = (len(prepared) + cols - 1) // cols
        canvas = Image.new("RGB", (cols * thumb_w, rows * cell_h), "white")
        draw = ImageDraw.Draw(canvas)
        for index, (path, thumb) in enumerate(prepared):
            x = (index % cols) * thumb_w
            y = (index // cols) * cell_h
            canvas.paste(thumb, (x, y + 24))
            draw.text((x + 6, y + 6), path.stem, fill="black", font=font)
        out = review / f"{out_prefix}_{sheet_index // per_sheet + 1}.png"
        canvas.save(out, dpi=(200, 200))
        print(out)


make_set(review / "rendered_pdf_pages", "main", "contact_current_main")
make_set(review / "rendered_pdf_pages", "supp", "contact_current_supp")
make_set(review / "rendered_prior_v4_final", "main", "contact_prior_main")
make_set(review / "rendered_prior_v4_final", "supp", "contact_prior_supp")
