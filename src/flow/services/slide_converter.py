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
from pdf2image import convert_from_path

class LinuxSlideConverter(SlideConverter):
    """Linux 운영 환경용 변환기 (LibreOffice + pdf2image 사용)"""
    
    def __init__(self):
        self._cache_dir = Path(tempfile.gettempdir()) / "flow_ppt_cache"
        self._cache_dir.mkdir(exist_ok=True)
        self._current_pdf = None
        self._current_pptx = None

    def convert_slide(self, pptx_path: Path, index: int) -> QImage:
        """LibreOffice로 PDF 변환 후 모든 슬라이드를 이미지 파일로 캐싱"""
        if not pptx_path or not pptx_path.exists():
            return self._draw_error_image("파일 없음")

        # 캐시 디렉토리 구조: flow_ppt_cache/{pptx_hash}/slide_{index}.png
        import hashlib
        pptx_hash = hashlib.md5(str(pptx_path.resolve()).encode()).hexdigest()
        pptx_cache_dir = self._cache_dir / pptx_hash
        pptx_cache_dir.mkdir(exist_ok=True)
        
        img_path = pptx_cache_dir / f"slide_{index}.png"
        
        # 1. 이미 캐싱된 파일이 있으면 즉시 반환 (매우 빠름)
        if img_path.exists():
            return QImage(str(img_path))

        # 2. 캐시가 없으면 일괄 변환 수행
        try:
            # 먼저 PDF가 있는지 확인 (없으면 생성)
            pdf_path = pptx_cache_dir / "temp.pdf"
            if not pdf_path.exists():
                subprocess.run([
                    "libreoffice", "--headless", 
                    "--convert-to", "pdf", 
                    "--outdir", str(pptx_cache_dir),
                    str(pptx_path)
                ], check=True, capture_output=True)
                # LibreOffice는 원본 파일명.pdf로 저장하므로 이름 변경
                original_pdf = pptx_cache_dir / f"{pptx_path.stem}.pdf"
                if original_pdf.exists():
                    original_pdf.replace(pdf_path)

            # PDF 전체를 이미지로 변환하여 캐시 디렉토리에 저장
            # (CPU 코어 사용 옵션 등을 추가할 수 있으나 여기서는 단순 구현)
            images = convert_from_path(
                str(pdf_path),
                output_folder=str(pptx_cache_dir),
                fmt="png",
                output_file="slide", # slide-1.png, slide-2.png 형식으로 저장됨
                paths_only=True      # 파일 경로만 반환받아 메모리 절약
            )
            
            # pdf2image 명명 규칙(slide-1.png)을 우리 규칙(slide_0.png)으로 정리하거나 그대로 사용
            # 여기서는 파일 중 하나를 반환
            for i, path in enumerate(sorted(images)):
                target = pptx_cache_dir / f"slide_{i}.png"
                if not target.exists():
                    Path(path).replace(target)
            
            if img_path.exists():
                return QImage(str(img_path))
                
        except Exception as e:
            print(f"Linux PPT 최적화 변환 실패: {e}")
            
        return self._draw_error_image(f"변환 실패 (Page {index+1})")

    def _draw_error_image(self, text: str) -> QImage:
        """오류 시 표시할 이미지"""
        img = QImage(1280, 720, QImage.Format.Format_RGB32)
        img.fill("#ff0000")
        # 텍스트 그리는 로직은 생략하거나 간단히 구현
        return img

class WindowsSlideConverter(SlideConverter):
    """Windows 운영 환경용 변환기 (PowerPoint COM 사용)"""
    
    def __init__(self):
        self._temp_dir = Path(tempfile.gettempdir()) / "flow_ppt_win"
        self._temp_dir.mkdir(exist_ok=True)

    def convert_slide(self, pptx_path: Path, index: int) -> QImage:
        """PowerPoint COM을 사용하여 전체 슬라이드를 한 번에 캐싱"""
        import pythoncom
        from win32com import client
        import hashlib
        
        # 캐시 경로 설정
        pptx_hash = hashlib.md5(str(pptx_path.resolve()).encode()).hexdigest()
        pptx_cache_dir = self._temp_dir / pptx_hash
        pptx_cache_dir.mkdir(exist_ok=True)
        
        img_path = pptx_cache_dir / f"slide_{index + 1}.PNG" # PPT Export는 slide_1.PNG 형식임
        
        # 1. 캐시 확인
        if img_path.exists():
            return QImage(str(img_path))

        # 2. 일괄 Export 수행
        pythoncom.CoInitialize()
        try:
            pp = client.Dispatch("PowerPoint.Application")
            pres = pp.Presentations.Open(str(pptx_path.resolve()), WithWindow=False, ReadOnly=True)
            
            try:
                # 폴더 전체를 지정하여 모든 슬라이드 내보내기
                # Export(Path, FilterName, Width, Height)
                pres.Export(str(pptx_cache_dir), "PNG", 1920, 1080)
                
                # 내보낸 후 파일명이 Slide1.PNG 등으로 생성됨을 확인하여 규칙에 맞게 반환하거나 로드
                # (Windows PowerPoint 버전에 따라 파일명이 다를 수 있으므로 유연하게 대처)
                possible_path = pptx_cache_dir / f"Slide{index + 1}.PNG"
                if possible_path.exists():
                    return QImage(str(possible_path))
                    
            finally:
                pres.Close()
        except Exception as e:
            print(f"Windows PPT 일괄 변환 실패: {e}")
            
        return QImage(1280, 720, QImage.Format.Format_RGB32)
