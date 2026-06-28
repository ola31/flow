"""SlideManager - PPTX 슬라이드를 이미지로 관리하는 서비스"""

from __future__ import annotations

import queue
import time
from pathlib import Path

from pptx import Presentation
from PySide6.QtCore import QObject, QThread, Signal
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from flow.services.slide_converter import (
    MarkdownSlideConverter,
    NoConverterAvailableError,
    SlideConverter,
    create_slide_converter,
)


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

    def _count_slides(self, path: Path) -> int:
        """Counts slides using the converter for .md, python-pptx for .pptx.

        Only the MarkdownSlideConverter exposes get_slide_count; the .md
        branch is therefore only reached when this worker holds one.
        """
        if str(path).lower().endswith(".md"):
            converter = self._converter
            count = converter.get_slide_count(path)  # type: ignore[attr-defined]
            return int(count)
        prs = Presentation(str(path))
        return len(prs.slides)

    def _handle_single_load(self, path: Path):
        self.status.emit("PPT 파일 읽기 중...")
        try:
            slide_count = self._count_slides(path)
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
                count = self._count_slides(abs_p)
            except Exception:
                pass
            results.append((name, count))

        total_slides = sum(c for _, c in results)
        if total_slides > 0:
            converted = 0
            engine_info = self._converter.get_engine_name()
            for name, abs_p in song_data_list:
                count = next((c for n, c in results if n == name), 0)
                for i in range(count):
                    if self._abort_requested or self.isInterruptionRequested():
                        return
                    self._converter.convert_slide(
                        abs_p, i, status_callback=self.status.emit
                    )
                    converted += 1
                    self.progress.emit(converted, total_slides, engine_info)

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

    # PPT 변환 엔진(PowerPoint/LibreOffice)이 없을 때 PPT 조작 시도 시 발화.
    # MainWindow가 catch해서 설치 안내 다이얼로그를 띄운다.
    engine_missing = Signal()

    def __init__(self, converter: SlideConverter = None) -> None:
        super().__init__()
        self._pptx_path: Path | None = None
        self._slide_count: int = 0
        self._songs: list = []
        self._slide_offsets: dict[str, int] = {}
        self._total_slide_count: int = 0
        try:
            self._converter = converter or create_slide_converter()
        except NoConverterAvailableError:
            self._converter = None
        self._observer = None
        self._old_workers: list[SlideWorker] = []
        self._pending_reload_song = None

        if self._converter is not None:
            self._worker = SlideWorker(self._converter)
            self._connect_worker(self._worker)
            self._worker.start()
        else:
            self._worker = None

        # Markdown converter is always available — no external deps
        self._markdown_converter = MarkdownSlideConverter()
        self._markdown_worker = SlideWorker(self._markdown_converter)
        self._connect_worker(self._markdown_worker)
        self._markdown_worker.start()

        # 외부 PowerPoint 편집 중 파일 watcher 일시 중지 플래그
        self._watch_paused: bool = False

    def is_engine_available(self) -> bool:
        """PPT 변환 엔진이 사용 가능한지."""
        return self._converter is not None

    def stop_workers(self):
        for worker in (self._worker, self._markdown_worker):
            if worker is not None:
                worker.abort_current_task()

    def clear_caches(self) -> None:
        """Clear cached converted slide images for all converter backends."""
        if self._converter is not None:
            self._converter.clear_cache()
        self._markdown_converter.clear_cache()

    def is_watch_paused(self) -> bool:
        return self._watch_paused

    def pause_file_watching(self) -> None:
        """파일 watcher 일시 중지.

        외부 프로그램(예: PowerPoint)에서 PPT를 편집하는 동안 호출.
        편집 중 저장이 발생해도 자동 리로드를 시도하지 않아 파일 락 충돌
        및 PowerPoint 크래시를 예방한다.
        """
        self._watch_paused = True
        self.stop_watching()  # observer 자체 중지
        # 진행 중인 변환도 함께 중단해 COM/file handle 점유 해제
        self.stop_workers()

    def resume_file_watching(self) -> None:
        """파일 watcher 재개.

        사용자가 외부 편집을 마쳤을 때 호출. 보통 슬라이드 새로고침
        흐름과 함께 트리거된다.
        """
        self._watch_paused = False
        if self._pptx_path and self._pptx_path.exists():
            self.start_watching()

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
        if self._converter is None:
            self._songs = []
            self._slide_offsets = {}
            self._total_slide_count = 0
            self._slide_count = 0
            return

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

    def _worker_for(self, path: Path) -> SlideWorker | None:
        """Return the worker matching the file's extension."""
        if str(path).lower().endswith(".md"):
            return self._markdown_worker
        return self._worker

    def load_pptx(self, path: str | Path):
        p = Path(path).resolve() if path and str(path).strip() else None
        if not p or not p.is_file():
            self._pptx_path = None
            self._slide_count = 0
            self.load_finished.emit(0)
            return

        worker = self._worker_for(p)
        if worker is None:
            self.engine_missing.emit()
            self.load_finished.emit(0)
            return

        self._pptx_path = p
        self.load_started.emit()
        worker.add_task(PPTTask(PPTTask.LOAD_SINGLE, p))

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
            # markdown wins over pptx per Song.slide_source
            source = getattr(s, "slide_source", None)
            if source == "markdown":
                song_data_list.append((s.name, s.markdown_path))
            elif source == "pptx" or (source is None and s.has_slides):
                song_data_list.append((s.name, s.abs_slides_path))

        if not song_data_list:
            self.load_finished.emit(0)
            return

        # Split batch by file extension — markdown songs go to markdown worker,
        # pptx songs to pptx worker. Each worker only knows how to count its
        # own format.
        md_batch = [
            (n, p) for n, p in song_data_list
            if str(p).lower().endswith(".md")
        ]
        pptx_batch = [
            (n, p) for n, p in song_data_list
            if not str(p).lower().endswith(".md")
        ]

        if pptx_batch and self._worker is None:
            self.engine_missing.emit()
            self.load_finished.emit(0)
            return

        self.songs_metadata_started.emit()
        if md_batch:
            self._markdown_worker.add_task(
                PPTTask(PPTTask.LOAD_METADATA, md_batch)
            )
        if pptx_batch:
            self._worker.add_task(
                PPTTask(PPTTask.LOAD_METADATA, pptx_batch)
            )

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
        if self._total_slide_count > 0:
            try:
                song_name, local_index = self.global_to_local(index)
                return self.get_song_slide_image(
                    song_name, local_index, status_callback=status_callback
                )
            except Exception:
                return None

        # 단일 파일 모드 — _pptx_path 확장자에 따라 컨버터 선택
        if not self._pptx_path:
            return None
        if str(self._pptx_path).lower().endswith(".md"):
            return self._markdown_converter.convert_slide(
                self._pptx_path, index, status_callback=status_callback
            )
        if self._converter is None:
            return None
        return self._converter.convert_slide(
            self._pptx_path, index, status_callback=status_callback
        )

    def get_song_slide_image(
        self, song_name: str, local_index: int, status_callback=None
    ):
        song = next((s for s in self._songs if s.name == song_name), None)
        if song is None:
            return None
        source = getattr(song, "slide_source", None)
        if source == "markdown":
            return self._markdown_converter.convert_slide(
                song.markdown_path, local_index, status_callback=status_callback
            )
        if source == "pptx" or (source is None and song.has_slides):
            if self._converter is None:
                return None
            return self._converter.convert_slide(
                song.abs_slides_path, local_index, status_callback=status_callback
            )
        return None

    def start_watching(self, path: str | Path = None):
        if path:
            self._pptx_path = Path(path)
        if not self._pptx_path or not self._pptx_path.parent.exists():
            return
        # pause 상태에선 다른 코드 경로(load_pptx 등)에서 호출돼도 watcher 비활성 유지
        if self._watch_paused:
            return

        self.stop_watching()
        self._pptx_path = self._pptx_path.resolve()
        self._observer = Observer()
        handler = SlideUpdateHandler(self._pptx_path, self._on_watch_event)
        self._observer.schedule(handler, str(self._pptx_path.parent), recursive=False)
        self._observer.start()

    def _on_watch_event(self) -> None:
        """Watcher callback. Invalidates markdown cache before emitting.

        For .md files, the in-memory render cache must be cleared before any
        listener responds to ``file_changed`` so a re-render reads fresh
        content from disk.
        """
        if self._pptx_path is not None and str(self._pptx_path).lower().endswith(
            ".md"
        ):
            self._markdown_converter.invalidate_cache(self._pptx_path)
        self.file_changed.emit()

    def stop_watching(self):
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=1)
            self._observer = None

    def shutdown(self):
        self.stop_watching()
        for worker in (self._worker, self._markdown_worker):
            if worker is not None:
                worker.stop()
        for w in self._old_workers:
            if w.isRunning():
                w.stop()
        self._old_workers.clear()

    def invalidate_markdown_cache(self, md_path: Path) -> None:
        """Public hook to drop the markdown render cache for one song."""
        self._markdown_converter.invalidate_cache(md_path)

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
            source = getattr(song, "slide_source", None)
            has_source = (
                source in ("markdown", "pptx")
                or (source is None and song.has_slides)
            )
            if has_source:
                self._slide_offsets[song.name] = offset
                offset += song.get_slide_count()
        self._total_slide_count = offset

    def reload_song(self, song):
        # markdown 우선, 없으면 PPT, 둘 다 없으면 0장 처리
        source = getattr(song, "slide_source", None)
        if source == "markdown":
            target_path = song.markdown_path
        elif source == "pptx" or (source is None and song.has_slides):
            target_path = song.abs_slides_path
        else:
            target_path = None

        if target_path is None:
            if self._songs:
                song.set_slide_count(0)
                self._recalculate_offsets()
                self.load_finished.emit(self._total_slide_count)
            return

        worker = self._worker_for(target_path)
        if worker is None:
            self.engine_missing.emit()
            return

        # markdown converter 캐시는 source 변경 가능성에 대비해 invalidate
        if source == "markdown":
            self._markdown_converter.invalidate_cache(target_path)

        if self._songs:
            self._pending_reload_song = song
        self.load_started.emit()
        worker.add_task(PPTTask(PPTTask.LOAD_SINGLE, target_path))

    def reload_all_songs(self):
        if not self._songs:
            return
        # 곡 중에 PPT가 하나라도 있으면 PPT 엔진 필요
        has_pptx = any(
            getattr(s, "slide_source", None) == "pptx" or
            (getattr(s, "slide_source", None) is None and s.has_slides)
            for s in self._songs
        )
        if has_pptx and self._converter is None:
            self.engine_missing.emit()
            return
        self.clear_caches()
        self.load_songs(self._songs)
