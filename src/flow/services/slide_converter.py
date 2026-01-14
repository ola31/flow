"""SlideConverter - 플랫폼별 PPTX 슬라이드 이미지 변환 인터페이스"""

import abc
from pathlib import Path
from PySide6.QtGui import QImage

class SlideConverter(abc.ABC):
    """PPTX 슬라이드를 이미지로 변환하는 추상 베이스 클래스"""
    
    @abc.abstractmethod
    def convert_slide(self, pptx_path: Path, index: int) -> QImage:
        """특정 슬라이드를 QImage로 변환"""
        pass

import subprocess
import tempfile
import shutil
import hashlib
import fitz  # PyMuPDF

class LinuxSlideConverter(SlideConverter):
    """Linux 운영 환경용 변환기 (LibreOffice + PyMuPDF 사용)"""
    
    def __init__(self):
        self._cache_dir = Path(tempfile.gettempdir()) / "flow_ppt_cache"
        self._cache_dir.mkdir(exist_ok=True)

    def convert_slide(self, pptx_path: Path, index: int) -> QImage:
        """LibreOffice로 PDF 변환 후 PyMuPDF로 이미지 캐싱"""
        return _convert_with_libreoffice(pptx_path, index, self._cache_dir, "libreoffice")

    def _draw_error_image(self, text: str) -> QImage:
        img = QImage(1280, 720, QImage.Format.Format_RGB32)
        img.fill("#ff0000")
        return img

def _convert_with_libreoffice(pptx_path: Path, index: int, cache_dir: Path, soffice_cmd: str) -> QImage:
    """LibreOffice를 사용하여 PPTX를 PDF로 변환 후 이미지를 추출하는 공통 로직"""
    if not pptx_path or not pptx_path.exists():
        return QImage(1280, 720, QImage.Format.Format_RGB32)

    pptx_hash = hashlib.md5(str(pptx_path.resolve()).encode()).hexdigest()
    pptx_cache_dir = cache_dir / pptx_hash
    pptx_cache_dir.mkdir(exist_ok=True)
    
    img_path = pptx_cache_dir / f"slide_{index}.png"
    
    if img_path.exists():
        return QImage(str(img_path))

    try:
        pdf_path = pptx_cache_dir / "temp.pdf"
        if not pdf_path.exists():
            # [중요] 윈도우에서 LibreOffice가 이미 실행 중일 때 충돌 방지를 위해 별도 프로필 사용
            user_profile = pptx_cache_dir / "lo_profile"
            user_profile.mkdir(exist_ok=True)
            
            # 윈도우 경로 형식으로 변환
            user_profile_url = f"file:///{str(user_profile).replace('\\', '/')}"
            
            cmd = [
                soffice_cmd,
                f"-env:UserInstallation={user_profile_url}",
                "--headless",
                "--convert-to", "pdf",
                "--outdir", str(pptx_cache_dir),
                str(pptx_path)
            ]
            
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            original_pdf = pptx_cache_dir / f"{pptx_path.stem}.pdf"
            if original_pdf.exists():
                original_pdf.replace(pdf_path)
            else:
                # 가끔 파일명이 다른 경우 검색 시도
                pdf_files = list(pptx_cache_dir.glob("*.pdf"))
                if pdf_files:
                    pdf_files[0].replace(pdf_path)

        if not pdf_path.exists():
             raise RuntimeError("PDF 변환 결과 파일을 찾을 수 없습니다.")

        # PyMuPDF(fitz)를 사용하여 PDF의 모든 페이지를 이미지로 변환 및 캐싱
        doc = fitz.open(str(pdf_path))
        for i in range(len(doc)):
            page = doc.load_page(i)
            # 고해상도 변환 (2.0 = 144 DPI)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            target = pptx_cache_dir / f"slide_{i}.png"
            pix.save(str(target))
        doc.close()
        
        if img_path.exists():
            return QImage(str(img_path))
            
    except subprocess.CalledProcessError as e:
        print(f"LibreOffice 변환 명령어 실패: {e.stdout} / {e.stderr}")
    except Exception as e:
        print(f"LibreOffice 변환 에러: {e}")
        
    return QImage(1280, 720, QImage.Format.Format_RGB32)

class WindowsSlideConverter(SlideConverter):
    """Windows 운영 환경용 변환기 (PowerPoint COM -> LibreOffice fallback)"""
    
    def __init__(self):
        self._temp_dir = Path(tempfile.gettempdir()) / "flow_ppt_win"
        self._temp_dir.mkdir(exist_ok=True)
        self._has_pp = None # None: 미확인, True/False: 확인됨
        self._soffice_path = self._find_libreoffice()

    def _find_libreoffice(self) -> str | None:
        """윈도우에서 LibreOffice 실행 파일 경로 탐색"""
        common_paths = [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"
        ]
        for path in common_paths:
            if Path(path).exists():
                return path
        
        # PATH 환경변수 확인
        which_path = shutil.which("soffice")
        return which_path

    def _check_powerpoint_installed(self) -> bool:
        """PowerPoint 설치 여부 확인"""
        if self._has_pp is not None:
            return self._has_pp
            
        import pythoncom
        from win32com import client
        
        pythoncom.CoInitialize()
        try:
            # 단순히 Dispatch만 시도하여 설치 여부 확인
            pp = client.Dispatch("PowerPoint.Application")
            self._has_pp = True
            return True
        except Exception:
            self._has_pp = False
            return False

    def convert_slide(self, pptx_path: Path, index: int) -> QImage:
        """PowerPoint가 있으면 COM 사용, 없으면 LibreOffice 사용"""
        
        # 1. PowerPoint 사용 시도
        if self._check_powerpoint_installed():
            try:
                return self._convert_with_com(pptx_path, index)
            except Exception as e:
                print(f"PowerPoint COM 변환 실패, Fallback 시도: {e}")
        
        # 2. LibreOffice 사용 시도
        if self._soffice_path:
            return _convert_with_libreoffice(pptx_path, index, self._temp_dir, self._soffice_path)
            
        # 3. 모두 실패 시 에러 이미지
        print("에러: PowerPoint 또는 LibreOffice를 찾을 수 없습니다.")
        return QImage(1280, 720, QImage.Format.Format_RGB32)

    def _convert_with_com(self, pptx_path: Path, index: int) -> QImage:
        """기존 PowerPoint COM 방식 로직"""
        import pythoncom
        from win32com import client
        
        pptx_hash = hashlib.md5(str(pptx_path.resolve()).encode()).hexdigest()
        pptx_cache_dir = self._temp_dir / pptx_hash
        pptx_cache_dir.mkdir(exist_ok=True)
        
        img_path = pptx_cache_dir / f"Slide{index + 1}.PNG"
        if img_path.exists():
            return QImage(str(img_path))

        pythoncom.CoInitialize()
        pp = client.Dispatch("PowerPoint.Application")
        pres = pp.Presentations.Open(str(pptx_path.resolve()), WithWindow=False, ReadOnly=True)
        try:
            pres.Export(str(pptx_cache_dir), "PNG", 1920, 1080)
            if img_path.exists():
                return QImage(str(img_path))
        finally:
            pres.Close()
        
        return QImage(1280, 720, QImage.Format.Format_RGB32)
