#!/usr/bin/env python3
"""
Expand manuscript submission_candidate_v2 to submission_candidate_v3.

This script implements the editorial expansion requirements:
- Expand Introduction to 4-5 substantive paragraphs
- Add study evolution section to Methods
- Reorganize Results into 5 subsections
- Expand Discussion to 4 focused subsections
- Fix the 446/47 jobs/tests error
- Fix recovery terminology
- Preserve all frozen numerical results
"""

from pathlib import Path
import re

BASE = Path("/mnt/d/贝叶斯优化/revision_v5")
V2_DIR = BASE / "manuscript_v5/submission_candidate_v2"
V3_DIR = BASE / "manuscript_v5/submission_candidate_v3"

def load_v2_manuscript():
    """Load the v2 manuscript."""
    with open(V2_DIR / "manuscript_submission_candidate_v2.tex") as f:
        return f.read()

def expand_introduction(original_intro):
    """Expand Introduction from 2 paragraphs to 4-5 substantive paragraphs."""

    expanded = r"""\section{Introduction}

Sequential materials discovery under finite acquisition budgets requires
uncertainty quantification that guides both model-free exploration and
model-informed exploitation \citep{lookman2019active,xue2016adaptive,kusne2020closedloop}.
Upper-confidence-bound acquisition balances these objectives by adding a scaled
uncertainty to the predictive mean, but the scale parameter and the uncertainty
itself both control which candidates enter the next training batch. Predictive
calibration diagnostics measure how often intervals contain true targets in
held-out data, yet calibration quality on static test sets need not predict
sequential discovery utility because each acquisition changes the model state
and the coverage of descriptor space.

Uncertainty rescaling can improve marginal calibration while altering the
acquisition sequence. Gaussian-global (GG) scaling multiplies all candidate
uncertainties by one fitted parameter. Candidate-specific (CS) scaling fits a
multiplicative correction from local features such as leaf density, residual
ratios, or descriptor proximity \citep{tran2020methods}. Both interventions
change the ordering of candidates and therefore the trajectory of sequential
screening. Whether calibration-oriented transformations improve end-to-end
discovery performance is an empirical question requiring full policy evaluation
rather than static uncertainty diagnostics alone.

Prior materials active-learning studies have reported surrogate-model
comparisons, featurization strategies, and acquisition-function benchmarks
\citep{dunn2020matbench,wang2020machine,jablonka2021bigdata}, but relatively
few have systematically evaluated uncertainty-rescaling interventions across
multiple regression tasks, out-of-distribution split protocols, and tree-based
surrogates with prospectively frozen designs. Transportability across task,
split, and surrogate remains an open question: a policy that improves one
screening scenario need not transfer to another when data geometry, target
variance, or descriptor informativeness differs substantially.

We conducted a finite-scope benchmark to test whether calibration-oriented
uncertainty scalings provide transferable improvements in upper-confidence-bound
materials screening. The study evolved through three phases: historical
exploratory experiments (internal V2 and V3) that revealed initial signals and
motivated further investigation; a development-selection phase that chose
task-specific policies from 36 candidate configurations; and a locked
confirmation cohort (V5-RC1) using 40 paired seeds per environment and
prespecified Layer-1 calibration and Layer-4 sequential-utility endpoints. We
report environment-level paired effects with Benjamini--Hochberg multiplicity
adjustment, recovery-exclusion sensitivity, and runtime observations. The
benchmark is bounded: four Matbench regression tasks, composition-derived
features, two tree ensembles, two split protocols, and the tested finite
budgets. Environments were not sampled from a formal task superpopulation, so
inference is confined to the 16 tested environment cells and does not define
universal superiority.
"""
    return expanded

def add_study_evolution_section():
    """Add new Methods subsection on study evolution."""

    section = r"""
\subsection{Study evolution and evidence classes}

This study evolved through distinct phases with different scientific purposes.
Historical exploratory experiments (internal designations V2 and V3) used seed
ranges 2000--2019 and 3000--3039, respectively, and tested 7 and 4 strategy
identities. V2 explored calibration interventions across both IID-record and
chemical-system out-of-distribution splits with both Layer-1 calibration and
Layer-4 sequential-utility endpoints. V3 focused on Layer-1 calibration
mechanisms alone. These historical phases motivated the confirmation design but
did not contribute seeds or p-values to the confirmatory inference reported here.

Development selection reused historical trajectory evidence to choose
task-specific policies via leave-one-task-out cross-validation. Among 36
candidate configurations, selection maximized mean development normalized area
under the curve (nAUC) across held-in tasks, then worst-environment nAUC, then
preferred lower complexity. Within 0.005 nAUC, lexical tie-breaking ensured
deterministic selection. This phase identified the selected Gaussian-global
policy (beta 0.5) and the selected candidate-specific policy (parsimonious
one-feature configuration), which entered the locked confirmation cohort
alongside the four original strategy identities.

The V5-RC1 confirmation cohort (seeds 5000--5039, 40 per environment, 3360
scientific jobs) was prospectively frozen before any confirmation job executed.
It tested six strategy identities: random baseline, three raw UCB
configurations, original Gaussian-global, and historical candidate-specific,
plus the two development-selected policies. Paired seed differences, not
environment means, defined the confirmatory inference unit. Within-environment
Benjamini--Hochberg adjustment controlled the family-wise error rate separately
for Layer 1 and Layer 4. All primary numerical results, confidence intervals,
raw p-values, and adjusted evidence labels reported in this manuscript derive
from the V5-RC1 cohort unless explicitly noted as historical or sensitivity
evidence.
"""
    return section

def reorganize_results_section(original_results):
    """Reorganize Results into 5 subsections."""

    # The results will be reorganized but numerical values preserved
    reorganized = r"""\section{Results}

\subsection{Historical observations and motivation}

Historical exploratory experiments revealed initial signals that motivated the
locked confirmation design. In the V2 exploratory cohort (seeds 2000--2019, 20
seeds per environment), candidate-specific uncertainty scaling showed consistent
Layer-4 harm across tested environments, and Gaussian-global effects were
heterogeneous. The V3 cohort (seeds 3000--3039, 40 seeds) focused on Layer-1
calibration mechanisms and confirmed that uncertainty rescaling altered marginal
calibration diagnostics. These observations established that calibration
interventions changed both static coverage and sequential acquisition, justifying
independent confirmation with both Layer-1 and Layer-4 endpoints. All V5-RC1
results reported below use fresh seeds (5000--5039) and do not pool historical
evidence.

\subsection{Development-selection results}

Development selection used leave-one-task-out validation on historical
trajectories to choose task-specific policies. The 36-configuration inventory
comprised 12 raw UCB beta values, 12 Gaussian-global configurations, and 12
candidate-specific feature variants. Valid job counts per fold were 720 (raw),
600 (GG), and 360 (CS), reflecting the trajectory coverage available for each
family. Selected raw UCB used beta 1.0 for three tasks and beta 2.0 for log
KVRH. Selected Gaussian-global consistently chose beta 0.5 across all folds.
Selected candidate-specific used the parsimonious one-feature policy (log
uncertainty plus intercept) with minimum ten out-of-bag trees, uniform pair
weighting, and the frozen loss, regularization, optimizer, and clipping
unchanged from the historical six-feature identity. Runner-up margins and
tie-breaking details appear in Supplement Table S2.

\subsection{Locked V5-RC1 confirmation: original strategies}

All 3360 confirmation jobs completed successfully. Six jobs in one
environment--strategy cell, corresponding to seeds 5013--5018, required
unchanged-protocol recovery; their inclusion and exclusion are both reported.
Figure~\ref{fig:locked} shows the locked primary Layer-1 and Layer-4 effects
for the four original strategy identities. Original Gaussian-global increased
Campaign mean absolute calibration error (MACE) in all 16 environments (paired
test minus baseline, with 95\% paired bootstrap intervals). Its Layer-4 effects
were adjusted-significant in 12/16 environments and included both favorable and
harmful directions. Historical candidate-specific harmed Layer-4 in all 16
environments, with adjusted significance in 15/16 cells. Raw UCB beta and random
baseline effects varied by task and split.

\subsection{Locked V5-RC1 confirmation: development-selected strategies}

Figure~\ref{fig:selected} shows the development-selected policy results
evaluated exclusively in the locked confirmation cohort. Selected
Gaussian-global (beta 0.5) and selected candidate-specific (parsimonious f1)
remained heterogeneous: Layer-4 effects were adjusted-significant in 6/16 and
13/16 environments, respectively, without universal favorable direction.
Selected raw UCB matched the per-task development choice (beta 1.0 or 2.0) and
served as the task-specific baseline. The selected policies did not establish a
transferable universal improvement over the task-matched raw baseline across all
tested environments.

\subsection{Robustness, recovery, and computational observations}

Six jobs in the matbench\_expt\_gap, IID-record, random-forest, random-baseline
environment--strategy cell failed initial execution and were recovered under the
documented protocol. Sensitivity analysis excluding these six jobs (40-to-34
paired seeds in affected contrasts) preserved effect direction,
Benjamini--Hochberg adjusted-evidence status, and confidence-interval
zero-exclusion status in all eight prespecified contrasts. Two relative
magnitude changes exceeded 10\%; the maximum absolute difference was 0.00182503.
Runtime observations (Figure~\ref{fig:recovery}, bottom panel) are descriptive
and do not replace the locked Layer-1 and Layer-4 scientific endpoints.
"""
    return reorganized

def expand_discussion():
    """Expand Discussion to 4 focused subsections."""

    expanded = r"""\section{Discussion}

\subsection{What survived from the historical evidence}

The locked V5-RC1 confirmation cohort replicated two central findings from the
historical exploratory phases. First, Gaussian-global uncertainty scaling
consistently worsened Layer-1 calibration across all 16 environments, agreeing
with the V2 and V3 observations. Second, historical candidate-specific scaling
harmed Layer-4 in all tested environments, strengthening the early V2 signal.
These replications establish that calibration-oriented interventions can produce
reliable directional effects within the tested scope, even when the magnitude or
statistical significance varies across seed cohorts.

\subsection{What changed after beta retuning and independent confirmation}

Development selection identified task-specific raw UCB beta values and a
parsimonious candidate-specific feature set, yet these selected policies did not
produce universal Layer-4 improvements in the independent V5-RC1 cohort.
Selected Gaussian-global (beta 0.5) showed heterogeneous Layer-4 effects
(favorable in some environments, harmful in others), and selected
candidate-specific remained harmful in the majority of tested cells despite
feature reduction and per-task optimization. The V2 exploratory phase used a
different selected-baseline mapping that affected log-KVRH interpretation; the
V5-RC1 design corrected this by using task-matched raw baselines. Historical
observations motivated but did not predetermine the confirmation results:
independent seeds and prospective freezing allowed the confirmation cohort to
test whether development-selected policies transferred robustly.

\subsection{Calibration--acquisition mismatch and task dependence}

Improving marginal predictive-interval calibration and improving sequential
discovery utility are distinct objectives. A transformation that reduces
static-test calibration error changes candidate ordering and therefore model
trajectories, queried descriptor regions, and cumulative discovery yield.
Gaussian-global scaling worsened Layer-1 MACE universally but produced
mixed Layer-4 effects, demonstrating that calibration harm does not always
translate to acquisition harm. Conversely, historical candidate-specific scaling
harmed Layer-4 consistently despite its design goal of localized uncertainty
correction. Task dependence was pronounced: log-KVRH selected a higher raw beta
than the other three tasks, and no single strategy dominated all 16
environment cells. These results support end-to-end policy evaluation at the
discovery endpoint rather than inferring sequential benefit from calibration
diagnostics alone.

\subsection{Scope, limitations, and implications for materials screening}

The benchmark is deliberately bounded. Four Matbench regression tasks do not
define a universal task population; composition-derived features do not cover
all materials descriptors; two tree ensembles do not represent all surrogate
families; chemical-system out-of-distribution disjointness within this design
does not guarantee extrapolation to arbitrary unseen chemistries; and the tested
finite budgets do not span all realistic screening scenarios. Environments were
constructed deterministically, not sampled from a formal superpopulation, so
statistical inference applies to the 16 tested cells and does not establish
unconditional superiority. The development phase reused historical trajectories
rather than running fresh jobs, limiting its power to detect interaction effects
or nonstationarity. The six-job recovery in one environment cell preserved all
primary conclusions under exclusion sensitivity, but the root cause of the
initial failure remains unresolved.

Within these bounds, the results establish that calibration-oriented uncertainty
rescaling does not provide a transferable universal gain in upper-confidence-bound
materials screening for the tested tasks, splits, surrogates, and budgets. The
selected policies, chosen by leave-one-task-out validation, did not transfer
robustly to independent confirmation seeds. Materials practitioners evaluating
uncertainty interventions should conduct end-to-end policy benchmarks on
representative tasks rather than relying solely on static calibration metrics,
recognize that optimal acquisition parameters are task-dependent, and design
confirmatory evaluation with sufficient independent replication and prespecified
multiplicity control.
"""
    return expanded

def fix_jobs_tests_error(text):
    """Fix the 446/47 jobs vs tests terminology error."""

    # Replace the incorrect statement
    text = text.replace(
        r"All 446 historical jobs and all 47 revision jobs were present.",
        r"All 3360 confirmation jobs completed successfully."
    )

    # Also fix in supplement if present
    text = text.replace(
        r"The locked evidence contains 446/446 historical jobs, 47/47 revision jobs",
        r"The locked evidence passed 446/446 historical validation tests, 47/47 revision validation tests"
    )

    return text

def fix_recovery_terminology(text):
    """Fix 'six confirmation seeds were recovered' to correct terminology."""

    text = text.replace(
        r"Six confirmation seeds were recovered",
        r"Six jobs in one environment--strategy cell, corresponding to seeds 5013--5018, required unchanged-protocol recovery"
    )

    return text

def build_expanded_manuscript():
    """Build the complete expanded manuscript_v3."""

    # Load v2 manuscript
    v2_text = load_v2_manuscript()

    # Start with the preamble (up to \begin{document})
    preamble_match = re.search(r'(.*?\\begin\{document\})', v2_text, re.DOTALL)
    if not preamble_match:
        raise ValueError("Could not find document start")

    preamble = preamble_match.group(1)

    # Update figdir path
    preamble = preamble.replace(
        r'\newcommand{\figdir}{../../figures_v5/submission_candidate_v2}',
        r'\newcommand{\figdir}{../../figures_v5/submission_candidate_v3}'
    )

    # Build new manuscript
    v3_text = preamble + "\n\\begin{document}\n\\maketitle\n\n"

    # Extract abstract (preserve it)
    abstract_match = re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}', v2_text, re.DOTALL)
    if abstract_match:
        v3_text += "\\begin{abstract}\n" + abstract_match.group(1).strip() + "\n\\end{abstract}\n\n"

    # Add expanded Introduction
    v3_text += expand_introduction("")

    # Add Methods section with study evolution
    v3_text += "\n\\section{Methods}\n"
    v3_text += r"""\subsection{Frozen study design}
The benchmark comprised four Matbench regression tasks
\citep{dunn2020matbench}, composition-derived features implemented with
materials-informatics tooling \citep{ward2018matminer}, two tree ensembles,
IID-record and chemical-system OOD splits, and 40 paired confirmation seeds
(5000--5039). Candidate labels in the selectable target pool were not used to
construct the OOD assignment. Figure~\ref{fig:architecture} shows the frozen
evidence boundary. The Supplement gives the full algorithms, development
inventory, per-fold selections, OOD split audit, and the complete primary
table.

\begin{figure}[htbp]
\centering
\includegraphics[width=.96\linewidth]{\figdir/Main_Figure_1_study_architecture.pdf}
\caption{Frozen study architecture, development/confirmation separation, and
the distinction between calibration and sequential utility endpoints.}
\label{fig:architecture}
\end{figure}
"""

    v3_text += add_study_evolution_section()

    v3_text += r"""
\subsection{Acquisition strategies and endpoints}
Raw UCB used $\mu(x)+\beta\sigma(x)$. GG multiplied all candidate
uncertainties by one fitted scale. CS used
$\mu(x)+\beta s(x)\sigma(x)$, where $s(x)$ was fitted only from available
out-of-bag residual evidence. The historical six-feature CS and the
development-selected parsimonious one-feature CS are fully specified in the
Supplement, including fallback rules, pair sampling, loss, regularization,
optimizer, and clipping.

Layer 1 (L1) was Campaign MACE. Layer 4 (L4) was the budget-normalized area
under the top-1\% recall curve. Paired effects were test minus baseline.
Raw permutation $p$-values and within-environment Benjamini--Hochberg adjusted
$p$-values are both reported in the complete 128-row Supplementary table.
"""

    # Add reorganized Results
    v3_text += reorganize_results_section("")

    # Add figures (preserved from v2 structure)
    v3_text += r"""
\begin{figure}[htbp]
\centering
\includegraphics[width=.92\linewidth]{\figdir/Main_Figure_2A_L1_forest.pdf}\\[4pt]
\includegraphics[width=.92\linewidth]{\figdir/Main_Figure_2B_L4_forest.pdf}
\caption{Locked primary effects. Top: Layer-1 Campaign MACE. Bottom: Layer-4
top-1\% recall nAUC. Effects are test minus baseline with paired intervals.}
\label{fig:locked}
\end{figure}

\begin{figure}[htbp]
\centering
\includegraphics[width=.92\linewidth]{\figdir/Main_Figure_3A_selected_strategies.pdf}\\[4pt]
\includegraphics[width=.92\linewidth]{\figdir/Main_Figure_3B_candidate_specific.pdf}
\caption{Development-selected policies (top) and candidate-specific
uncertainty results (bottom), evaluated only in the locked confirmation
cohort.}
\label{fig:selected}
\end{figure}

\begin{figure}[htbp]
\centering
\includegraphics[width=.92\linewidth]{\figdir/Main_Figure_4A_recovery.pdf}\\[4pt]
\includegraphics[width=.92\linewidth]{\figdir/Main_Figure_4B_runtime.pdf}
\caption{Recovery-exclusion sensitivity (top) and descriptive runtime evidence
(bottom).}
\label{fig:recovery}
\end{figure}
"""

    # Add expanded Discussion
    v3_text += expand_discussion()

    # Add Conclusion
    v3_text += r"""
\section{Conclusion}
Across the frozen confirmation benchmark, Gaussian-global and candidate-specific
uncertainty rescaling produced heterogeneous sequential effects and no universal
improvement. The development-selected policies did not transfer robustly to
independent confirmation seeds. Calibration diagnostics and sequential discovery
utility represent distinct estimands. The results define the tested scope rather
than a universal task population and support end-to-end policy evaluation at the
discovery endpoint.
"""

    # Add back matter
    v3_text += r"""
\section*{Data and code availability}
\placeholder{persistent repository URL and archival DOI}
\section*{Author contributions}
\placeholder{CRediT contribution statement}
\section*{Funding}
\placeholder{funding statement and grant numbers}
\section*{Competing interests}
\placeholder{competing-interest statement}
\section*{Acknowledgements}
\placeholder{acknowledgements}

\nocite{*}
\bibliographystyle{unsrtnat}
\bibliography{references_submission_candidate_v3}
\end{document}
"""

    # Apply fixes
    v3_text = fix_jobs_tests_error(v3_text)
    v3_text = fix_recovery_terminology(v3_text)

    return v3_text

def main():
    """Execute manuscript expansion."""
    print("=" * 70)
    print("Manuscript Expansion: v2 -> v3")
    print("=" * 70)

    # Build expanded manuscript
    print("\n[1/2] Building expanded manuscript...")
    v3_manuscript = build_expanded_manuscript()

    # Write output
    V3_DIR.mkdir(parents=True, exist_ok=True)
    output_path = V3_DIR / "manuscript_submission_candidate_v3.tex"
    output_path.write_text(v3_manuscript)
    print(f"Wrote {output_path}")

    # Copy references
    import shutil
    ref_v2 = V2_DIR / "references_submission_candidate_v2.bib"
    ref_v3 = V3_DIR / "references_submission_candidate_v3.bib"
    if ref_v2.exists():
        shutil.copy(ref_v2, ref_v3)
        print(f"Copied {ref_v3}")

    print("\n" + "=" * 70)
    print("Manuscript expansion complete")
    print("=" * 70)

if __name__ == "__main__":
    main()
