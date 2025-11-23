param()
Set-StrictMode -Version Latest

$root = Join-Path $PSScriptRoot '..' | Resolve-Path
Set-Location (Join-Path $root 'geo_search')

if (-not (Get-Command lupdate -ErrorAction SilentlyContinue)) {
    Write-Host "lupdate not found. Install Qt Linguist (add lupdate to PATH)." -ForegroundColor Yellow
    Write-Host "On Windows with Qt installed you may find lupdate at: C:\\Qt\\<version>\\bin\\lupdate.exe"
    exit 2
}

Write-Host "Running lupdate to update .ts files..."
& lupdate . -no-obsolete -ts i18n\*.ts

Write-Host "Running lrelease to build .qm files..."
& lrelease i18n\*.ts

Write-Host "Done. Review changes and commit if OK."
