"""SlideConverter - 플랫폼별 PPTX 슬라이드 이미지 변환 인터페이스"""
from __future__ import annotations

import abc
import hashlib
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

import fitz  # PyMuPDF
from PySide6.QtGui import QImage


class NoConverterAvailableError(RuntimeError):
    """PPT 변환에 사용할 엔진을 시스템에서 찾지 못했을 때.

    PowerPoint, LibreOffice, ONLYOFFICE 모두 부재일 때 발생.
    UI 레이어에서 catch해서 설치 안내 다이얼로그를 띄워야 한다.
    """

    def __init__(self, platform_name: str = ""):
        self.platform_name = platform_name or sys.platform
        super().__init__(
            f"No PPT conversion engine found on {self.platform_name}. "
            f"Install Microsoft PowerPoint or LibreOffice."
        )


class SlideConverter(abc.ABC):
    """PPTX 슬라이드를 이미지로 변환하는 추상 베이스 클래스"""

    @abc.abstractmethod
    def get_engine_name(self) -> str:
        """현재 사용 중인 엔진의 이름을 반환"""
        pass

    @abc.abstractmethod
    def convert_slide(
        self, pptx_path: Path, index: int, status_callback=None
    ) -> QImage:
        """특정 슬라이드를 이미지로 변환"""
        pass

    @abc.abstractmethod
    def invalidate_cache(self, pptx_path: Path) -> None:
        """특정 PPTX 파일의 캐시 삭제"""
        pass

    @abc.abstractmethod
    def clear_cache(self) -> None:
        """전체 캐시 삭제"""
        pass


def _get_project_root() -> Path:
    """프로젝트 루트 디렉토리 반환"""
    return Path(__file__).parent.parent.parent.parent


_GLOBAL_CONVERT_LOCK = threading.Lock()

# Target output resolution for PDF→PNG conversion.
# Synced to ConfigService.get_output_resolution() via set_target_size() at app
# startup so PPT- and markdown-sourced slides share the same target.
_target_size: tuple[int, int] = (1920, 1080)


def set_target_size(size: tuple[int, int]) -> None:
    """Set target output resolution for converted slide images."""
    global _target_size
    _target_size = (int(size[0]), int(size[1]))

# Target output resolution for converted slide images. Matches the markdown
# renderer's default `Frontmatter.resolution` so PPT- and markdown-sourced
# slides are visually interchangeable downstream.
_TARGET_WIDTH = 1920
_TARGET_HEIGHT = 1080


def _trim_pdf_edge_artifacts(png_path: Path, max_trim: int = 3) -> None:
    """PDF→PNG 변환 시 페이지 경계로 생기는 1~2px 흰 줄을 잘라낸다.

    LibreOffice가 PDF에 페이지 boundary를 그리고 PyMuPDF가 이를 흰
    픽셀로 렌더링하면, 송출 시 슬라이드 가장자리에 흰 선이 보임.
    각 가장자리 행/열 중 평균 밝기가 250+ 인 것만 트리밍 (콘텐츠 손실 방지).
    """
    try:
        from PIL import Image
        img = Image.open(str(png_path))
        if img.mode != "RGB":
            img = img.convert("RGB")
        w, h = img.size
        if w < 10 or h < 10:
            return

        def _row_is_white(y: int) -> bool:
            # 32개 샘플로 가장자리 행 판정 (전체 스캔보다 빠름)
            xs = [int(x * (w - 1) / 31) for x in range(32)]
            return all(
                sum(img.getpixel((x, y))) >= 250 * 3 for x in xs
            )

        def _col_is_white(x: int) -> bool:
            ys = [int(y * (h - 1) / 31) for y in range(32)]
            return all(
                sum(img.getpixel((x, y))) >= 250 * 3 for y in ys
            )

        top = 0
        while top < max_trim and _row_is_white(top):
            top += 1
        bottom = h
        while bottom > h - max_trim and _row_is_white(bottom - 1):
            bottom -= 1
        left = 0
        while left < max_trim and _col_is_white(left):
            left += 1
        right = w
        while right > w - max_trim and _col_is_white(right - 1):
            right -= 1

        if (top, left, bottom, right) != (0, 0, h, w):
            cropped = img.crop((left, top, right, bottom))
            cropped.save(str(png_path))
    except Exception:
        # 트리밍 실패는 silent — 원본 유지
        pass


def _convert_pdf_to_images(
    pdf_path: Path, cache_dir: Path, status_callback=None
) -> bool:
    """PDF의 모든 페이지를 고화질 PNG로 변환하여 캐시 디렉토리에 저장"""
    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        return False

    with _GLOBAL_CONVERT_LOCK:
        try:
            with fitz.open(str(pdf_path)) as doc:
                page_count = len(doc)
                if page_count == 0:
                    return False

                target_w, target_h = _target_size
                for i in range(page_count):
                    if status_callback:
                        status_callback(f"이미지 추출 중 ({i + 1}/{page_count})...")

                    page = doc.load_page(i)

                    rect = page.rect  # in points (1/72 inch)
                    sx = target_w / rect.width if rect.width > 0 else 2.0
                    sy = target_h / rect.height if rect.height > 0 else 2.0
                    pix = page.get_pixmap(
                        matrix=fitz.Matrix(sx, sy),
                        colorspace=fitz.csRGB,
                        alpha=False,
                    )

                    target = cache_dir / f"slide_{i}.png"
                    pix.save(str(target))
                    _trim_pdf_edge_artifacts(target)

            return True
        except Exception as e:
            # 가끔 subprocess 종료 직후 파일이 잠겨있을 수 있음
            if "document closed" in str(e) or "cannot open" in str(e).lower():
                import time

                time.sleep(0.5)
            return False


class OnlyOfficeSlideConverter(SlideConverter):
    """ONLYOFFICE Document Builder를 사용한 독립형 변환기 (설치 불필요)"""

    _lock = threading.Lock()  # 클래스 레벨 락으로 중복 변환 방지

    def __init__(self, executable_path: Path):
        self.exe = executable_path
        self._cache_dir = Path(tempfile.gettempdir()) / "flow_oo_cache"
        self._cache_dir.mkdir(exist_ok=True)

    def get_engine_name(self) -> str:
        return "ONLYOFFICE (standalone)"

    def _get_cache_dir_for_pptx(self, pptx_path: Path) -> Path | None:
        if not pptx_path or not pptx_path.exists():
            return None
        mtime = pptx_path.stat().st_mtime
        pptx_hash = hashlib.md5(
            f"oo_v1_{str(pptx_path.resolve())}_{mtime}_{_target_size[0]}x{_target_size[1]}".encode()
        ).hexdigest()
        return self._cache_dir / pptx_hash

    def invalidate_cache(self, pptx_path: Path) -> None:
        for item in self._cache_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)

    def clear_cache(self) -> None:
        if self._cache_dir.exists():
            shutil.rmtree(self._cache_dir, ignore_errors=True)
            self._cache_dir.mkdir(exist_ok=True)

    def convert_slide(
        self, pptx_path: Path, index: int, status_callback=None
    ) -> QImage:
        if not pptx_path:
            return QImage(1280, 720, QImage.Format.Format_RGB32)
        mtime = pptx_path.stat().st_mtime
        pptx_hash = hashlib.md5(
            f"oo_v1_{str(pptx_path.resolve())}_{mtime}_{_target_size[0]}x{_target_size[1]}".encode()
        ).hexdigest()
        pptx_cache_dir = self._cache_dir / pptx_hash

        img_path = pptx_cache_dir / f"slide_{index}.png"
        if img_path.exists():
            return QImage(str(img_path))

        with self._lock:
            # 락 획득 후 다시 한번 확인 (대기하는 동안 다른 스레드가 완료했을 수 있음)
            if img_path.exists():
                return QImage(str(img_path))

            if not pptx_cache_dir.exists():
                pptx_cache_dir.mkdir(parents=True, exist_ok=True)

            script_path = pptx_cache_dir / "convert.docbuilder"
            pdf_path = pptx_cache_dir / "temp.pdf"

            # 폰트 경로 설정 (무거운 시스템 전체 스캔 대신 assets/fonts만 지정)
            root = _get_project_root()
            app_fonts = root / "assets" / "fonts"
            fonts_dir = str(app_fonts.resolve()).replace("\\", "/")
            tmp_dir = str(pptx_cache_dir.resolve()).replace("\\", "/")

            script_content = f"""
            builder.SetTmpFolder("{tmp_dir}");
            builder.AddFontsDir("{fonts_dir}");
            builder.OpenFile("{str(pptx_path.resolve()).replace("\\", "/")}");
            builder.SaveFile("pdf", "{str(pdf_path.resolve()).replace("\\", "/")}");
            builder.CloseFile();
            """
            script_path.write_text(script_content, encoding="utf-8")

            try:
                if status_callback:
                    status_callback("ONLYOFFICE 엔진으로 PDF 변환 중...")
                subprocess.run(
                    [str(self.exe), str(script_path)], check=True, capture_output=True
                )
                if pdf_path.exists():
                    _convert_pdf_to_images(
                        pdf_path, pptx_cache_dir, status_callback=status_callback
                    )
                else:
                    print(
                        f"[OnlyOfficeSlideConverter] 슬라이드 {index} 변환 실패 (PDF 생성 안됨)"
                    )
            except Exception as e:
                print(f"[OnlyOfficeSlideConverter] 슬라이드 {index} 변환 실패: {e}")

        if img_path.exists():
            return QImage(str(img_path))
        from PySide6.QtCore import Qt

        img = QImage(1280, 720, QImage.Format.Format_RGB32)
        img.fill(Qt.GlobalColor.black)
        return img


class WindowsSlideConverter(SlideConverter):
    """Windows용 변환기 (PowerPoint PDF 변환 -> PyMuPDF 추출)"""

    def __init__(self):
        self._cache_dir = Path(tempfile.gettempdir()) / "flow_win_cache"
        self._cache_dir.mkdir(exist_ok=True)
        self._has_pp = None

    def get_engine_name(self) -> str:
        if self._check_powerpoint_installed():
            return "PowerPoint (installed)"
        return "LibreOffice (installed)"

    def invalidate_cache(self, pptx_path: Path) -> None:
        for item in self._cache_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)

    def clear_cache(self) -> None:
        if self._cache_dir.exists():
            shutil.rmtree(self._cache_dir, ignore_errors=True)
            self._cache_dir.mkdir(exist_ok=True)

    def _check_powerpoint_installed(self) -> bool:
        if self._has_pp is not None:
            return self._has_pp
        try:
            from win32com import client
            import pythoncom

            pythoncom.CoInitialize()
            client.Dispatch("PowerPoint.Application")
            self._has_pp = True
        except:
            self._has_pp = False
        return self._has_pp

    def convert_slide(
        self, pptx_path: Path, index: int, status_callback=None
    ) -> QImage:
        if not pptx_path:
            return QImage(1280, 720, QImage.Format.Format_RGB32)
        mtime = pptx_path.stat().st_mtime
        pptx_hash = hashlib.md5(
            f"win_v2_{str(pptx_path.resolve())}_{mtime}_{_target_size[0]}x{_target_size[1]}".encode()
        ).hexdigest()
        pptx_cache_dir = self._cache_dir / pptx_hash

        img_path = pptx_cache_dir / f"slide_{index}.png"
        if img_path.exists():
            return QImage(str(img_path))

        if not pptx_cache_dir.exists():
            pptx_cache_dir.mkdir(parents=True, exist_ok=True)

        if self._check_powerpoint_installed():
            try:
                self._convert_with_com_pdf(
                    pptx_path, pptx_cache_dir, status_callback=status_callback
                )
            except Exception as e:
                print(f"[WindowsSlideConverter] 슬라이드 {index} 변환 실패: {e}")

        if img_path.exists():
            return QImage(str(img_path))

        # Fallback to LibreOffice if available
        soffice = self._find_libreoffice()
        if soffice:
            return _convert_with_libreoffice(
                pptx_path,
                index,
                self._cache_dir,
                soffice,
                status_callback=status_callback,
            )

        return QImage(1280, 720, QImage.Format.Format_RGB32)

    def _convert_with_com_pdf(
        self, pptx_path: Path, cache_dir: Path, status_callback=None
    ):
        """PowerPoint COM을 사용하여 PDF로 저장 후 이미지 추출 (고속 방식)"""
        from win32com import client
        import pythoncom

        pdf_path = cache_dir / "temp.pdf"
        if pdf_path.exists() and (cache_dir / "slide_0.png").exists():
            return

        if status_callback:
            status_callback("PowerPoint 엔진을 사용하여 PDF 변환 중...")

        pythoncom.CoInitialize()
        pp = client.Dispatch("PowerPoint.Application")
        # WithWindow=False로 백그라운드 실행
        pres = pp.Presentations.Open(
            str(pptx_path.resolve()), WithWindow=False, ReadOnly=True
        )
        try:
            # 32 = ppSaveAsPDF
            pres.SaveAs(str(pdf_path.resolve()), 32)
            pres.Close()
            _convert_pdf_to_images(pdf_path, cache_dir, status_callback=status_callback)
        finally:
            # 파워포인트가 다른 창에서 열려있지 않다면 종료 시도 (선택적)
            # pp.Quit() # 다른 작업 중일 수 있으므로 주의해서 사용
            pass

    def _find_libreoffice(self) -> str | None:
        common_paths = [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ]
        for path in common_paths:
            if Path(path).exists():
                return path
        return shutil.which("soffice")


class LinuxSlideConverter(SlideConverter):
    """Linux용 변환기 (LibreOffice 기반)"""

    def __init__(self):
        self._cache_dir = Path(tempfile.gettempdir()) / "flow_linux_cache"
        self._cache_dir.mkdir(exist_ok=True)

    def get_engine_name(self) -> str:
        return "LibreOffice (Linux)"

    def convert_slide(
        self, pptx_path: Path, index: int, status_callback=None
    ) -> QImage:
        return _convert_with_libreoffice(
            pptx_path,
            index,
            self._cache_dir,
            "libreoffice",
            status_callback=status_callback,
        )

    def invalidate_cache(self, pptx_path: Path) -> None:
        for item in self._cache_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)

    def clear_cache(self) -> None:
        if self._cache_dir.exists():
            shutil.rmtree(self._cache_dir, ignore_errors=True)
            self._cache_dir.mkdir(exist_ok=True)


class MacOSSlideConverter(SlideConverter):
    """macOS용 변환기 — PowerPoint(AppleScript) → LibreOffice fallback."""

    def __init__(self):
        self._cache_dir = Path(tempfile.gettempdir()) / "flow_macos_cache"
        self._cache_dir.mkdir(exist_ok=True)
        self._has_pp = None
        self._soffice_path = None

    def get_engine_name(self) -> str:
        if self._check_powerpoint_installed():
            return "PowerPoint (macOS)"
        return "LibreOffice (macOS)"

    def _check_powerpoint_installed(self) -> bool:
        if self._has_pp is not None:
            return self._has_pp
        # macOS PowerPoint는 보통 /Applications/Microsoft PowerPoint.app 경로
        candidates = [
            Path("/Applications/Microsoft PowerPoint.app"),
            Path.home() / "Applications" / "Microsoft PowerPoint.app",
        ]
        self._has_pp = any(p.exists() for p in candidates)
        return self._has_pp

    def _find_libreoffice(self) -> str | None:
        if self._soffice_path is not None:
            return self._soffice_path or None
        candidates = [
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",
            str(Path.home() / "Applications/LibreOffice.app/Contents/MacOS/soffice"),
        ]
        for c in candidates:
            if Path(c).exists():
                self._soffice_path = c
                return c
        from_path = shutil.which("soffice") or shutil.which("libreoffice")
        self._soffice_path = from_path or ""
        return from_path

    def invalidate_cache(self, pptx_path: Path) -> None:
        for item in self._cache_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)

    def clear_cache(self) -> None:
        if self._cache_dir.exists():
            shutil.rmtree(self._cache_dir, ignore_errors=True)
            self._cache_dir.mkdir(exist_ok=True)

    def convert_slide(
        self, pptx_path: Path, index: int, status_callback=None
    ) -> QImage:
        if not pptx_path:
            return QImage(1280, 720, QImage.Format.Format_RGB32)

        mtime = pptx_path.stat().st_mtime
        pptx_hash = hashlib.md5(
            f"mac_v1_{str(pptx_path.resolve())}_{mtime}_{_target_size[0]}x{_target_size[1]}".encode()
        ).hexdigest()
        pptx_cache_dir = self._cache_dir / pptx_hash

        img_path = pptx_cache_dir / f"slide_{index}.png"
        if img_path.exists():
            return QImage(str(img_path))

        if not pptx_cache_dir.exists():
            pptx_cache_dir.mkdir(parents=True, exist_ok=True)

        if self._check_powerpoint_installed():
            try:
                self._convert_with_applescript(
                    pptx_path, pptx_cache_dir, status_callback=status_callback
                )
            except Exception as e:
                print(f"[MacOSSlideConverter] PowerPoint 변환 실패: {e}")

        if img_path.exists():
            return QImage(str(img_path))

        soffice = self._find_libreoffice()
        if soffice:
            return _convert_with_libreoffice(
                pptx_path,
                index,
                self._cache_dir,
                soffice,
                status_callback=status_callback,
            )

        return QImage(1280, 720, QImage.Format.Format_RGB32)

    def _convert_with_applescript(
        self, pptx_path: Path, cache_dir: Path, status_callback=None
    ):
        """macOS PowerPoint에 AppleScript를 보내 PDF로 저장 후 이미지 추출."""
        pdf_path = cache_dir / "temp.pdf"
        if pdf_path.exists() and (cache_dir / "slide_0.png").exists():
            return

        if status_callback:
            status_callback("PowerPoint(macOS) 엔진을 사용하여 PDF 변환 중...")

        # AppleScript로 PPT를 PDF로 export
        script = f'''
        tell application "Microsoft PowerPoint"
            activate
            set ppFile to POSIX file "{pptx_path.resolve()}" as alias
            open ppFile
            set pdfFile to POSIX file "{pdf_path.resolve()}"
            save active presentation in pdfFile as save as PDF
            close active presentation saving no
        end tell
        '''
        subprocess.run(
            ["osascript", "-e", script], check=True, capture_output=True, timeout=120
        )
        if pdf_path.exists():
            _convert_pdf_to_images(pdf_path, cache_dir, status_callback=status_callback)


# ─── 엔진 감지 헬퍼 (모든 OS) ────────────────────────────────────────────────

def _detect_powerpoint() -> bool:
    """현재 OS에서 PowerPoint가 설치되어 있는지 감지."""
    if sys.platform == "win32":
        try:
            from win32com import client
            import pythoncom
            pythoncom.CoInitialize()
            client.Dispatch("PowerPoint.Application")
            return True
        except Exception:
            return False
    if sys.platform == "darwin":
        candidates = [
            Path("/Applications/Microsoft PowerPoint.app"),
            Path.home() / "Applications" / "Microsoft PowerPoint.app",
        ]
        return any(p.exists() for p in candidates)
    return False  # Linux PowerPoint 없음


def _detect_libreoffice() -> str | None:
    """LibreOffice 실행 파일 경로를 반환. 없으면 None."""
    if sys.platform == "win32":
        for p in (
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ):
            if Path(p).exists():
                return p
    elif sys.platform == "darwin":
        for p in (
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",
            str(Path.home() / "Applications/LibreOffice.app/Contents/MacOS/soffice"),
        ):
            if Path(p).exists():
                return p
    # PATH 검색 (모든 OS)
    return shutil.which("soffice") or shutil.which("libreoffice")


def _convert_with_libreoffice(
    pptx_path: Path, index: int, cache_dir: Path, soffice_cmd: str, status_callback=None
) -> QImage:
    """LibreOffice를 사용한 공통 변환 로직 (디버깅 강화)"""
    from PySide6.QtCore import Qt

    if not pptx_path:
        img = QImage(1280, 720, QImage.Format.Format_RGB32)
        img.fill(Qt.GlobalColor.black)
        return img

    mtime = pptx_path.stat().st_mtime
    pptx_hash = hashlib.md5(
        f"lo_v10_{str(pptx_path.resolve())}_{mtime}_{_target_size[0]}x{_target_size[1]}".encode()
    ).hexdigest()
    pptx_cache_dir = cache_dir / pptx_hash

    img_path = pptx_cache_dir / f"slide_{index}.png"
    if img_path.exists():
        return QImage(str(img_path))

    if not pptx_cache_dir.exists():
        pptx_cache_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = pptx_cache_dir / "temp.pdf"
    if not pdf_path.exists():
        if status_callback:
            status_callback("PPT 구조 분석 및 PDF 변환 중...")
        try:
            # -env:UserInstallation을 사용하여 인스턴스 충돌 방지 (Linux 필수)
            user_install_dir = pptx_cache_dir / "lo_user"
            user_install_dir.mkdir(exist_ok=True)

            cmd = [
                soffice_cmd,
                f"-env:UserInstallation=file://{user_install_dir.resolve()}",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(pptx_cache_dir.resolve()),
                str(pptx_path.resolve()),
            ]
            subprocess.run(cmd, check=True, capture_output=True)

            # 생성된 PDF 찾기
            for f in pptx_cache_dir.glob("*.pdf"):
                if f.name != "temp.pdf":
                    if pdf_path.exists():
                        pdf_path.unlink()
                    f.replace(pdf_path)
                    break
        except:
            pass

    if pdf_path.exists():
        _convert_pdf_to_images(
            pdf_path, pptx_cache_dir, status_callback=status_callback
        )

    if img_path.exists():
        return QImage(str(img_path))

    from PySide6.QtCore import Qt

    img = QImage(1280, 720, QImage.Format.Format_RGB32)
    img.fill(Qt.GlobalColor.black)
    return img


def _find_bundled_onlyoffice() -> Path | None:
    """프로젝트 bin/ 폴더에 동봉된 ONLYOFFICE DocBuilder를 탐색."""
    os_map = {"win32": "window", "darwin": "macos", "linux": "linux"}
    os_key = os_map.get(sys.platform, sys.platform)

    root = _get_project_root()
    search_base = root / "bin"
    if not search_base.exists():
        return None

    target_names = (
        ["docbuilder.exe"]
        if sys.platform == "win32"
        else ["docbuilder", "documentbuilder"]
    )

    machine = platform.machine().lower()
    arch_candidates = []
    if "64" in machine or "amd64" in machine:
        arch_candidates.extend(["x64", "x86_64", "amd64"])
    if "arm" in machine or "aarch64" in machine:
        arch_candidates.extend(["arm64", "aarch64"])
    if not arch_candidates:
        arch_candidates.append("x86")

    for arch in arch_candidates:
        for target in target_names:
            for match in search_base.rglob(target):
                path_str = str(match.parent).lower()
                if os_key in path_str and arch in path_str:
                    return match
    for target in target_names:
        for match in search_base.rglob(target):
            if os_key in str(match.parent).lower():
                return match
    return None


class MarkdownSlideConverter(SlideConverter):
    """Renders Flow markdown slide files to images using Qt only."""

    def __init__(self) -> None:
        self._cache: dict[Path, list] = {}

    def get_engine_name(self) -> str:
        return "Markdown"

    def get_slide_count(self, md_path: Path) -> int:
        return len(self._slides_for(md_path))

    def convert_slide(self, md_path: Path, index: int, status_callback=None) -> QImage:
        slides = self._slides_for(md_path)
        return slides[index]

    def invalidate_cache(self, md_path: Path) -> None:
        self._cache.pop(Path(md_path).resolve(), None)

    def clear_cache(self) -> None:
        self._cache.clear()

    def _slides_for(self, md_path: Path) -> list:
        from flow.services.markdown import parse, render_all

        key = Path(md_path).resolve()
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        text = key.read_text(encoding="utf-8")
        spec = parse(text)
        images = render_all(spec, song_dir=key.parent)
        self._cache[key] = images
        return images


def create_slide_converter() -> SlideConverter:
    """OS를 먼저 판별하고, 그 안에서 PowerPoint → 동봉 LibreOffice → 시스템
    LibreOffice → 동봉 ONLYOFFICE 순으로 사용 가능한 첫 엔진을 선택해 변환기를
    반환한다.

    Raises:
        NoConverterAvailableError: 어떤 엔진도 찾지 못한 경우.
    """
    has_pp = _detect_powerpoint()
    has_system_lo = _detect_libreoffice() is not None
    bundled_oo = _find_bundled_onlyoffice()

    if sys.platform == "win32":
        if has_pp or has_system_lo:
            return WindowsSlideConverter()
        if bundled_oo is not None:
            return OnlyOfficeSlideConverter(bundled_oo)
    elif sys.platform == "darwin":
        if has_pp or has_system_lo:
            return MacOSSlideConverter()
        if bundled_oo is not None:
            return OnlyOfficeSlideConverter(bundled_oo)
    else:  # linux 및 기타
        if has_system_lo:
            return LinuxSlideConverter()
        if bundled_oo is not None:
            return OnlyOfficeSlideConverter(bundled_oo)

    raise NoConverterAvailableError(sys.platform)
