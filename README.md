# Flow: 찬양 가사 송출 시스템

악보 기반 직관적 UI를 통해 찬양 가사를 유튜브 라이브로 송출하는 데스크톱 애플리케이션

## 설치

```bash
# 가상 환경 생성 (최초 1회)
python -m venv .venv

# 가상 환경 활성화
# Linux/macOS
source .venv/bin/activate
# Windows
.venv\Scripts\activate

# 의존성 설치
pip install -e ".[dev]"
```

## 실행

```bash
# 애플리케이션 실행
flow

# 또는
python -m flow.main
```

## 테스트

```bash
# 전체 테스트 실행
pytest

# 커버리지 포함
pytest --cov=flow --cov-report=term-missing
```

## 기능

- **편집 모드**: 악보 이미지 로드, 핫스팟 생성, 가사 매핑
- **라이브 모드**: Preview-Live 2단계 송출
- **송출 모드**: 듀얼 모니터 전체화면 가사 표시
