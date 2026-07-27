$ErrorActionPreference = 'Stop'
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$dir = Join-Path $root 'manuscript_v5\submission_candidate_v4_final'
$pdflatex = 'C:\Users\ROG\AppData\Local\Programs\MiKTeX\miktex\bin\x64\pdflatex.exe'
$bibtex = 'C:\Users\ROG\AppData\Local\Programs\MiKTeX\miktex\bin\x64\bibtex.exe'

Push-Location $dir
try {
    & $pdflatex -interaction=nonstopmode -halt-on-error manuscript_submission_candidate_v4_final.tex
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $bibtex manuscript_submission_candidate_v4_final
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $pdflatex -interaction=nonstopmode -halt-on-error manuscript_submission_candidate_v4_final.tex
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $pdflatex -interaction=nonstopmode -halt-on-error manuscript_submission_candidate_v4_final.tex
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & $pdflatex -interaction=nonstopmode -halt-on-error supplement_submission_candidate_v4_final.tex
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $bibtex supplement_submission_candidate_v4_final
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $pdflatex -interaction=nonstopmode -halt-on-error supplement_submission_candidate_v4_final.tex
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $pdflatex -interaction=nonstopmode -halt-on-error supplement_submission_candidate_v4_final.tex
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}
