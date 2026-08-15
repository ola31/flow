# Flow: 악보 기반 슬라이드 송출 시스템

악보 이미지 위에 핫스팟을 배치하고 PPT 슬라이드를 매핑하여, 한 번의 클릭으로 슬라이드를 라이브 송출하는 데스크톱 애플리케이션. 악보(또는 가사 시트) 기반 송출이 필요한 다양한 컨텍스트에 사용 가능.

## 핵심 구조

**곡(Song)** — 재사용 가능한 기본 단위. 악보 이미지 + PPT + 핫스팟 매핑을 포함.
**프로젝트(Project)** — 곡들을 순서대로 조합한 셋리스트.
**워크스페이스(Workspace)** — 공용 곡 라이브러리와 프로젝트 목록을 함께 담는 작업 공간.

```
워크스페이스/
├── .flow-workspace   # 워크스페이스 루트 표식 (.git과 같은 역할)
├── library/
│   └── 곡A/
│       ├── song.json     # 시트, 핫스팟 매핑
│       ├── sheets/       # 악보 이미지
│       ├── slides.pptx   # PPT 슬라이드
│       └── slides.md     # 마크다운 슬라이드(선택)
└── projects/
    └── 2026-06-07/
        ├── project.json  # 곡 순서, 절 상태, 참조 정보
        └── songs/        # 프로젝트 전용 로컬 오버라이드(선택)
```

## 설치

```bash
python -m venv .venv
source .venv/bin/activate    # Linux/macOS
# .venv\Scripts\activate     # Windows
pip install -e ".[dev]"
```

## 실행

```bash
flow
# 또는
python -m flow.main
```

## 테스트

```bash
pytest                                   # 전체
pytest -n auto --reruns 1                # 병렬 (CI와 동일)
pytest --cov=flow --cov-report=term-missing
```

Qt 테스트는 `tests/conftest.py`가 `QT_QPA_PLATFORM=offscreen`을 강제해
헤드리스로 돕니다. 실제 화면에서 돌리려면 `QT_QPA_PLATFORM=wayland pytest ...`.

참고: PySide6 UI 테스트는 Qt/Python 조합에 민감합니다. CI가 검증하는
버전은 Python 3.11입니다.

## 주요 기능

### 편집 모드
- 악보 이미지 위에 핫스팟 배치 (클릭으로 추가, 드래그로 이동)
- 슬라이드 더블클릭으로 핫스팟-슬라이드 매핑
- 절(1-5절 + 후렴)별 독립 매핑
- 매핑 패널: 핫스팟 선택 시 절별 매핑 현황 한눈에 확인
- Undo/Redo 지원 (Ctrl+Z/Y)

### 라이브 모드 (F5)
- Preview → Live 2단계 송출 (좌우 방향키로 핫스팟 선택, Enter로 송출)
- 위아래 방향키로 곡·시트 전환
- 숫자키(1-5, C)로 절 전환
- B키로 블랙아웃
- 듀얼 모니터 전체화면 송출 (F11) — 송출 모니터 선택 가능
- 라이브 중 마크다운 슬라이드 긴급 수정, 라이브러리에서 곡 추가
- 수정 패치는 `.patches.json`에 저장 후 렌더링에 즉시 반영

### 웹 송출
- 같은 네트워크의 휴대폰·태블릿 브라우저로 현재 슬라이드 실시간 전송
- 접속 주소 QR 코드 표시, 접속자 수 표시
- HDMI 출력과 동시 송출 가능
- 야외처럼 네트워크가 없는 곳을 위한 Wi-Fi 핫스팟 (Linux는 nmcli,
  Windows는 모바일 핫스팟). 접속 시 페이지가 자동으로 열리는
  캡티브 포털 설정은 Linux만 지원

### 곡 관리
- 셋리스트 카드 뷰: 문제가 있는 곡만 경고 표시(악보/슬라이드/매핑 없음)
- 셋리스트 구간 나누기: 한 프로젝트에 오전·오후처럼 여러 순서를 함께 담기
- 라이브러리 브라우저: 제목·가사 검색, 카드를 눌러 악보·가사 미리보기 후 추가
- 곡 편집 모드: 좌측 곡 전환 목록으로 라이브러리를 오가지 않고 바로 이동
- 악보 이미지 교체: 핫스팟과 매핑을 유지한 채 그림만 교체(크기가 다르면 좌표 보정)
- 워크스페이스 기반 공용 라이브러리/프로젝트 분리
- 프로젝트 복제 시 라이브러리 곡은 참조 유지, 로컬 곡만 복사

### 마크다운 슬라이드
- `slides.md` 기반 슬라이드 작성
- frontmatter로 폰트, 색상, 배경, 출력 해상도 지정
- 편집기 내 실시간 미리보기와 썸네일 렌더링
- 라이브 종료 후 긴급 수정 패치를 원본에 반영하거나 폐기

## 기술 스택

- Python 3.10+, PySide6 (Qt Widgets)
- python-pptx, PyMuPDF, pdf2image + LibreOffice (PPT→이미지 변환)
- qrcode, watchdog, PyYAML
- Pretendard(UI 폰트) + Material Symbols Rounded(아이콘) 번들
- PyInstaller (배포)
