$ErrorActionPreference = 'Stop'

python -m pip install --upgrade pip
python -m pip install -e ".[build,test]"
python -m pytest -q
pyinstaller --noconfirm packaging\macro_input_recorder.spec

if (!(Test-Path "dist\MacroInputRecorder.exe")) {
  throw "dist\MacroInputRecorder.exe was not created"
}

Get-FileHash "dist\MacroInputRecorder.exe" -Algorithm SHA256 | Format-List | Out-File "dist\MacroInputRecorder.exe.sha256.txt" -Encoding utf8
Write-Host "Built dist\MacroInputRecorder.exe"
