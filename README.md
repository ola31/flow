# Flow: 예배 슬라이드 송출 시스템

악보 이미지 위에 핫스팟을 배치하고 PPT 슬라이드를 매핑하여, 예배 중 한 번의 클릭으로 슬라이드를 라이브 송출하는 데스크톱 애플리케이션.

## 핵심 구조

**곡(Song)** — 재사용 가능한 기본 단위. 악보 이미지 + PPT + 핫스팟 매핑을 포함.
**프로젝트(Project)** — 곡들을 순서대로 조합한 셋리스트. 예배 한 회차에 해당.

```
프로젝트 폴더/
├── project.json          # 곡 순서, 설정
└── songs/
    ├── 주님의기쁨/
    │   ├── song.json     # 시트, 핫스팟 매핑
    │   ├── sheets/       # 악보 이미지
    │   └── slides.pptx   # PPT 슬라이드
    └── 은혜/
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
pytest
pytest --cov=flow --cov-report=term-missing
```

## 주요 기능

### 편집 모드
- 악보 이미지 위에 핫스팟 배치 (클릭으로 추가, 드래그로 이동)
- 슬라이드 더블클릭으로 핫스팟-슬라이드 매핑
- 절(1-5절 + 후렴)별 독립 매핑
- 매핑 패널: 핫스팟 선택 시 절별 매핑 현황 한눈에 확인
- Undo/Redo 지원 (Ctrl+Z/Y)

### 라이브 모드 (F5)
- Preview → Live 2단계 송출 (방향키로 선택, Enter로 송출)
- 숫자키(1-5, C)로 절 전환
- B키로 블랙아웃
- 듀얼 모니터 전체화면 송출 (F11)

### 곡 관리
- 셋리스트 카드 뷰: 각 곡의 상태(악보/PPT/매핑) 확인
- 라이브러리 브라우저: 검색 + 상태 배지로 곡 추가
- 곡 편집 모드: 프로젝트 내에서 개별 곡 편집 후 복귀

## 기술 스택

- Python 3.10+, PySide6 (Qt Widgets)
- python-pptx, pdf2image + LibreOffice
- Material Symbols Rounded (아이콘 폰트)
- PyInstaller (배포)
