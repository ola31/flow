"""Song(곡) 도메인 모델 테스트

곡 기반 구조의 핵심 도메인 모델 테스트
"""

import json
import pytest
from pathlib import Path
from flow.domain.song import Song
from flow.domain.score_sheet import ScoreSheet
from flow.domain.hotspot import Hotspot
from flow.domain.workspace import Workspace


class TestSongCreation:
    """곡 생성 테스트"""

    def test_create_song_with_name_and_folder(self):
        """이름과 폴더로 곡 생성"""
        song = Song(name="song_a", folder=Path("songs/song_a"))

        assert song.name == "song_a"
        assert song.folder == Path("songs/song_a")

    def test_song_default_values(self):
        """곡 기본값 확인"""
        song = Song(name="Test", folder=Path("songs/test"))

        assert song.order == 0
        assert song.score_sheets == []
        # __post_init__가 slides_path와 sheets_dir를 설정함
        assert song.slides_path == Path("songs/test/slides.pptx")
        assert song.sheets_dir == Path("songs/test/sheets")

    def test_song_post_init_sets_default_paths(self):
        """__post_init__가 기본 경로 설정"""
        song = Song(name="Test", folder=Path("songs/test"))

        assert song.slides_path == Path("songs/test/slides.pptx")
        assert song.sheets_dir == Path("songs/test/sheets")


class TestSongScoreSheets:
    """곡-시트 관계 테스트"""

    def test_add_score_sheet_to_song(self):
        """곡에 시트 추가"""
        song = Song(name="Test", folder=Path("songs/test"))
        sheet = ScoreSheet(name="Sheet1")

        song.score_sheets.append(sheet)

        assert len(song.score_sheets) == 1
        assert song.score_sheets[0].name == "Sheet1"

    def test_score_sheet_property_returns_first(self):
        """score_sheet 프로퍼티가 첫 번째 시트 반환"""
        song = Song(name="Test", folder=Path("songs/test"))
        sheet1 = ScoreSheet(name="Sheet1")
        sheet2 = ScoreSheet(name="Sheet2")

        song.score_sheets.extend([sheet1, sheet2])

        assert song.score_sheet == sheet1

    def test_score_sheet_property_returns_none_if_empty(self):
        """시트가 없으면 score_sheet는 None"""
        song = Song(name="Test", folder=Path("songs/test"))

        assert song.score_sheet is None


class TestSongSlideCount:
    """곡 슬라이드 개수 테스트"""

    def test_default_slide_count_is_zero(self):
        """기본 슬라이드 개수는 0"""
        song = Song(name="Test", folder=Path("songs/test"))

        assert song.get_slide_count() == 0

    def test_set_slide_count(self):
        """슬라이드 개수 설정"""
        song = Song(name="Test", folder=Path("songs/test"))

        song.set_slide_count(10)

        assert song.get_slide_count() == 10


class TestSongShiftIndices:
    """곡 인덱스 이동 테스트 (다중 PPT 지원)"""

    def test_shift_indices_moves_hotspot_indices(self):
        """shift_indices가 모든 핫스팟 인덱스 이동"""
        song = Song(name="Test", folder=Path("songs/test"))
        sheet = ScoreSheet(name="Sheet1")
        hotspot = Hotspot(x=10, y=20)
        hotspot.set_slide_index(5, verse_index=0)
        sheet.add_hotspot(hotspot)
        song.score_sheets.append(sheet)

        song.shift_indices(10)

        assert hotspot.get_slide_index(0) == 15  # 5 + 10

    def test_shift_indices_across_multiple_sheets(self):
        """여러 시트의 핫스팟 인덱스 모두 이동"""
        song = Song(name="Test", folder=Path("songs/test"))

        sheet1 = ScoreSheet(name="Sheet1")
        hotspot1 = Hotspot(x=10, y=20)
        hotspot1.set_slide_index(3, verse_index=0)
        sheet1.add_hotspot(hotspot1)

        sheet2 = ScoreSheet(name="Sheet2")
        hotspot2 = Hotspot(x=30, y=40)
        hotspot2.set_slide_index(7, verse_index=0)
        sheet2.add_hotspot(hotspot2)

        song.score_sheets.extend([sheet1, sheet2])

        song.shift_indices(5)

        assert hotspot1.get_slide_index(0) == 8  # 3 + 5
        assert hotspot2.get_slide_index(0) == 12  # 7 + 5

    def test_shift_indices_with_verse_mappings(self):
        """절별 매핑도 함께 이동"""
        song = Song(name="Test", folder=Path("songs/test"))
        sheet = ScoreSheet(name="Sheet1")
        hotspot = Hotspot(x=10, y=20)
        hotspot.set_slide_index(1, verse_index=0)  # 1절
        hotspot.set_slide_index(10, verse_index=5)  # 후렴
        sheet.add_hotspot(hotspot)
        song.score_sheets.append(sheet)

        song.shift_indices(20)

        assert hotspot.get_slide_index(0) == 21  # 1 + 20
        assert hotspot.get_slide_index(5) == 30  # 10 + 20


class TestSongAbsolutePaths:
    """곡 절대 경로 테스트"""

    def test_abs_slides_path_with_project_dir(self):
        """project_dir이 있으면 절대 경로 반환"""
        song = Song(
            name="Test",
            folder=Path("songs/test"),
            project_dir=Path("/home/user/projects/worship"),
        )

        expected = Path("/home/user/projects/worship/songs/test/slides.pptx")
        assert song.abs_slides_path == expected

    def test_abs_sheets_dir_with_project_dir(self):
        """project_dir이 있으면 sheets 절대 경로 반환"""
        song = Song(
            name="Test",
            folder=Path("songs/test"),
            project_dir=Path("/home/user/projects/worship"),
        )

        expected = Path("/home/user/projects/worship/songs/test/sheets")
        assert song.abs_sheets_dir == expected


class TestSongEdgeCases:
    """곡 엣지 케이스 테스트"""

    def test_empty_song_no_sheets(self):
        """시트가 없는 빈 곡"""
        song = Song(name="Empty", folder=Path("songs/empty"))

        assert song.score_sheets == []
        assert song.score_sheet is None
        assert song.get_slide_count() == 0

    def test_song_default_source_is_local(self):
        """Song 기본 source는 local (워크스페이스 구조 기본값)"""
        song = Song(name="Test", folder=Path("songs/test"))
        assert song.source == "local"

    def test_song_with_custom_slides_path(self):
        """커스텀 slides_path 설정"""
        song = Song(
            name="Test",
            folder=Path("songs/test"),
            slides_path=Path("custom/presentation.pptx"),
        )

        assert song.slides_path == Path("custom/presentation.pptx")


class TestSongWorkspaceLoading:
    """워크스페이스 기반 곡 로딩 테스트 (local → library 우선순위)"""

    def _write_song_json(self, folder: Path, name: str) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "song.json").write_text(
            json.dumps({"name": name, "sheets": []}), encoding="utf-8"
        )

    def test_load_from_library_when_only_library_exists(self, tmp_path):
        ws = Workspace.create(tmp_path / "ws")
        self._write_song_json(ws.library_song_dir("곡B"), "곡B")

        song = Song.load_from_workspace(ws, "행사A", "곡B")
        assert song is not None
        assert song.name == "곡B"
        assert song.source == "library"
        assert song.folder == ws.library_song_dir("곡B").resolve()

    def test_load_from_local_when_both_exist(self, tmp_path):
        ws = Workspace.create(tmp_path / "ws")
        self._write_song_json(ws.library_song_dir("곡B"), "곡B(lib)")

        local_path = ws.project_dir("행사A") / "songs" / "곡B"
        self._write_song_json(local_path, "곡B(local)")

        song = Song.load_from_workspace(ws, "행사A", "곡B")
        assert song is not None
        assert song.name == "곡B(local)"  # 로컬 우선
        assert song.source == "local"
        assert song.folder == local_path.resolve()

    def test_returns_none_when_song_missing(self, tmp_path):
        ws = Workspace.create(tmp_path / "ws")
        assert Song.load_from_workspace(ws, "행사A", "없는곡") is None

    def test_order_is_preserved(self, tmp_path):
        ws = Workspace.create(tmp_path / "ws")
        self._write_song_json(ws.library_song_dir("곡"), "곡")

        song = Song.load_from_workspace(ws, "project", "곡", order=3)
        assert song is not None
        assert song.order == 3

    def test_absolute_paths_work_without_project_dir(self, tmp_path):
        ws = Workspace.create(tmp_path / "ws")
        self._write_song_json(ws.library_song_dir("곡"), "곡")

        song = Song.load_from_workspace(ws, "project", "곡")
        assert song is not None
        # project_dir 없이도 abs_slides_path가 작동
        assert song.abs_slides_path.is_absolute()
        assert song.abs_slides_path == (
            ws.library_song_dir("곡") / "slides.pptx"
        ).resolve()


class TestSlidesFileAutoDetection:
    """slides.pptx가 없어도 곡 폴더에 pptx가 정확히 1개면 자동 인식."""

    def _song(self, tmp_path):
        from pathlib import Path

        d = tmp_path / "songs" / "song_d"
        d.mkdir(parents=True)
        return d, Song(
            name="song_d", folder=Path("songs/song_d"), project_dir=tmp_path
        )

    def test_single_custom_named_pptx_detected(self, tmp_path):
        d, song = self._song(tmp_path)
        (d / "찬양대회.pptx").write_bytes(b"PK")

        assert song.has_slides is True
        assert song.abs_slides_path == d / "찬양대회.pptx"
        assert song.slide_source == "pptx"

    def test_conventional_name_wins_over_custom(self, tmp_path):
        d, song = self._song(tmp_path)
        (d / "slides.pptx").write_bytes(b"PK1")
        (d / "다른파일.pptx").write_bytes(b"PK2")

        assert song.abs_slides_path == d / "slides.pptx"

    def test_multiple_custom_pptx_is_ambiguous(self, tmp_path):
        d, song = self._song(tmp_path)
        (d / "버전1.pptx").write_bytes(b"PK")
        (d / "버전2.pptx").write_bytes(b"PK")

        assert song.has_slides is False  # 모호 → 인식 안 함
        assert song.slide_source == "none"

    def test_markdown_still_wins_over_custom_pptx(self, tmp_path):
        d, song = self._song(tmp_path)
        (d / "찬양대회.pptx").write_bytes(b"PK")
        (d / "slides.md").write_text("# t\n\n가사\n", encoding="utf-8")

        assert song.slide_source == "markdown"

    def test_detect_slides_file_helper(self, tmp_path):
        from flow.domain.song import detect_slides_file

        d = tmp_path / "empty"
        d.mkdir()
        assert detect_slides_file(d) is None

        (d / "자유이름.pptx").write_bytes(b"PK")
        assert detect_slides_file(d) == d / "자유이름.pptx"

        (d / "slides.pptx").write_bytes(b"PK")
        assert detect_slides_file(d) == d / "slides.pptx"
