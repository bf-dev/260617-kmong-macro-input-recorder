$ErrorActionPreference = 'Stop'

python -m pip install --upgrade pip
python -m pip install -e ".[build,test]"
python -m pytest -q
python .\scripts\capture_p2c_preview.py --output "dist\p2c-pos-macro-ui-preview.png"
pyinstaller --noconfirm packaging\p2c_pos_macro.spec

if (!(Test-Path "dist\P2CPOSMacro.exe")) {
  throw "dist\P2CPOSMacro.exe was not created"
}
if (!(Test-Path "dist\p2c-pos-macro-ui-preview.png")) {
  throw "dist\p2c-pos-macro-ui-preview.png was not created"
}

Get-FileHash "dist\P2CPOSMacro.exe" -Algorithm SHA256 | Format-List | Out-File "dist\P2CPOSMacro.exe.sha256.txt" -Encoding utf8
Write-Host "Built dist\P2CPOSMacro.exe"
