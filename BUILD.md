# Flow 빌드 & 릴리스 가이드

## 한눈에 보기

```
__init__.py 의 __version__ 수정 → git commit → git tag v0.X.Y → git push --tags
                                                                    │
                                                                    ▼
                            GitHub Actions 가 Win/Mac/Linux 모두 자동 빌드
                                                                    │
                                                                    ▼
                       Release v0.X.Y 페이지에 인스톨러·포터블·AppImage 첨부
```

## 릴리스 절차 (정상 경로)

1. `src/flow/__init__.py` 의 `__version__` 을 다음 버전으로 올림 (예: `"0.1.0"` → `"0.2.0"`).
   - `pyproject.toml` 은 hatchling dynamic version 으로 자동 동기화됨 — 손대지 않음.
2. 변경 커밋 후 태그 push:
   ```bash
   git commit -am "release v0.2.0"
   git tag v0.2.0
   git push origin main --tags
   ```
3. GitHub Actions (`.github/workflows/release.yml`) 가 트리거됨 — 약 8~15분 소요.
4. 끝나면 `Releases` 탭에 새 릴리스가 만들어지고 다음 파일들이 첨부됨:

| 플랫폼 | 파일 | 사용법 |
|---|---|---|
| Windows | `Flow-Setup-{ver}.exe` | 더블클릭 → 마법사로 설치 (Program Files 등록, 시작 메뉴, 제어판 삭제 가능) |
| Windows | `Flow-portable-{ver}.zip` | 압축 해제 → `Flow.exe` 실행. 설치/레지스트리 사용 안 함 |
| macOS (Apple Silicon) | `Flow-macOS-{ver}.zip` | 압축 해제 → `Flow.app` 더블클릭. **첫 실행은 우클릭 → 열기** (미서명) |
| Linux (x86_64) | `Flow-{ver}-x86_64.AppImage` | `chmod +x` 후 실행. 어느 배포판에서나 동작 |

## 미리 알아둘 점

- **macOS 코드 서명/노타리제이션 없음** — Apple Developer ID ($99/년) 가 없는 상태라 사용자가 처음 열 때 "확인되지 않은 개발자" 경고가 뜨고, 우클릭→열기로 한 번 승인해야 함. 정식 배포 전에 노타리제이션 추가 권장.
- **macOS는 Apple Silicon (arm64) 만 빌드** — Intel Mac 에서는 실행되지 않음. 필요해지면 워크플로우 matrix 에 `macos-13` 추가.
- **Linux 는 ubuntu-22.04 빌드** — glibc 2.35+ 환경에서 동작. 더 오래된 배포판이 필요하면 ubuntu-20.04 로 낮추거나 별도 매트릭스 추가.

## 로컬 빌드 (테스트용)

CI 와 동일한 흐름을 로컬에서 돌려 검증할 수 있습니다.

### Windows

```powershell
.venv\Scripts\activate
pip install pyinstaller
pyinstaller Flow.spec --noconfirm
# 결과: dist\Flow\Flow.exe
```

인스톨러까지 만들려면 [Inno Setup](https://jrsoftware.org/isinfo.php) 설치 후:

```powershell
iscc /DAppVersion=0.1.0 /DSourceDir=..\dist\Flow /DOutputDir=..\dist installer\Flow.iss
# 결과: dist\Flow-Setup-0.1.0.exe
```

### macOS

```bash
source .venv/bin/activate
pip install pyinstaller
pyinstaller Flow.spec --noconfirm
# 결과: dist/Flow.app
open dist/Flow.app
```

### Linux

```bash
source .venv/bin/activate
pip install pyinstaller
pyinstaller Flow.spec --noconfirm
# 결과: dist/Flow/Flow

# AppImage 만들려면:
wget -q https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage -O appimagetool
chmod +x appimagetool
# (이후 .github/workflows/release.yml 의 "Build AppImage" 단계 참고)
```

## 파일 구조

| 파일 | 목적 |
|---|---|
| `Flow.spec` | PyInstaller 설정 (Win/Mac/Linux 공통, OS 별 자동 분기) |
| `installer/Flow.iss` | Inno Setup 스크립트 — Windows Setup.exe 생성 |
| `assets/icon.ico` / `.png` / `.icns` | OS 별 아이콘 |
| `assets/flow.desktop` | Linux 데스크톱 진입점 (AppImage 안에 포함됨) |
| `.github/workflows/release.yml` | 태그 push → 자동 빌드/릴리스 워크플로우 |

## 향후 개선 후보

1. **Windows 코드 서명** — EV/OV 인증서 ($100~300/년). SmartScreen 경고 제거.
2. **macOS 노타리제이션** — Apple Developer Program ($99/년) + GitHub Secrets 등록. 우클릭→열기 단계 제거.
3. **macOS Intel 빌드** — `macos-13` 러너를 matrix 에 추가.
4. **자동 업데이트** — Sparkle (macOS) / 자체 다운로드 체크 등.
5. **Linux 추가 포맷** — Flatpak, .deb, Snap 등 (배포 채널 늘어날 때).
