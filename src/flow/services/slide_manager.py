"""SlideManager - PPTX 슬라이드를 이미지로 관리하는 서비스"""

import time
import queue
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QThread, Qt, QTimer
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

        if Path(event.src_path).resolve() != self.target_path:
            return

        now = time.time()
        if now - self.last_triggered > 0.1:
            self.callback()
            self.last_triggered = now


class PPTTask:
    """PPT 작업 단위 (큐에 담길 객체)"""

    LOAD_SINGLE = "LOAD_SINGLE"
    LOAD_METADATA = "LOAD_METADATA"

    def __init__(self, task_type, data):
        self.task_type = task_type
        self.data = data


class SlideWorker(QThread):
    """모든 PPT 작업을 순차적으로 처리하는 전용 백그라운드 스레드"""

    # 결과 전송용 시그널
    single_load_finished = Signal(int)
    metadata_finished = Signal(list)
    progress = Signal(int, int, str)
    status = Signal(str)
    error = Signal(str)

    def __init__(self, converter: SlideConverter):
        super().__init__()
        self._converter = converter
        self._task_queue = queue.Queue()
        self._is_running = True
        self._abort_requested = False

    def add_task(self, task: PPTTask):
        self._abort_requested = True
        while not self._task_queue.empty():
            try:
                self._task_queue.get_nowait()
            except queue.Empty:
                break
        self._abort_requested = False
        self._task_queue.put(task)

    def abort_current_task(self):
        self._abort_requested = True
        while not self._task_queue.empty():
            try:
                self._task_queue.get_nowait()
            except queue.Empty:
                break

    def stop(self):
        self._is_running = False
        self._abort_requested = True
        self.requestInterruption()
        self.wait(1000)

    def run(self):
        while self._is_running:
            try:
                task = self._task_queue.get(timeout=0.5)
            except queue.Empty:
                if self.isInterruptionRequested():
                    break
                continue

            self._abort_requested = False
            try:
                if task.task_type == PPTTask.LOAD_SINGLE:
                    self._handle_single_load(task.data)
                elif task.task_type == PPTTask.LOAD_METADATA:
                    self._handle_metadata_load(task.data)
            except Exception as e:
                if not self._abort_requested and not self.isInterruptionRequested():
                    self.error.emit(str(e))
            finally:
                self._task_queue.task_done()

    def _handle_single_load(self, path: Path):
        self.status.emit("PPT 파일 읽기 중...")
        try:
            prs = Presentation(str(path))
            slide_count = len(prs.slides)
            engine_info = self._converter.get_engine_name()

            if slide_count > 0:
                for i in range(slide_count):
                    if self._abort_requested or self.isInterruptionRequested():
                        return
                    self._converter.convert_slide(
                        path, i, status_callback=self.status.emit
                    )
                    self.progress.emit(i + 1, slide_count, engine_info)

            if not self._abort_requested and not self.isInterruptionRequested():
                self.single_load_finished.emit(slide_count)
        except Exception as e:
            if not self._abort_requested:
                raise SlideLoadError(f"PPTX 로드 중 오류 발생: {e}")

    def _handle_metadata_load(self, song_data_list: list[tuple[str, Path]]):
        results = []
        for name, abs_p in song_data_list:
            if self._abort_requested or self.isInterruptionRequested():
                return
            count = 0
            try:
                prs = Presentation(str(abs_p))
                count = len(prs.slides)
            except:
                pass
            results.append((name, count))

        if not self._abort_requested and not self.isInterruptionRequested():
            self.metadata_finished.emit(results)


class SlideManager(QObject):
    """PPTX 파일을 로드하고 슬라이드 이미지를 관리함"""

    file_changed = Signal()
    load_started = Signal()
    load_finished = Signal(int)
    load_error = Signal(str)
    load_progress = Signal(int, int, str)
    load_status = Signal(str)

    songs_metadata_started = Signal()
    songs_metadata_finished = Signal(int)

    def __init__(self, converter: SlideConverter = None) -> None:
        super().__init__()
        self._pptx_path: Path | None = None
        self._slide_count: int = 0
        self._songs: list = []
        self._slide_offsets: dict[str, int] = {}
        self._total_slide_count: int = 0
        self._converter = converter or create_slide_converter()
        self._observer = None
        self._old_workers: list[SlideWorker] = []
        self._pending_reload_song = None

        self._worker = SlideWorker(self._converter)
        self._connect_worker(self._worker)
        self._worker.start()

    def stop_workers(self):
        self._worker.abort_current_task()

    def _connect_worker(self, worker: SlideWorker) -> None:
        worker.single_load_finished.connect(self._on_single_load_finished)
        worker.metadata_finished.connect(self._on_metadata_loaded)
        worker.progress.connect(self.load_progress.emit)
        worker.status.connect(self.load_status.emit)
        worker.error.connect(self.load_error.emit)

    def _disconnect_worker(self, worker: SlideWorker) -> None:
        worker.single_load_finished.disconnect(self._on_single_load_finished)
        worker.metadata_finished.disconnect(self._on_metadata_loaded)
        worker.progress.disconnect(self.load_progress.emit)
        worker.status.disconnect(self.load_status.emit)
        worker.error.disconnect(self.load_error.emit)

    def reset_worker(self):
        old = self._worker
        self._disconnect_worker(old)
        old.stop()

        self._old_workers = [w for w in self._old_workers if w.isRunning()]
        self._old_workers.append(old)

        self._songs = []
        self._slide_offsets = {}
        self._total_slide_count = 0
        self._slide_count = 0

        self._worker = SlideWorker(self._converter)
        self._connect_worker(self._worker)
        self._worker.start()

    def load_pptx(self, path: str | Path):
        p = Path(path).resolve() if path and str(path).strip() else None
        if not p or not p.is_file():
            self._pptx_path = None
            self._slide_count = 0
            self.load_finished.emit(0)
            return

        self._pptx_path = p
        self.load_started.emit()
        self._worker.add_task(PPTTask(PPTTask.LOAD_SINGLE, p))

    def _on_single_load_finished(self, count: int):
        self._slide_count = count
        if self._pending_reload_song:
            self._pending_reload_song.set_slide_count(count)
            self._pending_reload_song = None
            self._recalculate_offsets()
        self.load_finished.emit(self.get_slide_count())

    def load_songs(self, songs: list):
        self._songs = songs
        self._slide_offsets = {}
        self._total_slide_count = 0

        song_data_list = []
        for s in songs:
            if s.has_slides:
                song_data_list.append((s.name, s.abs_slides_path))

        if not song_data_list:
            self.load_finished.emit(0)
            return

        self.songs_metadata_started.emit()
        self._worker.add_task(PPTTask(PPTTask.LOAD_METADATA, song_data_list))

    def _on_metadata_loaded(self, results: list[tuple[str, int]]):
        if not self._songs:
            return

        for name, count in results:
            song = next((s for s in self._songs if s.name == name), None)
            if song:
                song.set_slide_count(count)

        self._recalculate_offsets()
        self.songs_metadata_finished.emit(self._total_slide_count)
        self.load_finished.emit(self._total_slide_count)

    def get_slide_count(self) -> int:
        if self._total_slide_count > 0:
            return self._total_slide_count
        return self._slide_count

    def get_slide_image(self, index: int, status_callback=None):
        if not self._converter:
            return None

        if self._total_slide_count > 0:
            try:
                song_name, local_index = self.global_to_local(index)
                return self.get_song_slide_image(
                    song_name, local_index, status_callback=status_callback
                )
            except:
                return None

        return self._converter.convert_slide(
            self._pptx_path, index, status_callback=status_callback
        )

    def get_song_slide_image(
        self, song_name: str, local_index: int, status_callback=None
    ):
        song = next((s for s in self._songs if s.name == song_name), None)
        if not song or not song.has_slides:
            return None
        return self._converter.convert_slide(
            song.abs_slides_path, local_index, status_callback=status_callback
        )

    def start_watching(self, path: str | Path = None):
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
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=1)
            self._observer = None

    def shutdown(self):
        self.stop_watching()
        self._worker.stop()
        for w in self._old_workers:
            if w.isRunning():
                w.stop()
        self._old_workers.clear()

    def global_to_local(self, global_index: int) -> tuple[str, int]:
        for song in self._songs:
            offset = self._slide_offsets.get(song.name, 0)
            count = song.get_slide_count()
            if offset <= global_index < offset + count:
                return (song.name, global_index - offset)
        raise ValueError(f"Invalid index: {global_index}")

    def local_to_global(self, song_name: str, local_index: int) -> int:
        offset = self._slide_offsets.get(song_name)
        if offset is None:
            raise ValueError(f"Song not found: {song_name}")
        return offset + local_index

    def get_song_offset(self, song_name: str) -> int:
        return self._slide_offsets.get(song_name, 0)

    def _recalculate_offsets(self) -> None:
        offset = 0
        for song in self._songs:
            if song.has_slides:
                self._slide_offsets[song.name] = offset
                offset += song.get_slide_count()
        self._total_slide_count = offset

    def reload_song(self, song):
        if self._songs:
            if song.has_slides:
                self._pending_reload_song = song
                self.load_started.emit()
                self._worker.add_task(
                    PPTTask(PPTTask.LOAD_SINGLE, song.abs_slides_path)
                )
            else:
                song.set_slide_count(0)
                self._recalculate_offsets()
                self.load_finished.emit(self._total_slide_count)
        elif song.has_slides:
            self.load_started.emit()
            self._worker.add_task(PPTTask(PPTTask.LOAD_SINGLE, song.abs_slides_path))

    def reload_all_songs(self):
        if self._songs:
            self._converter.clear_cache()
            self.load_songs(self._songs)
