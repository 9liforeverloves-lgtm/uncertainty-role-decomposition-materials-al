param(
    [ValidateSet("audit", "development-reduced", "confirmation")]
    [string]$Stage = "audit",
    [int]$Workers = 4
)

$ErrorActionPreference = "Stop"
$RevisionRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$WorkspaceRoot = Split-Path -Parent $RevisionRoot
$CodePackage = Get-ChildItem -LiteralPath $WorkspaceRoot -Directory -ErrorAction Stop |
    ForEach-Object { Join-Path $_.FullName "_code_package" } |
    Where-Object { Test-Path -LiteralPath (Join-Path $_ ".venv_corrected_v1\Scripts\python.exe") } |
    ForEach-Object { Get-Item -LiteralPath $_ } |
    Select-Object -First 1
$Python = if ($CodePackage) {
    Join-Path $CodePackage.FullName ".venv_corrected_v1\Scripts\python.exe"
} else {
    Join-Path $WorkspaceRoot "_missing_code_package_\python.exe"
}

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Pinned project Python is missing: $Python"
}

& $Python "$RevisionRoot\scripts\seed_namespace_audit.py"
& $Python "$RevisionRoot\scripts\build_ood_audit.py"
& $Python "$RevisionRoot\scripts\audit_global_scaling_equivalence.py"
& $Python "$RevisionRoot\scripts\verify_protected_baseline.py"
& $Python -m pytest -q -p no:cacheprovider --basetemp "$RevisionRoot\logs_v5\pytest_tmp_reproduce" "$RevisionRoot\tests"

if ($Stage -eq "development-reduced") {
    & $Python "$RevisionRoot\scripts\run_manifest_pool.py" --phase development_reduced --workers $Workers
}

if ($Stage -eq "confirmation") {
    if (-not (Test-Path -LiteralPath "$RevisionRoot\manifests_v4\CONFIRMATION_FREEZE_LOCK_V5_RC1.json")) {
        throw "Confirmation is blocked until development selection and the final confirmation freeze are complete."
    }
    & $Python "$RevisionRoot\scripts\run_manifest_pool.py" --phase confirmation --workers $Workers
}
