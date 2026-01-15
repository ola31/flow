"""SlideConverter - 플랫폼별 PPTX 슬라이드 이미지 변환 인터페이스"""

import abc
import os
import subprocess
import tempfile
import shutil
import hashlib
from pathlib import Path
from PySide6.QtGui import QImage
import fitz  # PyMuPDF

class SlideConverter(abc.ABC):
    """PPTX 슬라이드를 이미지로 변환하는 추상 베이스 클래스"""
    
    @abc.abstractmethod
    def get_engine_name(self) -> str:
        """현재 사용 중인 엔진의 이름을 반환"""
        pass

def _get_project_root() -> Path:
    """프로젝트 루트 디렉토리 반환"""
    return Path(__file__).parent.parent.parent.parent

def _convert_pdf_to_images(pdf_path: Path, cache_dir: Path) -> bool:
    """PDF의 모든 페이지를 고화질 PNG로 변환하여 캐시 디렉토리에 저장"""
    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        return False
        
    try:
        # with 문을 사용하여 문서가 자동으로 닫히도록 관리
        with fitz.open(str(pdf_path)) as doc:
            page_count = len(doc)
            if page_count == 0: return False
            
            for i in range(page_count):
                page = doc.load_page(i)
                # 2.0배 배율 (약 144 DPI) - 2K급 선명도 (속도와 화질의 균형)
                pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
                target = cache_dir / f"slide_{i}.png"
                pix.save(str(target))
            
        return True
    except Exception as e:
        # 가끔 subprocess 종료 직후 파일이 잠겨있을 수 있음
        if "document closed" in str(e) or "cannot open" in str(e).lower():
            import time
            time.sleep(0.5) # 잠시 대기 후 재시도 방안 고려 가능
        print(f"[SlideConverter] PDF 이미지 추출 실패: {e}")
        return False

import threading

class OnlyOfficeSlideConverter(SlideConverter):
    """ONLYOFFICE Document Builder를 사용한 독립형 변환기 (설치 불필요)"""
    
    _lock = threading.Lock() # 클래스 레벨 락으로 중복 변환 방지

    def __init__(self, executable_path: Path):
        self.exe = executable_path
        self._cache_dir = Path(tempfile.gettempdir()) / "flow_oo_cache"
        self._cache_dir.mkdir(exist_ok=True)
        
    def get_engine_name(self) -> str:
        return "ONLYOFFICE (standalone)"

    def convert_slide(self, pptx_path: Path, index: int) -> QImage:
        if not pptx_path:
            return QImage(1280, 720, QImage.Format.Format_RGB32)
        mtime = pptx_path.stat().st_mtime
        pptx_hash = hashlib.md5(f"oo_v1_{str(pptx_path.resolve())}_{mtime}".encode()).hexdigest()
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
            fonts_dir = str(app_fonts.resolve()).replace('\\', '/')
            tmp_dir = str(pptx_cache_dir.resolve()).replace('\\', '/')
            
            script_content = f"""
            builder.SetTmpFolder("{tmp_dir}");
            builder.AddFontsDir("{fonts_dir}");
            builder.OpenFile("{str(pptx_path.resolve()).replace('\\', '/')}");
            builder.SaveFile("pdf", "{str(pdf_path.resolve()).replace('\\', '/')}");
            builder.CloseFile();
            """
            script_path.write_text(script_content, encoding="utf-8")

            try:
                subprocess.run([str(self.exe), str(script_path)], check=True, capture_output=True)
                if pdf_path.exists():
                    _convert_pdf_to_images(pdf_path, pptx_cache_dir)
                else:
                    print(f"[OnlyOfficeSlideConverter] 슬라이드 {index} 변환 실패 (PDF 생성 안됨)")
            except Exception as e:
                print(f"[OnlyOfficeSlideConverter] 슬라이드 {index} 변환 실패: {e}")

        if img_path.exists():
            return QImage(str(img_path))
        return QImage(1280, 720, QImage.Format.Format_RGB32)

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

    def _check_powerpoint_installed(self) -> bool:
        if self._has_pp is not None: return self._has_pp
        try:
            from win32com import client
            import pythoncom
            pythoncom.CoInitialize()
            client.Dispatch("PowerPoint.Application")
            self._has_pp = True
        except: self._has_pp = False
        return self._has_pp

    def convert_slide(self, pptx_path: Path, index: int) -> QImage:
        if not pptx_path:
            return QImage(1280, 720, QImage.Format.Format_RGB32)
        mtime = pptx_path.stat().st_mtime
        pptx_hash = hashlib.md5(f"win_v2_{str(pptx_path.resolve())}_{mtime}".encode()).hexdigest()
        pptx_cache_dir = self._cache_dir / pptx_hash
        
        img_path = pptx_cache_dir / f"slide_{index}.png"
        if img_path.exists():
            return QImage(str(img_path))


        if not pptx_cache_dir.exists():
            pptx_cache_dir.mkdir(parents=True, exist_ok=True)

        if self._check_powerpoint_installed():
            try:
                self._convert_with_com_pdf(pptx_path, pptx_cache_dir)
            except Exception as e:
                print(f"[WindowsSlideConverter] 슬라이드 {index} 변환 실패: {e}")

        if img_path.exists():
            return QImage(str(img_path))
        
        # Fallback to LibreOffice if available
        soffice = self._find_libreoffice()
        if soffice:
            return _convert_with_libreoffice(pptx_path, index, self._cache_dir, soffice)
            
        return QImage(1280, 720, QImage.Format.Format_RGB32)

    def _convert_with_com_pdf(self, pptx_path: Path, cache_dir: Path):
        """PowerPoint COM을 사용하여 PDF로 저장 후 이미지 추출 (고속 방식)"""
        from win32com import client
        import pythoncom
        
        pdf_path = cache_dir / "temp.pdf"
        if pdf_path.exists() and (cache_dir / "slide_0.png").exists():
            return

        pythoncom.CoInitialize()
        pp = client.Dispatch("PowerPoint.Application")
        # WithWindow=False로 백그라운드 실행
        pres = pp.Presentations.Open(str(pptx_path.resolve()), WithWindow=False, ReadOnly=True)
        try:
            # 32 = ppSaveAsPDF
            pres.SaveAs(str(pdf_path.resolve()), 32)
            pres.Close()
            _convert_pdf_to_images(pdf_path, cache_dir)
        finally:
            # 파워포인트가 다른 창에서 열려있지 않다면 종료 시도 (선택적)
            # pp.Quit() # 다른 작업 중일 수 있으므로 주의해서 사용
            pass

    def _find_libreoffice(self) -> str | None:
        common_paths = [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"
        ]
        for path in common_paths:
            if Path(path).exists(): return path
        return shutil.which("soffice")

class LinuxSlideConverter(SlideConverter):
    """Linux용 변환기 (LibreOffice 기반)"""
    def __init__(self):
        self._cache_dir = Path(tempfile.gettempdir()) / "flow_linux_cache"
        self._cache_dir.mkdir(exist_ok=True)

    def get_engine_name(self) -> str:
        return "LibreOffice (Linux)"

    def convert_slide(self, pptx_path: Path, index: int) -> QImage:
        return _convert_with_libreoffice(pptx_path, index, self._cache_dir, "libreoffice")

def _convert_with_libreoffice(pptx_path: Path, index: int, cache_dir: Path, soffice_cmd: str) -> QImage:
    """LibreOffice를 사용한 공통 변환 로직"""
    if not pptx_path:
        return QImage(1280, 720, QImage.Format.Format_RGB32)
    mtime = pptx_path.stat().st_mtime
    pptx_hash = hashlib.md5(f"lo_v2_{str(pptx_path.resolve())}_{mtime}".encode()).hexdigest()
    pptx_cache_dir = cache_dir / pptx_hash
    
    img_path = pptx_cache_dir / f"slide_{index}.png"
    if img_path.exists():
        return QImage(str(img_path))


    if not pptx_cache_dir.exists():
        pptx_cache_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = pptx_cache_dir / "temp.pdf"
    if not pdf_path.exists():
        try:
            cmd = [
                soffice_cmd,
                "--headless",
                "--convert-to", "pdf",
                "--outdir", str(pptx_cache_dir),
                str(pptx_path)
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            # 생성된 파일명을 temp.pdf로 변경
            for f in pptx_cache_dir.glob("*.pdf"):
                f.replace(pdf_path)
                break
        except Exception as e:
            print(f"[SlideConverter] LibreOffice 변환 실패: {e}")

    if pdf_path.exists():
        _convert_pdf_to_images(pdf_path, pptx_cache_dir)

    if img_path.exists():
        return QImage(str(img_path))
    return QImage(1280, 720, QImage.Format.Format_RGB32)

def create_slide_converter() -> SlideConverter:
    """플랫폼 및 아키텍처를 감지하여 최적의 변환기를 선택 (Windows는 PowerPoint 우선)"""
    import sys
    import platform
    
    # OS 맵핑
    os_map = {"win32": "window", "darwin": "macos", "linux": "linux"}
    os_key = os_map.get(sys.platform, sys.platform)
    
    # 1. Windows 라면 PowerPoint COM 엔진을 최우선으로 시도 (가장 정확한 폰트 렌더링)
    if sys.platform == "win32":
        win_converter = WindowsSlideConverter()
        if win_converter._check_powerpoint_installed():
            # print("[SlideConverter] PowerPoint 엔진 사용 (Windows 권장)")
            return win_converter

    # 2. 독립 엔진(ONLYOFFICE) 탐색
    root = _get_project_root()
    search_base = root / "bin"
    target_names = ["docbuilder.exe"] if sys.platform == "win32" else ["docbuilder", "documentbuilder"]
    
    machine = platform.machine().lower()
    arch_candidates = []
    if "64" in machine or "amd64" in machine:
        arch_candidates.extend(["x64", "x86_64", "amd64"])
    if "arm" in machine or "aarch64" in machine:
        arch_candidates.extend(["arm64", "aarch64"])
    if not arch_candidates:
        arch_candidates.append("x86")

    # 아키텍처 우선 탐색
    for arch in arch_candidates:
        for target in target_names:
            for match in search_base.rglob(target):
                path_str = str(match.parent).lower()
                if os_key in path_str and arch in path_str:
                    print(f"[SlideConverter] 독립 엔진 발견: {match.relative_to(search_base)}")
                    return OnlyOfficeSlideConverter(match)

    # OS 폴더 Fallback 탐색
    for target in target_names:
        for match in search_base.rglob(target):
            if os_key in str(match.parent).lower():
                print(f"[SlideConverter] 독립 엔진 발견 (Fallback): {match.relative_to(search_base)}")
                return OnlyOfficeSlideConverter(match)

    # 3. 최후의 보루: 리눅스 기본 변환기
    if sys.platform == "win32":
        return WindowsSlideConverter() # 이미 위에서 체크했지만 구조상 유지
    return LinuxSlideConverter()

