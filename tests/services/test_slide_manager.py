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
    mgr._worker.stop()


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

    def test_file_watcher_notifies_on_change(self, tmp_path, manager):
        pptx_file = tmp_path / "test.pptx"
        pptx_file.write_text("initial content")

        change_detected = False

        def on_change():
            nonlocal change_detected
            change_detected = True

        manager.file_changed.connect(on_change)

        manager.start_watching(pptx_file)
        pptx_file.write_text("updated content")

        import time

        for _ in range(20):
            if change_detected:
                break
            time.sleep(0.1)

        assert change_detected
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
