import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from flow.services.slide_manager import SlideManager, SlideWorker, PPTTask


@pytest.fixture
def mock_converter():
    converter = MagicMock()
    converter.convert_slide.return_value = None
    converter.get_engine_name.return_value = "Mock"
    return converter


@pytest.fixture
def manager(mock_converter):
    mgr = SlideManager(converter=mock_converter)
    yield mgr
    # Tear down everything (worker + markdown worker + file watcher) so that
    # an asserting test never leaks a QThread/Observer → SIGABRT during exit.
    mgr.shutdown()


class TestSlideManager:
    def test_initial_slide_count_is_zero(self, manager):
        assert manager.get_slide_count() == 0

    def test_get_slide_image_returns_qimage(self, manager, mock_converter):
        from PySide6.QtGui import QImage

        mock_image = QImage(100, 100, QImage.Format.Format_RGB32)
        mock_converter.convert_slide.return_value = mock_image

        manager._pptx_path = Path("/fake/test.pptx")
        image = manager.get_slide_image(0)

        assert isinstance(image, QImage)
        assert image.width() == 100

    def test_reset_worker_clears_state(self, manager):
        manager._songs = ["fake_song"]
        manager._slide_offsets = {"test": 5}
        manager._total_slide_count = 10

        manager.reset_worker()

        assert manager._songs == []
        assert manager._slide_offsets == {}
        assert manager._total_slide_count == 0
        assert manager._slide_count == 0

    def test_global_to_local_raises_on_invalid_index(self, manager):
        with pytest.raises(ValueError, match="Invalid index"):
            manager.global_to_local(999)

    def test_local_to_global_raises_on_unknown_song(self, manager):
        with pytest.raises(ValueError, match="Song not found"):
            manager.local_to_global("nonexistent", 0)

    def test_file_watcher_notifies_on_change(self, tmp_path, manager, qtbot):
        pptx_file = tmp_path / "test.pptx"
        pptx_file.write_text("initial content")

        manager.start_watching(pptx_file)
        # Give the watchdog Observer thread a moment to register the inotify
        # watch before we modify the file. Without this the modification can
        # race ahead of the watcher and the event is lost on slower runners.
        import time
        time.sleep(0.5)

        # qtbot.waitSignal pumps the Qt event loop while waiting, which is
        # required because file_changed is emitted from the watchdog thread
        # and arrives via QueuedConnection.
        with qtbot.waitSignal(manager.file_changed, timeout=4000):
            pptx_file.write_text("updated content")

        manager.stop_watching()


class TestSlideWorker:
    def test_abort_clears_queue(self, mock_converter):
        worker = SlideWorker(mock_converter)
        worker._task_queue.put(PPTTask(PPTTask.LOAD_SINGLE, Path("/fake")))
        worker._task_queue.put(PPTTask(PPTTask.LOAD_SINGLE, Path("/fake2")))

        worker.abort_current_task()

        assert worker._task_queue.empty()
        assert worker._abort_requested is True

    def test_add_task_resets_abort_flag(self, mock_converter):
        worker = SlideWorker(mock_converter)
        worker._abort_requested = True

        worker.add_task(PPTTask(PPTTask.LOAD_SINGLE, Path("/fake")))

        assert worker._abort_requested is False
        assert not worker._task_queue.empty()


class TestFileWatcherPause:
    """외부 PPT 편집 시나리오를 위한 watcher 일시 중지/재개."""

    def test_initial_state_not_paused(self, manager):
        assert manager.is_watch_paused() is False

    def test_pause_sets_flag_and_stops_observer(self, manager, tmp_path):
        # observer가 동작 중이라고 가정 — pptx_path 설정 후 시작
        pptx = tmp_path / "x.pptx"
        pptx.write_bytes(b"fake")
        manager.start_watching(pptx)
        assert manager._observer is not None

        manager.pause_file_watching()
        assert manager.is_watch_paused() is True
        assert manager._observer is None  # stop_watching이 None으로 만듦

    def test_paused_state_blocks_start_watching(self, manager, tmp_path):
        pptx = tmp_path / "x.pptx"
        pptx.write_bytes(b"fake")
        manager.pause_file_watching()  # pause 먼저

        # 다른 코드 경로(load_pptx 등)에서 start_watching이 호출돼도 무시
        manager.start_watching(pptx)
        assert manager._observer is None

    def test_resume_restarts_watcher(self, manager, tmp_path):
        pptx = tmp_path / "x.pptx"
        pptx.write_bytes(b"fake")
        manager._pptx_path = pptx.resolve()

        manager.pause_file_watching()
        assert manager.is_watch_paused() is True

        manager.resume_file_watching()
        assert manager.is_watch_paused() is False
        assert manager._observer is not None

    def test_resume_noop_if_pptx_missing(self, manager, tmp_path):
        manager._pptx_path = tmp_path / "no.pptx"  # 존재하지 않음

        manager.pause_file_watching()
        manager.resume_file_watching()

        assert manager.is_watch_paused() is False
        assert manager._observer is None  # 파일 없으면 시작 안 함
