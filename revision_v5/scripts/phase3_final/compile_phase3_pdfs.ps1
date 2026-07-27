$ErrorActionPreference = 'Continue'
$docDir = (Get-Location).Path
$logDir = [System.IO.Path]::GetFullPath((Join-Path $docDir '..\..\logs_v5\reviewer_revision_v4\phase3'))

function Run-Step {
    param(
        [string]$Program,
        [string[]]$Arguments,
        [string]$LogPath,
        [bool]$Append
    )
    if ($Append) {
        & $Program @Arguments 2>&1 | Tee-Object -FilePath $LogPath -Append
    } else {
        & $Program @Arguments 2>&1 | Tee-Object -FilePath $LogPath
    }
    if ($LASTEXITCODE -ne 0) {
        throw "$Program failed with exit code $LASTEXITCODE"
    }
}

$mainLog = Join-Path $logDir 'compile_main_v4.log'
Run-Step 'pdflatex' @('-interaction=nonstopmode','-halt-on-error','-file-line-error','manuscript_submission_candidate_v4.tex') $mainLog $false
Run-Step 'bibtex' @('manuscript_submission_candidate_v4') $mainLog $true
Run-Step 'pdflatex' @('-interaction=nonstopmode','-halt-on-error','-file-line-error','manuscript_submission_candidate_v4.tex') $mainLog $true
Run-Step 'pdflatex' @('-interaction=nonstopmode','-halt-on-error','-file-line-error','manuscript_submission_candidate_v4.tex') $mainLog $true

$suppLog = Join-Path $logDir 'compile_supplement_v4.log'
Run-Step 'pdflatex' @('-interaction=nonstopmode','-halt-on-error','-file-line-error','supplement_submission_candidate_v4.tex') $suppLog $false
Run-Step 'pdflatex' @('-interaction=nonstopmode','-halt-on-error','-file-line-error','supplement_submission_candidate_v4.tex') $suppLog $true
Run-Step 'pdflatex' @('-interaction=nonstopmode','-halt-on-error','-file-line-error','supplement_submission_candidate_v4.tex') $suppLog $true

Write-Output 'COMPILE_MAIN=passed'
Write-Output 'COMPILE_SUPPLEMENT=passed'
