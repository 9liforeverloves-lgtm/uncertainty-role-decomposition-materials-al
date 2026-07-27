$ErrorActionPreference = 'Continue'

$project = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$python = Join-Path $project '.venv_final_validation\Scripts\python.exe'
$tests = Join-Path $project 'reviewer_revision_v4\tests'
$logDir = Join-Path $project 'logs_v5\reviewer_revision_v4\final_r1'
$junit = Join-Path $logDir 'final_r1_junit.xml'
$log = Join-Path $logDir 'final_r1_complete_test.log'
$manuscriptDir = Join-Path $project 'manuscript_v5\submission_candidate_v4_final_r1'

New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$commandText = "$python -m pytest $tests -vv -ra --junitxml=$junit"

"COMMAND=$commandText" | Set-Content -LiteralPath $log -Encoding UTF8
"BASELINE_TEST_COUNT=175" | Add-Content -LiteralPath $log -Encoding UTF8
& $python --version 2>&1 | ForEach-Object {
    $_
    $_ | Out-File -LiteralPath $log -Append -Encoding utf8
}
& $python -m pytest --version 2>&1 | ForEach-Object {
    $_
    $_ | Out-File -LiteralPath $log -Append -Encoding utf8
}
& $python -m pytest $tests -vv -ra "--junitxml=$junit" 2>&1 |
    ForEach-Object {
        $_
        $_ | Out-File -LiteralPath $log -Append -Encoding utf8
    }
$testExit = $LASTEXITCODE

"===== VERIFIED SHA-256 =====" | Add-Content -LiteralPath $log -Encoding UTF8
$hashTargets = @(
    (Join-Path $manuscriptDir 'manuscript_submission_candidate_v4_final_r1.pdf'),
    (Join-Path $manuscriptDir 'supplement_submission_candidate_v4_final_r1.pdf'),
    (Join-Path $project 'tables_v5\FINAL_TABLE_LOCK_V5.json'),
    (Join-Path $project 'tables_v5\v5_rc1_primary_contrasts_final.csv')
)
Get-FileHash -Algorithm SHA256 -LiteralPath $hashTargets |
    ForEach-Object {
        $line = "$($_.Hash.ToLower())  $($_.Path)"
        $line
        $line | Out-File -LiteralPath $log -Append -Encoding utf8
    }

"TEST_EXIT_CODE=$testExit" | Add-Content -LiteralPath $log -Encoding UTF8
exit $testExit
