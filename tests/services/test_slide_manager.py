"""SlideManager 단위 테스트 (RED 단계)"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

# 우리가 만들 클래스
from flow.services.slide_manager import SlideManager

class TestSlideManager:
    """SlideManager의 요구사항 검증"""
    
    def test_load_pptx_count_slides(self, tmp_path):
        """PPTX를 로드하면 슬라이드 개수를 알 수 있어야 함"""
        # Given: 실제 임시 파일 생성 (exists() 체크 통과 목적)
        pptx_path = tmp_path / "test.pptx"
        pptx_path.write_text("dummy")
        
        # python-pptx의 Presentation 객체 모킹
        with patch("flow.services.slide_manager.Presentation") as MockPres:
            mock_pres = MockPres.return_value
            mock_pres.slides = [MagicMock() for _ in range(5)]
            
            manager = SlideManager()
            
            # When: 로드
            count = manager.load_pptx(pptx_path)
            
            # Then: 5개여야 함
            assert count == 5
            assert manager.get_slide_count() == 5
            
    def test_get_slide_image_returns_qimage(self):
        """특정 슬라이드의 이미지를 요청하면 QImage가 반환되어야 함"""
        from PySide6.QtGui import QImage
        
        manager = SlideManager()
        # 가상의 변환기(Converter)를 주입했다고 가정
        mock_converter = MagicMock()
        mock_image = QImage(100, 100, QImage.Format.Format_RGB32)
        mock_converter.convert_slide.return_value = mock_image
        manager._converter = mock_converter
        
        # When: 0번 슬라이드 이미지 요청
        image = manager.get_slide_image(0)
        
        # Then: QImage여야 함
        assert isinstance(image, QImage)
        assert image.width() == 100

    def test_file_watcher_notifies_on_change(self, tmp_path):
        """파일이 변경되면 SlideManager가 이를 감지하고 시그널을 보내야 함"""
        # Given: 실제 임시 파일 생성
        pptx_file = tmp_path / "test.pptx"
        pptx_file.write_text("initial content")
        
        manager = SlideManager()
        change_detected = False
        
        def on_change():
            nonlocal change_detected
            change_detected = True
            
        # file_changed 시그널이 있다고 가정 (아직 구현 전이므로 AttributeError 발생 예상)
        manager.file_changed.connect(on_change)
        
        # When: 파일 감시 시작 및 파일 수정
        manager.start_watching(pptx_file)
        pptx_file.write_text("updated content")
        
        # Then: 변경 감지 시그널이 발생해야 함
        import time
        for _ in range(20):  # 2초까지 대기 (watchdog 이벤트 지연 고려)
            if change_detected: break
            time.sleep(0.1)
            
        assert change_detected
        manager.stop_watching()
