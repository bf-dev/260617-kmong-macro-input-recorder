# P2C POS Macro

P2C/MOM'S TOUCH 포스용 Windows 자동화 프로그램입니다. 고객 녹화 파일을 고객 PC에서 다시 불러오는 방식이 아니라, 확인된 3개 작업을 프로그램 안에 내장해서 독립 실행되도록 만들었습니다.

## 포함 작업

- 가승인
- 개점
- 마감

첫 실행 시 내장 작업과 이미지 기준점(anchor)을 `문서/P2C_POS_자동화/workflows`에 자동 복구합니다. 고객은 `recording.zip`을 따로 선택할 필요가 없습니다.

## 실행 로직

- 버튼 클릭 위치 주변 이미지 anchor를 먼저 화면에서 찾습니다.
- 해상도/배율 차이에 대비해 0.88~1.12 범위의 다중 배율 이미지 매칭을 시도합니다.
- 이미지가 흔들리면 포스 화면 구조를 보고 주황색 액션 버튼, 어두운 확인창의 노란 확인 버튼, 흰 보조 버튼을 감지합니다.
- 그래도 못 찾는 경우에만 녹화 당시 화면 비율 기준 좌표 보정을 사용합니다.
- 녹화 종료 과정의 Alt+Tab, 작업표시줄 클릭, 매크로 녹화기 창 클릭은 가져오기 단계에서 제외했습니다.

## 개발/검증

```bash
python3.12 -m venv .venv
. .venv/bin/activate
pip install -e '.[test,build]'
pytest -q
python scripts/capture_p2c_preview.py --output delivery/p2c-pos-macro-ui-preview.png
```

Windows EXE는 GitHub Actions의 `Build Windows EXE` 워크플로로 빌드합니다.
