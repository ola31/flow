# Flow 애플리케이션 빌드 가이드

이 문서는 Flow 애플리케이션을 Windows 실행 파일(.exe)로 빌드하는 방법을 설명합니다.
빌드된 exe 파일은 터미널 창 없이 바로 실행됩니다.

## 사전 요구사항

- Python 3.10 이상
- 가상환경 활성화 상태

## 빌드 도구 설치

> ⚠️ **중요**: 반드시 가상환경(`.venv`)을 활성화한 상태에서 PyInstaller를 설치하세요!  
> 시스템 Python에 설치하면 가상환경의 패키지들을 찾지 못합니다.

```powershell
# 가상환경 활성화
.venv\Scripts\activate

# PyInstaller 설치 (가상환경 내에서)
pip install pyinstaller
```

## 빌드 방법

### 기본 빌드 (단일 폴더)

```powershell
pyinstaller --name Flow --windowed --noconfirm src/flow/main.py
```

### 단일 exe 파일로 빌드

```powershell
pyinstaller --name Flow --windowed --onefile --noconfirm src/flow/main.py
```

### 옵션 설명

| 옵션 | 설명 |
|------|------|
| `--name Flow` | 출력 파일 이름을 "Flow"로 지정 |
| `--windowed` | 터미널 창 없이 GUI 모드로 실행 (중요!) |
| `--onefile` | 모든 파일을 하나의 exe로 패키징 |
| `--noconfirm` | 기존 빌드 폴더 덮어쓰기 |

## 빌드 결과물

빌드 완료 후 다음 위치에 파일이 생성됩니다:

- **단일 폴더 빌드**: `dist/Flow/Flow.exe`
- **단일 파일 빌드**: `dist/Flow.exe`

## 아이콘 추가 (선택사항)

아이콘 파일(.ico)이 있다면 다음과 같이 추가할 수 있습니다:

```powershell
pyinstaller --name Flow --windowed --onefile --icon=assets/icon.ico --noconfirm src/flow/main.py
```

## 리소스 파일 포함

`assets` 폴더의 리소스를 포함해야 한다면:

```powershell
pyinstaller --name Flow --windowed --onefile --add-data "assets;assets" --noconfirm src/flow/main.py
```

## 문제 해결

### 1. 모듈을 찾을 수 없음 오류

숨겨진 임포트가 있다면 `--hidden-import` 옵션을 사용합니다:

```powershell
pyinstaller --name Flow --windowed --onefile --hidden-import PySide6.QtWidgets --noconfirm src/flow/main.py
```

### 2. DLL 누락 오류

`bin` 폴더에 외부 바이너리가 있다면 함께 포함합니다:

```powershell
pyinstaller --name Flow --windowed --onefile --add-binary "bin/*;bin" --noconfirm src/flow/main.py
```

### 3. pdf2image 관련 오류

`pdf2image`는 Poppler를 필요로 합니다. `bin` 폴더에 Poppler가 있다면:

```powershell
pyinstaller --name Flow --windowed --onefile --add-binary "bin/poppler/*;bin/poppler" --noconfirm src/flow/main.py
```

## 권장 빌드 명령어 (전체)

```powershell
pyinstaller --name Flow --windowed --onefile --add-data "assets;assets" --add-binary "bin;bin" --noconfirm src/flow/main.py
```

## 권장 빌드 방법 (추천)

우리는 실행 속도 최적화를 위해 **`.spec` 파일을 이용한 폴더 방식(`--onedir`)** 빌드를 권장합니다. 로딩 화면(Splash Screen)과 리소스 파일이 이 설정에 포함되어 있습니다.

```powershell
# 1. 가상환경 활성화
.venv\Scripts\activate

# 2. spec 파일을 이용한 빌드
pyinstaller Flow.spec --noconfirm
```

### 빌드 결과물
빌드 완료 후 `dist/Flow/` 폴더가 생성됩니다. 그 안의 `Flow.exe`가 실행 파일이며, 이 폴더 전체가 프로그램의 '내용물'입니다.

---

## 인스톨러(Installer) 제작 및 배포

폴더 통째로 사용자에게 주는 대신, 하나의 깔끔한 **설치 파일(`Setup.exe`)**로 만들고 싶다면 외부 도구를 사용하세요.

### 1. Inno Setup (권장)
- 가장 널리 쓰이는 무료 설치 프로그램 제작 도구입니다.
- `dist/Flow/` 폴더를 소스로 지정하여 설치 경로(`Program Files`)와 바로가기를 생성하는 스크립트를 작성할 수 있습니다.
- 설치 후 **삭제(Uninstall)** 및 **업데이트(Update)**가 제어판을 통해 관리됩니다.

### 2. 업데이트 전략
- 새로운 버전을 인스톨러로 배포하면, 기존 설치 경로의 파일들을 자동으로 교체합니다.
- 사용자 설정은 홈 디렉토리(`.flow/`)에 남으므로 안전합니다.

## 문제 해결 및 주의사항

1. **로딩 화면 미출력**: `assets/splash.png` 파일이 있는지 확인하세요.
2. **실행 속도**: `--onedir` 방식은 처음 실행 시 압축 해제가 없어 매우 빠릅니다.
3. **보안 소프트웨어**: 빌드된 exe가 백신에 의해 차단될 수 있으므로, 인스톨러로 배포하고 디지털 서명을 하는 것이 좋습니다.
