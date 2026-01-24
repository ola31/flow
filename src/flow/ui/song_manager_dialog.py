"""곡 관리 다이얼로그"""
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
    QListWidget, QInputDialog, QMessageBox, QLabel
)
from PySide6.QtCore import Signal
from pptx import Presentation


class SongManagerDialog(QDialog):
    """곡 추가/제거/순서 변경 다이얼로그"""
    
    songs_changed = Signal()  # 곡 목록 변경 시 발생
    
    def __init__(self, project_dir: Path, selected_songs: list, parent=None):
        super().__init__(parent)
        self.project_dir = project_dir
        self.songs_dir = project_dir / "songs"
        self.selected_songs = selected_songs  # Song 객체 리스트
        
        self.setWindowTitle("곡 관리")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        self._setup_ui()
        self._load_song_list()
    
    def _setup_ui(self):
        """UI 구성"""
        layout = QVBoxLayout(self)
        
        # 설명
        label = QLabel("프로젝트에 포함된 곡 목록:")
        layout.addWidget(label)
        
        # 곡 목록
        self.song_list = QListWidget()
        layout.addWidget(self.song_list)
        
        # 버튼들
        btn_layout = QHBoxLayout()
        
        self.btn_add_new = QPushButton("새 곡 만들기")
        self.btn_add_new.clicked.connect(self._on_add_new_song)
        btn_layout.addWidget(self.btn_add_new)
        
        self.btn_import = QPushButton("기존 곡 불러오기")
        self.btn_import.clicked.connect(self._on_import_song)
        btn_layout.addWidget(self.btn_import)
        
        self.btn_remove = QPushButton("제거")
        self.btn_remove.clicked.connect(self._on_remove_song)
        btn_layout.addWidget(self.btn_remove)
        
        btn_layout.addStretch()
        
        self.btn_close = QPushButton("닫기")
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)
        
        layout.addLayout(btn_layout)
    
    def _load_song_list(self):
        """현재 선택된 곡 목록 표시"""
        self.song_list.clear()
        for song in self.selected_songs:
            self.song_list.addItem(f"{song.order}. {song.name}")
    
    def _on_add_new_song(self):
        """새 곡 추가"""
        name, ok = QInputDialog.getText(self, "새 곡", "곡 이름:")
        if not ok or not name.strip():
            return
        
        name = name.strip()
        
        # songs/ 폴더 생성
        self.songs_dir.mkdir(exist_ok=True)
        
        # 곡 폴더 생성
        song_dir = self.songs_dir / name
        if song_dir.exists():
            QMessageBox.warning(self, "오류", f"'{name}' 곡이 이미 존재합니다.")
            return
        
        song_dir.mkdir(parents=True)
        
        # 빈 slides.pptx 생성
        slides_path = song_dir / "slides.pptx"
        self._create_empty_pptx(slides_path)
        
        # sheets/ 폴더 생성
        (song_dir / "sheets").mkdir(exist_ok=True)
        
        # song.json 생성 (빈 템플릿)
        import json
        song_data = {
            "name": name,
            "sheet": None
        }
        with open(song_dir / "song.json", "w", encoding="utf-8-sig") as f:
            json.dump(song_data, f, ensure_ascii=False, indent=2)
        
        # Song 객체 생성 및 추가
        from flow.domain.song import Song
        from flow.domain.score_sheet import ScoreSheet
        
        song = Song(
            name=name,
            folder=Path("songs") / name,
            score_sheet=ScoreSheet(name=name),  # name 인자 추가
            order=len(self.selected_songs) + 1
        )
        self.selected_songs.append(song)
        
        self._load_song_list()
        self.songs_changed.emit()
        
        QMessageBox.information(self, "완료", f"'{name}' 곡이 추가되었습니다.")
    
    def _create_empty_pptx(self, path: Path):
        """빈 PPTX 파일 생성"""
        prs = Presentation()
        prs.save(str(path))
    
    def _on_import_song(self):
        """기존 곡 불러오기 (파일 탐색기)"""
        from PySide6.QtWidgets import QFileDialog
        
        # 곡 폴더 선택
        song_folder = QFileDialog.getExistingDirectory(
            self,
            "곡 폴더 선택",
            str(Path.home()),
            QFileDialog.ShowDirsOnly
        )
        
        if not song_folder:
            return
        
        song_folder = Path(song_folder)
        song_name = song_folder.name
        
        # song.json 파일 확인
        song_json_path = song_folder / "song.json"
        if not song_json_path.exists():
            QMessageBox.warning(
                self, "오류", 
                f"선택한 폴더에 song.json 파일이 없습니다.\n곡 폴더를 선택해주세요."
            )
            return
        
        # 이미 선택된 곡인지 확인
        if any(s.name == song_name for s in self.selected_songs):
            QMessageBox.warning(self, "오류", f"'{song_name}' 곡이 이미 추가되어 있습니다.")
            return
        
        # songs/ 폴더로 복사
        self.songs_dir.mkdir(exist_ok=True)
        dest_dir = self.songs_dir / song_name
        
        if dest_dir.exists():
            reply = QMessageBox.question(
                self, "확인",
                f"'{song_name}' 폴더가 이미 존재합니다. 덮어쓰시겠습니까?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
            import shutil
            shutil.rmtree(dest_dir)
        
        # 폴더 복사
        import shutil
        shutil.copytree(song_folder, dest_dir)
        
        # Song 객체 생성
        from flow.domain.song import Song
        from flow.domain.score_sheet import ScoreSheet
        import json
        
        with open(dest_dir / "song.json", "r", encoding="utf-8-sig") as f:
            song_data = json.load(f)
        
        sheet_data = song_data.get("sheet")
        score_sheet = ScoreSheet.from_dict(sheet_data) if sheet_data else ScoreSheet(name=song_name)
        
        song = Song(
            name=song_name,
            folder=Path("songs") / song_name,
            score_sheet=score_sheet,
            order=len(self.selected_songs) + 1
        )
        self.selected_songs.append(song)
        
        self._load_song_list()
        self.songs_changed.emit()
        
        QMessageBox.information(self, "완료", f"'{song_name}' 곡이 추가되었습니다.")

    def _on_remove_song(self):
        """곡 제거 (폴더는 유지)"""
        current_row = self.song_list.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "오류", "제거할 곡을 선택하세요.")
            return
        
        song = self.selected_songs[current_row]
        
        reply = QMessageBox.question(
            self, "확인", 
            f"'{song.name}' 곡을 프로젝트에서 제거하시겠습니까?\n(폴더는 유지됩니다)",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.selected_songs.pop(current_row)
            
            # 순서 재조정
            for i, s in enumerate(self.selected_songs):
                s.order = i + 1
            
            self._load_song_list()
            self.songs_changed.emit()
