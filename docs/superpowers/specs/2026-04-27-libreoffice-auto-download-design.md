# LibreOffice 자동 다운로드 설계

- **작성일**: 2026-04-27
- **상태**: 설계 승인 대기 → 구현 플랜
- **관련 이슈**: PowerPoint/LibreOffice 모두 부재 시 PPT 변환 불가 문제 해결

## 배경

현재 Flow는 PPT 슬라이드를 이미지로 변환할 때 시스템에 설치된 PowerPoint 또는 LibreOffice를 호출한다 (`src/flow/services/slide_converter.py`). 둘 다 없는 사용자에게는 `flow_show_install_guide()` 다이얼로그를 띄워 수동 설치를 안내하는데, 이는 사용자 마찰이 크다 (apt/brew/Windows 인스톨러 실행을 사용자에게 떠넘김).

해결책으로 Flow가 LibreOffice를 **앱-로컬 영역에 자동 다운로드**해서 사용한다. 시스템에 LibreOffice가 설치되는 게 아니라 Flow의 사용자 데이터 디렉토리에 풀어두는 portable 방식.

## 결정 사항

| 결정 | 선택 | 이유 |
|---|---|---|
| 호스팅 | 매니페스트 + 공식 미러 직접 다운로드 | TDF 미러 네트워크 활용, 우리 SPOF 회피, 호스팅 비용 0 |
| 트리거 시점 | Lazy (첫 PPT 로드 시점, 엔진 부재일 때만) | PPT 안 쓰는 사용자에게 노이즈 없음 |
| 실패 정책 | All-or-nothing (재시도) | 일회성 이벤트라 단순함이 우선 |
| 편집 버튼 fallback | 이번 범위 포함 | 추가 비용 ~30줄, UX 일관성 |
| 라이선스/상표 | Verbatim 재배포 (변경 없음) | TDF 상표 정책 클린, MPL 2.0 의무만 충족 |

## 아키텍처

```
UI Layer
├─ MainWindow
│  └─ engine_missing 시그널 → PreflightDialog (NEW)
└─ SongListWidget._open_in_external_app
   └─ QDesktopServices 실패 시 → bundled LO fallback (NEW)

Service Layer
├─ slide_converter.py
│  └─ create_slide_converter() — bundled LO 탐지 통합
└─ runtime/                                 ← 새 패키지
   ├─ libreoffice_runtime.py                ← 다운로드 오케스트레이터
   ├─ manifest.py                           ← 매니페스트 파싱 + OS×아키 매칭
   └─ extractor.py                          ← OS별 .tar.gz/.dmg/.msi 추출

Resource Layer
├─ flow/resources/libreoffice_manifest.json (체크인)
└─ {user_data}/Flow/runtime/libreoffice/    (런타임)
```

### 책임 분리

- `libreoffice_runtime.py` — "있나? 받자. 어디 있지?" (탐지/설치/경로 조회)
- `manifest.py` — JSON 파싱, 현재 OS×아키텍처 매칭
- `extractor.py` — 다운로드된 아카이브 추출 (포맷별)
- `slide_converter.py` — 변환만. 런타임 모듈에 "soffice 어딨어?"만 물어봄
- UI는 진행 다이얼로그와 시그널 핸들링만

## 매니페스트

`src/flow/resources/libreoffice_manifest.json`은 Flow 빌드와 함께 체크인되어 LibreOffice 버전 핀을 따라간다. URL/해시 변경은 새 Flow 릴리스로만 반영. 외부 호스팅 JSON은 YAGNI.

```json
{
  "version": "25.2.5.2",
  "source_url": "https://www.libreoffice.org/download/",
  "license_url": "https://www.libreoffice.org/about-us/licenses/",
  "builds": {
    "linux-x86_64": {
      "url": "https://download.documentfoundation.org/libreoffice/stable/25.2.5/deb/x86_64/LibreOffice_25.2.5.2_Linux_x86-64_deb.tar.gz",
      "sha256": "<채워넣기>",
      "size_bytes": 287654321,
      "format": "tar_gz",
      "soffice_relpath": "LibreOffice_25.2.5.2_Linux_x86-64_deb/program/soffice"
    },
    "linux-aarch64":   { "format": "tar_gz", "...": "..." },
    "macos-x86_64":    { "format": "dmg", "soffice_relpath": "LibreOffice.app/Contents/MacOS/soffice", "...": "..." },
    "macos-aarch64":   { "format": "dmg", "...": "..." },
    "windows-x86_64":  { "format": "msi", "soffice_relpath": "program/soffice.exe", "...": "..." },
    "windows-aarch64": { "format": "msi", "...": "..." }
  }
}
```

미지원 조합 (예: 32비트 x86, RISC-V) → `UnsupportedPlatformError` → 기존 install-guide로 fallback.

## 저장 위치

```python
def get_runtime_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ["LOCALAPPDATA"])
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    return base / "Flow" / "runtime" / "libreoffice"
```

### 디렉토리 레이아웃

```
{runtime_dir}/
├── 25.2.5.2/                          ← 버전별 폴더
│   ├── (압축 해제된 LibreOffice 트리)
│   ├── LICENSE                         ← 원본 보존
│   └── NOTICE
├── INSTALLED_VERSION                   ← 텍스트 파일, "25.2.5.2"
├── .lock                               ← 동시 다운로드 방지
└── .download/                          ← 다운로드 중 임시
    └── libreoffice-25.2.5.2.tar.gz.partial
```

- 버전 폴더 분리 → 신버전 검증 후 구버전 삭제 (in-place 교체보다 안전)
- `INSTALLED_VERSION`이 단일 진실: 매니페스트와 다르면 업그레이드 트리거
- atomic write (`tempfile + os.replace`)로 partial 상태 방지

## 트리거 흐름

```
[Idle]
   │ 사용자가 .pptx 로드, 엔진 미존재
   ▼
PreflightDialog
   "PPT를 열려면 변환 엔진이 필요해요 (LibreOffice ~290MB)"
   [지금 다운로드] [수동 설치 안내] [취소]
   ┌────────┬──────────┬──────┐
   ▼        ▼          ▼
Download   기존        Idle 복귀
Progress   install-     (다음 PPT 시 재트리거)
Dialog     guide
   │
   ┌──┴──┐
  성공   실패/취소
   │      │
   ▼      ▼
변환 재개  ErrorDialog
          [재시도] [수동 설치] [닫기]
```

### 진행 단계 (한 다이얼로그 안 phase 텍스트만 변경)

1. "다운로드 중... 120 / 290 MB" — 진행바 0~85%
2. "무결성 검증 중..." — 85~90%
3. "압축 해제 중..." — 90~99%
4. "완료. 변환을 이어갑니다." — 100% → 자동 닫힘

### 스레딩

- 다운로드/검증/추출은 `QThread` 워커 (PPT 변환과 동일 패턴)
- 시그널: `progress(int phase, int percent, str msg)`, `finished(bool success, str error)`
- UI 스레드는 진행바 갱신만

### 라이선스 표기 (의무)

- PreflightDialog 본문 하단: "LibreOffice는 The Document Foundation의 자유 소프트웨어입니다. [라이선스 보기] [공식 사이트]"
- 추출 시 패키지 내 `LICENSE`/`NOTICE` 파일을 `{runtime_dir}/{version}/`에 보존
- Flow의 About/Credits 화면이 있으면 "Includes LibreOffice (MPL 2.0)" 추가, 없으면 PreflightDialog 하단 표기로 대체

## 탐지 우선순위

`create_slide_converter()` 변경:

```python
def create_slide_converter() -> SlideConverter:
    has_pp = _detect_powerpoint()
    has_system_lo = _detect_libreoffice()
    has_bundled_lo = _detect_bundled_libreoffice()  # NEW

    # 우선순위: PowerPoint → bundled LO → 시스템 LO
    if sys.platform == "win32":
        if has_pp or has_bundled_lo or has_system_lo:
            return WindowsSlideConverter(bundled_lo_path=has_bundled_lo)
    elif sys.platform == "darwin":
        if has_pp or has_bundled_lo or has_system_lo:
            return MacOSSlideConverter(bundled_lo_path=has_bundled_lo)
    else:
        if has_bundled_lo or has_system_lo:
            return LinuxSlideConverter(bundled_lo_path=has_bundled_lo)

    raise NoConverterAvailableError(sys.platform)
```

각 컨버터의 LibreOffice 경로 조회는 `bundled_lo_path` 우선 → 시스템 경로 fallback.

## 편집 버튼 Fallback

`song_list_widget.py`의 PPT 편집 핸들러 (현재 `QDesktopServices.openUrl` 사용):

```python
url = QUrl.fromLocalFile(str(pptx_path))
if not QDesktopServices.openUrl(url):
    # OS 연결 앱 없음 → bundled LibreOffice 시도
    bundled = get_bundled_soffice_path()  # 새 헬퍼
    if bundled and bundled.exists():
        subprocess.Popen([str(bundled), "--impress", str(pptx_path)])
    else:
        QMessageBox.warning(self, "열기 실패", ...)
```

기존 파일 워처 일시정지 로직은 그대로 유지.

## 에러 처리 매트릭스

| 시나리오 | 동작 |
|---|---|
| 네트워크 끊김 | `requests.exceptions` catch → `.download/` 정리 → ErrorDialog ("네트워크 오류, 재시도") |
| SHA256 불일치 | 받은 파일 삭제 → ErrorDialog ("파일이 손상되었어요. 재시도") + GitHub 이슈 링크 |
| 디스크 공간 부족 | 다운로드 시작 전 `shutil.disk_usage()` 체크 → PreflightDialog 단계 차단 |
| 추출 실패 (.dmg mount 등) | 버전 폴더 정리 → ErrorDialog (수동 설치 안내) |
| 권한 부족 (sandboxed env) | `PermissionError` catch → ErrorDialog (수동 설치 안내) |
| 다운로드 중 강제 종료 | 다음 실행 시 `INSTALLED_VERSION` 없음 + `.download/` 잔존 → 시작 시 청소, 다음 PPT 시도 때 처음부터 |
| 미지원 아키텍처 | `UnsupportedPlatformError` → install-guide만 표시 |
| 매니페스트 버전 ↑ | `INSTALLED_VERSION` ≠ manifest version 감지 → 다음 PPT 로드 때 PreflightDialog ("엔진 업데이트가 있어요") |
| 동시 다운로드 시도 | `.lock` 파일 (fcntl/msvcrt) — 두 번째 시도는 차단 |

## 보안

- HTTPS 강제 (매니페스트 URL이 http면 reject)
- SHA256 검증 필수 (옵션 아님)
- Linux/macOS: 실행 권한 부여 (`chmod +x`)
- macOS: Gatekeeper/Quarantine attribute 처리는 실제 환경 검증 후 필요시 `xattr -d com.apple.quarantine` 추가

## 테스트

### 단위 테스트 (`tests/runtime/`)

| 모듈 | 테스트 |
|---|---|
| `manifest.py` | 정상 파싱, 누락 필드 거부, OS×아키 매칭, 미지원 조합 → `UnsupportedPlatformError` |
| `extractor.py` | tar.gz 압축 해제, 손상 파일 거부, `soffice_relpath` 존재 검증 |
| `libreoffice_runtime.py` | 설치 상태 판정 (없음/설치됨/구버전), 다운로드 흐름 (mocked HTTP/SHA256), 취소 시 `.download/` 정리, 디스크 부족 사전 차단 |
| `slide_converter.py` | bundled LO 우선순위 작동, fallback 체인 |

### 통합 테스트

- `engine_missing` → MainWindow가 PreflightDialog 띄우는지 (기존 install-guide 자리 교체)
- `QDesktopServices.openUrl` 실패 mock 시 bundled LO 호출

### 수동 E2E

- 실제 LO 다운로드 → 변환 → 편집 fallback (Linux에서 가능)
- 매니페스트 버전 강제 변경 → 업그레이드 흐름

### 기존 테스트 영향

- `tests/services/test_slide_manager.py` 일부 — `engine_missing` 핸들러 변경 반영
- 현재 baseline 239 통과 / 2 미해결 유지 목표

## 범위

### 포함

1. `src/flow/services/runtime/` 신규 패키지 (`libreoffice_runtime.py`, `manifest.py`, `extractor.py`)
2. `src/flow/resources/libreoffice_manifest.json` 체크인 (LO 25.2.x 기준)
3. `slide_converter.py`: bundled LO 탐지 + 우선순위 통합
4. `slide_manager.py`: `engine_missing` → 신규 다이얼로그 라우팅
5. `dialogs.py`: `PreflightDialog` + `DownloadProgressDialog` + `ErrorDialog` (기존 `flow_show_install_guide`는 PreflightDialog의 "수동 설치 안내" 분기로 유지)
6. `song_list_widget.py`: 편집 버튼 bundled LO fallback (~30줄)
7. About/Credits에 LibreOffice 라이선스 표기 (Flow에 별도 About 화면이 없다면 PreflightDialog 하단 표기로 대체)

### 제외 (별도 작업)

- 매니페스트 외부 호스팅 (현재 체크인)
- 자동 업그레이드 알림 시스템화 (지금은 다음 PPT 사용 때 자연스럽게 트리거)
- 사용자 설정에서 "엔진 제거" 버튼
- 언어팩 제거로 용량 다이어트 (verbatim 재배포 유지)
- macOS Gatekeeper/quarantine 자동 처리 (필요시 추가)

## 리스크 / 모름 박스

- **macOS quarantine**: 다운로드 후 실행 차단 가능. 실제 환경 검증 필요. 막히면 `xattr -d com.apple.quarantine` 추가.
- **Windows .msi 추출**: `program/` 폴더만 깔끔히 추출하는 표준 방법이 lessmsi 등 외부 도구 의존할 가능성. 검증 필요. 안 되면 silent 설치 (`msiexec /qn /a`) 후 결과 폴더만 사용.
- **TDF 미러 가용성/지역 편차**: 다운로드 실패 시 사용자가 수동 설치 fallback 가능하니 critical 아님.

## 라이선스 정리

LibreOffice는 MPL 2.0 (일부 LGPL 3.0+) — 바이너리 verbatim 재배포 합법. TDF 상표 정책상 verbatim + 무료 배포는 상표 라이선스 불필요.

의무:
- 소스 코드 접근 경로 명시 (LibreOffice 공식 소스 저장소 링크)
- LICENSE/NOTICE 파일 동봉
- Flow About/Credits에 LibreOffice 사용 명시

수정해서 재배포하려면 (예: 언어팩 제거) "based on LibreOffice"로 명칭 변경 필요. 본 설계는 verbatim 유지 → 추가 작업 없음.
