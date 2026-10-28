$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$python=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) {throw 'Environment creation failed.'}
}
& $python -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) {throw 'Dependency installation failed.'}
& $python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) {throw 'Tests failed.'}
& $python export_ce_table.py
if ($LASTEXITCODE -ne 0) {throw 'CE table generation failed.'}
& $python export_compatibility.py
if ($LASTEXITCODE -ne 0) {throw 'Compatibility reference generation failed.'}
& $python render_preview.py
if ($LASTEXITCODE -ne 0) {throw 'Asset rendering failed.'}
& $python -m PyInstaller --noconfirm --distpath build-output --workpath build rangelab.spec
if ($LASTEXITCODE -ne 0) {throw 'Packaging failed.'}
New-Item -ItemType Directory -Path 'release\RangeLab' -Force | Out-Null
Copy-Item -Path 'build-output\RangeLab\*' -Destination 'release\RangeLab' -Recurse -Force
Copy-Item -LiteralPath README.md,'AssaultCube-1.3.0.2.CT','ADDRESS-MAP.md','CT-TRAINER-GUIDE.md','MULTIPLAYER-COMPATIBILITY.md','MULTIPLAYER-DIAGNOSTICS.md','CONFIGURATION-GUIDE.md','SOURCE-REVIEW.md','NATIVE-FEATURES.md' -Destination 'release\RangeLab' -Force
