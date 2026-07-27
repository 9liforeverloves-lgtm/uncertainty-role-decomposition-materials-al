$ErrorActionPreference = 'Continue'

$project = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$manuscriptDir = Join-Path $project 'manuscript_v5\submission_candidate_v4_final_r1'
$logDir = Join-Path $project 'logs_v5\reviewer_revision_v4\final_r1'
$miktexBin = 'C:\Users\ROG\AppData\Local\Programs\MiKTeX\miktex\bin\x64'
$pdflatex = Join-Path $miktexBin 'pdflatex.exe'
$bibtex = Join-Path $miktexBin 'bibtex.exe'

New-Item -ItemType Directory -Force -Path $logDir | Out-Null
Push-Location $manuscriptDir
try {
    $transcript = Join-Path $logDir 'latex_compile.log'
    "COMPILE_TIME=$(Get-Date -Format o)" | Set-Content -LiteralPath $transcript -Encoding UTF8
    "PDFLATEX=$pdflatex" | Add-Content -LiteralPath $transcript -Encoding UTF8
    "BIBTEX=$bibtex" | Add-Content -LiteralPath $transcript -Encoding UTF8

    foreach ($stem in @(
        'manuscript_submission_candidate_v4_final_r1',
        'supplement_submission_candidate_v4_final_r1'
    )) {
        "===== $stem =====" | Add-Content -LiteralPath $transcript -Encoding UTF8
        & $pdflatex -interaction=nonstopmode -halt-on-error "$stem.tex" 2>&1 |
            Tee-Object -FilePath $transcript -Append
        if ($LASTEXITCODE -ne 0) { throw "pdflatex first pass failed for $stem" }

        if (Test-Path -LiteralPath "$stem.aux") {
            $auxText = Get-Content -Raw -LiteralPath "$stem.aux"
            if ($auxText -match '\\bibdata') {
                & $bibtex $stem 2>&1 | Tee-Object -FilePath $transcript -Append
                if ($LASTEXITCODE -ne 0) { throw "bibtex failed for $stem" }
            }
        }

        1..2 | ForEach-Object {
            & $pdflatex -interaction=nonstopmode -halt-on-error "$stem.tex" 2>&1 |
                Tee-Object -FilePath $transcript -Append
            if ($LASTEXITCODE -ne 0) { throw "pdflatex final pass failed for $stem" }
        }
    }

    Get-FileHash -Algorithm SHA256 -LiteralPath (
        Join-Path $manuscriptDir 'manuscript_submission_candidate_v4_final_r1.pdf'
    ), (
        Join-Path $manuscriptDir 'supplement_submission_candidate_v4_final_r1.pdf'
    ) | Format-Table Path,Hash -AutoSize | Out-String |
        Add-Content -LiteralPath $transcript -Encoding UTF8
}
finally {
    Pop-Location
}
