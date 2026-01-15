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
    finished = Signal(int) # 슬라이드 개수
    error = Signal(str)    # 에러 메시지
    
    def __init__(self, manager: 'SlideManager', path: str | Path):
        super().__init__()
        self.manager = manager
        self.path = path
        
    def run(self):
        try:
            # 시간 측정을 위해 살짝 대기 (필요시)
            count = self.manager._do_load_pptx(self.path)
            self.finished.emit(count)
        except Exception as e:
            self.error.emit(str(e))

class SlideManager(QObject):
    """PPTX 파일을 로드하고 슬라이드 이미지를 관리함"""
    
    file_changed = Signal()         # 파일 변경 시 발생
    load_started = Signal()         # 로딩 시작
    load_finished = Signal(int)     # 로딩 완료 (슬라이드 수)
    load_error = Signal(str)        # 로딩 에러
    
    def __init__(self, converter: SlideConverter = None) -> None:
        super().__init__()
        self._pptx_path: Path | None = None
        self._slide_count: int = 0
        self._converter = converter or create_slide_converter()
        self._observer = None
        self._load_worker = None
        
    def load_pptx(self, path: str | Path):
        """비동기 방식으로 PPTX 로드 시작"""
        if not path or not str(path).strip():
            # 빈 경로는 즉시 동기적으로 처리 (초기화)
            self._pptx_path = None
            self._slide_count = 0
            self.load_finished.emit(0)
            return

        if self._load_worker and self._load_worker.isRunning():
            return # 이미 로딩 중이면 무시
            
        self.load_started.emit()
        self._load_worker = PPTLoadWorker(self, path)
        self._load_worker.finished.connect(self.load_finished.emit)
        self._load_worker.error.connect(self.load_error.emit)
        self._load_worker.start()

    def _do_load_pptx(self, path: str | Path) -> int:
        """실제 로딩 로직 (백그라운드 스레드에서 호출됨)"""
        import time
        start_time = time.time()
        p = Path(path).resolve() if path and str(path).strip() else None
        
        # 최적화: 이미 같은 파일이 로드되어 있다면 즉시 반환
        if p == self._pptx_path and self._slide_count > 0:
            return self._slide_count
            
        self._pptx_path = p
        
        if p and p.is_file():
            engine_info = self._converter.get_engine_name()
            print(f"[SlideManager] PPT 로드 시작: {p.name} (엔진: {engine_info})")
            try:
                prs = Presentation(str(p))
                self._slide_count = len(prs.slides)

                # 모든 슬라이드 이미지를 미리 변환 (백그라운드 스레드)
                # 사용자 체감: 슬라이드 리스트가 다 채워져야 로딩 완료임
                if self._slide_count > 0:
                    for i in range(self._slide_count):
                        self.get_slide_image(i)
                        if (i + 1) % 5 == 0 or i + 1 == self._slide_count:
                             print(f"[SlideManager] 이미지 생성 중... ({i + 1}/{self._slide_count})")
                
                elapsed = time.time() - start_time
                print(f"[SlideManager] PPT 로드 완료: {self._slide_count} 슬라이드 전체 변환됨 (총 소요 시간: {elapsed:.2f}초)")
                    
            except PackageNotFoundError:
                self._slide_count = 0
                raise SlideLoadError(f"올바른 PPTX 형식이 아닙니다: {path}")
            except Exception as e:
                self._slide_count = 0
                raise SlideLoadError(f"PPTX 로드 중 오류 발생: {e}")
        else:
            self._slide_count = 0
            
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
        
    def stop_watching(self):
        """파일 감시 중지"""
        if self._observer:
            self._observer.stop()
            # 비동기적으로 멈추도록 (로딩 딜레이 방지)
            self._observer = None

