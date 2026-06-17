# P2C 포스 자동화

P2C/MOM'S TOUCH 포스 업무를 녹화 기반으로 실행하는 Windows GUI 도구입니다.

## 포함 기능

- `recording.zip` 또는 녹화 `output/events.json` 가져오기
- 클릭 위치 주변 스크린샷을 anchor 이미지로 저장
- 실행 시 anchor 이미지 인식 우선, 실패하면 화면 비율 좌표 보정으로 fallback
- 개점/마감/가승인 등 녹화 작업별 저장 및 1회 실행
- 시간당 가승인 반복 실행 설정
- 긴급 중지: 마우스를 화면 왼쪽 위 모서리로 이동하면 PyAutoGUI failsafe 작동
- 한국어 Tkinter UI

## 고객 기본 범위

- 포스: P2C
- 시간당 싸이버거 세트 5개
- 가승인 금액: 38,500원
- 개점/마감 포함

## 사용 흐름

1. 고객 PC에서 `MacroInputRecorder.exe`로 각 작업을 녹화합니다.
2. 저장된 `recording.zip` 또는 `output` 폴더를 `P2CPOSMacro.exe`에서 가져옵니다.
3. 작업 이름을 `개점`, `마감`, `가승인`처럼 저장합니다.
4. 실행 탭에서 작업을 선택하고 1회 실행 또는 시간당 자동 실행을 시작합니다.

## 검증

```bash
python3 -m compileall src tests
python3 -m pytest -q
pyinstaller --noconfirm packaging/p2c_pos_macro.spec
```

Windows EXE는 GitHub Actions `.github/workflows/windows-exe.yml`에서 `P2CPOSMacro.exe`로 빌드됩니다.

## 현재 제한

이 저장소에는 아직 고객 PC의 `recording.zip`이 들어오지 않았습니다. 녹화 파일이 들어오면 `녹화 가져오기`로 작업별 anchor/좌표를 생성해야 실제 P2C 화면에 맞게 실행됩니다.
