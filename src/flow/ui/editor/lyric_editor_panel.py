"""가사 편집 패널

선택된 핫스팟의 가사를 편집하는 UI
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTextEdit, QPushButton, QHBoxLayout
)
from PySide6.QtCore import Signal

from flow.domain.hotspot import Hotspot


class LyricEditorPanel(QWidget):
    """가사 편집 패널
    
    Signals:
        lyric_changed: 가사가 변경됨 (Hotspot)
    """
    
    lyric_changed = Signal(object)  # Hotspot
    
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._hotspot: Hotspot | None = None
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """UI 초기화"""
        layout = QVBoxLayout(self)
        
        # 헤더
        self._header = QLabel("가사 편집")
        self._header.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self._header)
        
        # 안내 텍스트
        self._info = QLabel("핫스팟을 선택하세요")
        self._info.setStyleSheet("color: gray;")
        layout.addWidget(self._info)
        
        # 가사 입력
        self._text_edit = QTextEdit()
        self._text_edit.setPlaceholderText("가사를 입력하세요...\n(여러 줄 입력 가능)")
        self._text_edit.setEnabled(False)
        self._text_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._text_edit)
        
        # 버튼들
        btn_layout = QHBoxLayout()
        
        self._save_btn = QPushButton("저장")
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(self._save_btn)
        
        self._clear_btn = QPushButton("지우기")
        self._clear_btn.setEnabled(False)
        self._clear_btn.clicked.connect(self._on_clear)
        btn_layout.addWidget(self._clear_btn)
        
        layout.addLayout(btn_layout)
    
    def set_hotspot(self, hotspot: Hotspot | None) -> None:
        """편집할 핫스팟 설정"""
        self._hotspot = hotspot
        
        if hotspot:
            self._info.setText(f"핫스팟 #{hotspot.order + 1}")
            self._text_edit.setPlainText(hotspot.lyric)
            self._text_edit.setEnabled(True)
            self._save_btn.setEnabled(True)
            self._clear_btn.setEnabled(True)
        else:
            self._info.setText("핫스팟을 선택하세요")
            self._text_edit.clear()
            self._text_edit.setEnabled(False)
            self._save_btn.setEnabled(False)
            self._clear_btn.setEnabled(False)
    
    def _on_text_changed(self) -> None:
        """텍스트 변경 시 즉시 저장"""
        if self._hotspot:
            self._hotspot.lyric = self._text_edit.toPlainText()
    
    def _on_save(self) -> None:
        """저장 버튼 클릭"""
        if self._hotspot:
            self._hotspot.lyric = self._text_edit.toPlainText()
            self.lyric_changed.emit(self._hotspot)
    
    def _on_clear(self) -> None:
        """지우기 버튼 클릭"""
        self._text_edit.clear()
        if self._hotspot:
            self._hotspot.lyric = ""
