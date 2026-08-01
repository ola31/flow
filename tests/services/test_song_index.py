

class TestStampCoversSheetDirs:
    def test_added_sheet_image_invalidates_cache(self, tmp_path):
        """sheets/ 하위에 이미지가 추가돼도 곡 폴더 mtime은 안 바뀐다 —
        지문이 sheets/ mtime을 포함해야 편집 후 곡 수가 갱신된다."""
        import time

        from flow.services.song_index import song_info

        d = tmp_path / "song_a"
        (d / "sheets").mkdir(parents=True)
        (d / "song.json").write_text('{"name": "song_a"}', encoding="utf-8-sig")

        assert song_info(d)["sheet_count"] == 0
        time.sleep(0.01)
        (d / "sheets" / "p1.png").touch()

        assert song_info(d)["sheet_count"] == 1
