#!/usr/bin/env python3
"""
Expand supplement submission_candidate_v2 to submission_candidate_v3.

Adds:
- Table S1: Study evolution and evidence classes
- Corrected terminology for tests vs jobs
- Enhanced evidence class descriptions
"""

from pathlib import Path
import re

BASE = Path("/mnt/d/贝叶斯优化/revision_v5")
V2_DIR = BASE / "manuscript_v5/submission_candidate_v2"
V3_DIR = BASE / "manuscript_v5/submission_candidate_v3"

def load_v2_supplement():
    """Load the v2 supplement."""
    with open(V2_DIR / "supplement_submission_candidate_v2.tex") as f:
        return f.read()

def build_study_evolution_table():
    """Build Table S1: Study evolution and evidence classes."""

    table = r"""\section{Study evolution and evidence classes}

Table~\ref{tab:study_evolution} documents the complete study evolution from
historical exploratory phases through locked confirmation to sensitivity
analysis.

\begin{table}[htbp]
\centering
\caption{Study evolution and evidence classes. Historical phases V2 and V3 used
different seed ranges and strategy sets from the V5-RC1 confirmation cohort.}
\label{tab:study_evolution}
\scriptsize
\begin{tabular}{@{}llllll@{}}
\toprule
\textbf{Phase} & \textbf{Seeds} & \textbf{Jobs} & \textbf{Strategies} & \textbf{Endpoints} & \textbf{Evidence class} \\
\midrule
Historical V2 & 2000--2019 & 1920 & 7 identities & L1, L4 & Exploratory \\
Historical V3 & 3000--3039 & 1920 & 4 identities & L1 only & Exploratory/mechanistic \\
Development & Reused & Post hoc & 36 configs & Dev nAUC & Development-selection \\
V5-RC1 & 5000--5039 & 3360 & 6 identities & L1, L4 & Confirmatory \\
Recovery sens. & 5000--5039 & 40$\to$34 & 8 contrasts & L1, L4 & Sensitivity \\
\bottomrule
\end{tabular}
\end{table}

\textbf{Historical V2}: Early exploration across 4 tasks, 2 splits, 2 surrogates,
with 20 seeds per environment. Tested raw UCB (4 beta values), Gaussian-global,
candidate-specific, and random baseline. Provided initial signal that CS harmed
Layer-4 and GG effects were heterogeneous.

\textbf{Historical V3}: Focused on Layer-1 calibration mechanisms with 40 seeds
per environment but only 4 strategy identities (raw beta 1.0, GG, CS, random).
Confirmed that uncertainty rescaling altered static calibration diagnostics.
Did not measure Layer-4 sequential utility.

\textbf{Development selection}: Post-hoc analysis on historical trajectories
using leave-one-task-out validation. Selected task-specific raw beta, GG beta
0.5, and parsimonious CS feature set. These selected identities entered V5-RC1
for independent confirmation.

\textbf{V5-RC1 confirmation}: Prospectively frozen before any job execution.
Fresh seed range 5000--5039, 40 seeds per environment, 3360 total jobs. Tested
6 frozen strategies including the 2 development-selected policies. Layer-1
(Campaign MACE) and Layer-4 (top-1\% recall nAUC) endpoints. Paired-seed
inference with within-environment Benjamini--Hochberg adjustment. All primary
manuscript results derive from this cohort unless explicitly noted otherwise.

\textbf{Recovery sensitivity}: Six jobs in one environment--strategy cell
(matbench\_expt\_gap, IID-record, random-forest, random baseline, seeds
5013--5018) required unchanged-protocol recovery. Sensitivity analysis excluded
these 6 jobs, reducing paired sample size from 40 to 34 in affected contrasts.
Preserved direction, adjusted-evidence status, and CI zero-exclusion in all 8
prespecified contrasts.
"""
    return table

def fix_validation_test_terminology(text):
    """Fix validation test vs scientific job terminology throughout supplement."""

    # Fix the main statement
    text = text.replace(
        r"The locked evidence contains 446/446 historical jobs, 47/47 revision jobs",
        r"The validation suite passed 446/446 historical reproducibility tests and 47/47 revision validation tests. The locked scientific cohort contained 3360 confirmation jobs"
    )

    # Add clarification
    clarification = r"""
\subsection{Validation tests vs scientific jobs}

The repository contains two distinct validation suites:

\begin{itemize}
\item \textbf{Historical validation suite}: 446 tests verifying that historical
V2/V3 result tables, hashes, manifests, and trajectories remain readable and
internally consistent. These are \emph{not} 446 additional scientific jobs.
\item \textbf{Revision validation suite}: 47 tests checking V5-RC1 protocol
freeze, manifest integrity, endpoint implementations, and analysis pipelines.
These are \emph{not} 47 additional scientific jobs.
\item \textbf{Scientific job count}: The V5-RC1 confirmation cohort comprised
3360 independent screening trajectories (4 tasks $\times$ 2 splits $\times$ 2
surrogates $\times$ 6 strategies $\times$ 40 seeds + 6 strategies $\times$ 2
selected-policy-only environments $\times$ 40 seeds).
\end{itemize}

Validation tests ensure computational reproducibility and data integrity; they
do not add to the scientific sample size.
"""

    # Insert after the first section
    text = text.replace(
        r"\section{Evidence boundary and frozen computation}",
        r"\section{Evidence boundary and frozen computation}" + "\n" + clarification
    )

    return text

def build_expanded_supplement():
    """Build the complete expanded supplement_v3."""

    # Load v2 supplement
    v2_text = load_v2_supplement()

    # Update figdir path
    v2_text = v2_text.replace(
        r'\newcommand{\figdir}{../../figures_v5/submission_candidate_v2}',
        r'\newcommand{\figdir}{../../figures_v5/submission_candidate_v3}'
    )

    # Fix validation terminology
    v2_text = fix_validation_test_terminology(v2_text)

    # Insert study evolution table after table of contents
    toc_pos = v2_text.find(r'\tableofcontents')
    if toc_pos > 0:
        insert_pos = v2_text.find(r'\section{', toc_pos)
        if insert_pos > 0:
            v2_text = (v2_text[:insert_pos] +
                      build_study_evolution_table() + "\n\n" +
                      v2_text[insert_pos:])

    # Fix recovery terminology
    v2_text = v2_text.replace(
        "Six confirmation seeds were recovered",
        "Six jobs in one environment--strategy cell, corresponding to seeds 5013--5018, required unchanged-protocol recovery"
    )

    return v2_text

def main():
    """Execute supplement expansion."""
    print("=" * 70)
    print("Supplement Expansion: v2 -> v3")
    print("=" * 70)

    # Build expanded supplement
    print("\n[1/1] Building expanded supplement...")
    v3_supplement = build_expanded_supplement()

    # Write output
    V3_DIR.mkdir(parents=True, exist_ok=True)
    output_path = V3_DIR / "supplement_submission_candidate_v3.tex"
    output_path.write_text(v3_supplement)
    print(f"Wrote {output_path}")

    # Copy tables directory if exists
    import shutil
    tables_v2 = V2_DIR / "tables"
    tables_v3 = V3_DIR / "tables"
    if tables_v2.exists() and not tables_v3.exists():
        shutil.copytree(tables_v2, tables_v3)
        print(f"Copied tables directory to {tables_v3}")

    print("\n" + "=" * 70)
    print("Supplement expansion complete")
    print("=" * 70)

if __name__ == "__main__":
    main()
