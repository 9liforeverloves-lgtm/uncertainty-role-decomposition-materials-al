from pathlib import Path
import hashlib
import json
import re

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "manuscript_v5" / "manuscript_acquisition_transportability_v5.tex"
SUPP = ROOT / "manuscript_v5" / "supplement_acquisition_transportability_v5.tex"


def manuscript_text():
    return MAIN.read_text(encoding="utf-8") + "\n" + SUPP.read_text(encoding="utf-8")


def test_final_claim_matrix_has_required_supported_claims_and_lock_chain():
    claims = pd.read_csv(ROOT / "09_claim_evidence_matrix.csv")
    required = {f"C{i:02d}" for i in range(1, 16)}
    assert required <= set(claims["claim_id"])
    assert not (claims["status"] == "not_supported").any()
    for column in [
        "final_table_lock_hash",
        "result_lock_hash",
        "trajectory_content_tree_hash",
        "selected_policy_lock_hash",
    ]:
        assert claims[column].str.fullmatch(r"[0-9a-f]{64}").all()


def test_final_number_traceability_is_complete_for_required_sentence_ids():
    trace = pd.read_csv(ROOT / "10_number_traceability.csv")
    required = {
        "M-DESIGN-01",
        "M-INF-01",
        "M-INF-02",
        "M-INF-03",
        "M-L4-01",
        "M-COMP-01",
        "M-RESULT-OGG-L1",
        "M-RESULT-OGG-L4",
        "M-RESULT-HCS-L4",
        "M-RESULT-SGG-L4",
        "M-RESULT-SCS-L4",
        "M-REC-01",
        "M-REC-02",
        "M-REC-03",
        "M-PROV-01",
    }
    assert required <= set(trace["sentence_id"])
    assert len(trace) >= 70
    assert trace["source_final_table"].notna().all()
    assert trace["row_filter"].notna().all()
    for column in [
        "final_table_lock_hash",
        "result_lock_hash",
        "trajectory_content_tree_hash",
        "selected_policy_lock_hash",
    ]:
        assert trace[column].str.fullmatch(r"[0-9a-f]{64}").all()


def test_manuscript_uses_locked_log_kvrh_selected_raw_beta_2():
    text = manuscript_text()
    assert "log KVRH" in text
    assert "Raw UCB $\\beta=2$" in text
    assert "only log kvrh uses raw ucb $\\beta=2$" in text.lower()


def test_manuscript_does_not_make_forbidden_scientific_claims():
    text = re.sub(r"\s+", " ", manuscript_text().lower())
    forbidden = [
        "raw beta 1 universally dominates",
        "all recovery effect magnitudes were robust",
        "was externally preregistered",
        "an external preregistration was",
        "failure was caused by i/o",
        "recovery failure was caused by i/o",
        "causal mediation effect",
    ]
    assert not any(phrase in text for phrase in forbidden)
    assert "no universal" in text
    assert (
        "strict relative magnitude robustness was not universal" in text
        or "strict magnitude robustness was not universal" in text
    )


def test_manuscript_references_only_final_v2_figures_and_final_tables():
    text = manuscript_text()
    figure_refs = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", text)
    assert figure_refs
    assert all("figures_v5/final_v2/" in ref for ref in figure_refs)
    forbidden = ("INVALID_ANALYSIS", "UNCORRECTED_ARCHIVE", "SUPERSEDED")
    assert not any(token in text for token in forbidden)


def test_final_table_lock_still_matches_all_locked_tables():
    lock_path = ROOT / "tables_v5" / "FINAL_TABLE_LOCK_V5.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    for item in lock["files"]:
        path = ROOT / item["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
