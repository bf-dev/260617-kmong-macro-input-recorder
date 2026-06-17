# Macro Input Recorder

A small Windows desktop recorder for macro preparation. It records local mouse clicks and keyboard presses, captures a screenshot for each event, and writes a JSON log plus PNG screenshots to the Desktop.

## Output structure

Each recording creates:

```text
Desktop/
  recording/
    YYYYMMDD_HHMMSS/
      output/
        events.json
        events.jsonl
        images/
          000001_mouse_click.png
          000002_key_press.png
```

## Use

1. Run `MacroInputRecorder.exe`.
2. Click **Start recording**.
3. Perform the clicks/keyboard input you want to capture.
4. Click **Stop recording**.
5. Open the output folder shown in the app.

## Build locally

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e .[build,test]
pytest -q
pyinstaller --noconfirm packaging\macro_input_recorder.spec
```

The Windows executable is written to `dist\MacroInputRecorder.exe`.

## GitHub Actions release

Pushing a tag like `v0.1.0` builds the standalone Windows EXE and attaches it to the GitHub Release.
