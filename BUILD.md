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

## spec 파일 사용 (고급)

반복적인 빌드를 위해 `.spec` 파일을 생성하고 수정할 수 있습니다:

1. 먼저 기본 빌드를 실행하면 `Flow.spec` 파일이 생성됩니다.
2. 필요에 따라 spec 파일을 수정합니다.
3. 이후 빌드 시:

```powershell
pyinstaller Flow.spec
```

## 배포 시 주의사항

1. 빌드는 배포 대상과 동일한 Windows 버전에서 수행하는 것이 좋습니다.
2. `--onefile` 옵션은 시작 시간이 다소 느려질 수 있습니다.
3. 백신 프로그램이 exe 파일을 오탐지할 수 있으니 예외 처리가 필요할 수 있습니다.
