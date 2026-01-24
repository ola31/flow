"""SlideManager - PPTX 슬라이드를 이미지로 관리하는 서비스"""

import time
from pathlib import Path
from PySide6.QtCore import QObject, Signal
from pptx import Presentation
from pptx.exc import PackageNotFoundError
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import sys
from flow.services.slide_converter import SlideConverter, create_slide_converter

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

from PySide6.QtCore import QObject, Signal, QThread

class PPTLoadWorker(QThread):
    """PPT 로딩을 백그라운드에서 수행하는 워커"""
    finished = Signal(int)          # 슬라이드 개수
    error = Signal(str)             # 에러 메시지
    progress = Signal(int, int, str)  # 진행률 (current, total, engine_name)
    
    def __init__(self, manager: 'SlideManager', path: str | Path):
        super().__init__()
        self.manager = manager
        self.path = path
        
    def run(self):
        try:
            count = self.manager._do_load_pptx(self.path, progress_callback=self._emit_progress)
            self.finished.emit(count)
        except Exception as e:
            self.error.emit(str(e))
    
    def _emit_progress(self, current: int, total: int, engine_name: str):
        self.progress.emit(current, total, engine_name)

class SlideManager(QObject):
    """PPTX 파일을 로드하고 슬라이드 이미지를 관리함"""
    
    file_changed = Signal()         # 파일 변경 시 발생
    load_started = Signal()         # 로딩 시작
    load_finished = Signal(int)     # 로딩 완료 (슬라이드 수)
    load_error = Signal(str)        # 로딩 에러
    load_progress = Signal(int, int, str)  # 진행률 (current, total, engine_name)
    
    def __init__(self, converter: SlideConverter = None) -> None:
        super().__init__()
        # 단일 PPT 모드 (레거시)
        self._pptx_path: Path | None = None
        self._slide_count: int = 0
        
        # 다중 PPT 모드 (곡별)
        self._songs: list = []  # Song 객체 리스트
        self._slide_offsets: dict[str, int] = {}  # song.name -> 전역 시작 인덱스
        self._total_slide_count: int = 0  # 모든 곡의 슬라이드 합계
        
        self._converter = converter or create_slide_converter()
        self._observer = None
        self._load_worker = None

