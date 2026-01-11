"""SlideManager - PPTX 슬라이드를 이미지로 관리하는 서비스"""

import time
from pathlib import Path
from PySide6.QtCore import QObject, Signal
from pptx import Presentation
from pptx.exc import PackageNotFoundError
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import sys
from flow.services.slide_converter import SlideConverter, LinuxSlideConverter, WindowsSlideConverter

class SlideLoadError(Exception):
    """PPTX 로드 실패 예외"""
    pass

class SlideUpdateHandler(FileSystemEventHandler):
    """파일 변경 이벤트 핸들러"""
    def __init__(self, target_path, callback):
        self.target_path = Path(target_path).resolve()
        self.callback = callback
        self.last_triggered = 0
        
    def on_modified(self, event):
        if event.is_directory:
            return
        
        # 특정 파일만 감시
        if Path(event.src_path).resolve() != self.target_path:
            return
            
        # 짧은 시간에 여러 번 발생하는 이벤트 방지 (Debounce)
        now = time.time()
        if now - self.last_triggered > 0.1:
            self.callback()
            self.last_triggered = now

class SlideManager(QObject):
    """PPTX 파일을 로드하고 슬라이드 이미지를 관리함"""
    
    file_changed = Signal()  # 파일 변경 시 발생
    
    def __init__(self, converter: SlideConverter = None) -> None:
        super().__init__()
        self._pptx_path: Path | None = None
        self._slide_count: int = 0
        if converter:
            self._converter = converter
        elif sys.platform == "win32":
            self._converter = WindowsSlideConverter()
        else:
            self._converter = LinuxSlideConverter()
        self._observer = None
        
    def load_pptx(self, path: str | Path) -> int:
        """PPTX 파일을 로드하고 슬라이드 개수 반환"""
        # 경로 정규화 및 존재 여부 확인
        p = Path(path).resolve() if path and str(path).strip() else None
        
        # 최적화: 이미 같은 파일이 로드되어 있다면 즉시 반환
        if p == self._pptx_path and self._slide_count > 0:
            return self._slide_count
            
        self._pptx_path = p
        
        if p and p.is_file():
            try:
                prs = Presentation(str(p))
                self._slide_count = len(prs.slides)
            except PackageNotFoundError:
                self._slide_count = 0
                raise SlideLoadError(f"올바른 PPTX 형식이 아닙니다: {path}\n단순히 확장자만 바꾸는 것으로는 충분하지 않습니다. '다른 이름으로 저장'을 통해 PPTX로 변환해 주세요.")
            except Exception as e:
                self._slide_count = 0
                raise SlideLoadError(f"PPTX 로드 중 오류 발생: {e}")
        else:
            self._slide_count = 0
            if p and p.exists():
                 raise SlideLoadError(f"경로가 파일이 아닙니다: {path}")
        return self._slide_count
    
    def get_slide_count(self) -> int:
        """현재 로드된 슬라이드 개수 반환"""
        return self._slide_count
    
    def get_slide_image(self, index: int):
        """특정 슬라이드의 이미지를 반환"""
        if self._converter:
            return self._converter.convert_slide(self._pptx_path, index)
        raise RuntimeError("이미지 변환기가 설정되지 않았습니다.")

    def start_watching(self, path: str | Path = None):
        """파일 변경 감시 시작"""
        if path:
            self._pptx_path = Path(path)
        
        if not self._pptx_path or not self._pptx_path.parent.exists():
            return

        self.stop_watching()
        
        self._pptx_path = self._pptx_path.resolve()
        self._observer = Observer()
        handler = SlideUpdateHandler(self._pptx_path, self.file_changed.emit)
        self._observer.schedule(handler, str(self._pptx_path.parent), recursive=False)
        self._observer.start()
        time.sleep(0.1)  # 감시자 시작 대기
        
    def stop_watching(self):
        """파일 감시 중지"""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
