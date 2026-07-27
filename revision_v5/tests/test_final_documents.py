from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MANUSCRIPT = ROOT / "manuscript_v5"


def test_final_pdf_and_docx_deliverables_exist_and_are_nonempty():
    for name in [
        "manuscript_acquisition_transportability_v5_final.pdf",
        "supplement_acquisition_transportability_v5_final.pdf",
        "manuscript_acquisition_transportability_v5_final.docx",
        "supplement_acquisition_transportability_v5_final.docx",
    ]:
        path = MANUSCRIPT / name
        assert path.is_file()
        assert path.stat().st_size > 10_000


def test_final_pdf_page_render_inventory_is_complete():
    review = ROOT / "logs_v5" / "pdf_review"
    assert len(list((review / "main").glob("page-*.png"))) == 12
    assert len(list((review / "supplement").glob("page-*.png"))) == 8


def test_final_latex_logs_have_no_layout_or_reference_warnings():
    for name in [
        "manuscript_acquisition_transportability_v5_final.log",
        "supplement_acquisition_transportability_v5_final.log",
    ]:
        text = (MANUSCRIPT / name).read_text(encoding="utf-8", errors="replace")
        forbidden = ("Overfull", "Undefined", "undefined", "LaTeX Warning", "! LaTeX Error")
        assert not any(token in text for token in forbidden)


def test_main_manuscript_includes_all_nine_final_v2_figures_once():
    text = (
        MANUSCRIPT / "manuscript_acquisition_transportability_v5.tex"
    ).read_text(encoding="utf-8")
    refs = re.findall(r"final_v2/(Figure\d+_[^}]+)\.pdf", text)
    assert len(refs) == 9
    assert len(set(refs)) == 9


def test_only_administrative_submission_placeholders_remain():
    text = (
        MANUSCRIPT / "manuscript_acquisition_transportability_v5.tex"
    ).read_text(encoding="utf-8")
    assert "AUTHOR INPUT REQUIRED" in text
    assert "sensitivity pending" not in text.lower()
    assert "conditional L4 pass" not in text
    assert "21 Strategies" not in text
    required = (
        MANUSCRIPT / "REQUIRED_AUTHOR_INPUTS.md"
    ).read_text(encoding="utf-8")
    for field in ["Author names", "Affiliations", "CRediT", "Funding", "Data license", "Target journal"]:
        assert field.lower() in required.lower()
