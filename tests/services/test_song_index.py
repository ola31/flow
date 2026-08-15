

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


class TestCategory:
    """분류는 meta.json에 있고, 목록을 그리는 화면들은 이 색인으로 읽는다."""

    def test_song_info_carries_the_category(self, tmp_path):
        from flow.services.song_index import invalidate, song_info
        from flow.services.song_meta import set_category

        song_dir = tmp_path / "song_a"
        song_dir.mkdir()
        (song_dir / "song.json").write_text(
            '{"name": "song_a"}', encoding="utf-8-sig"
        )

        assert song_info(song_dir)["category"] == ""

        set_category(song_dir, "바다")
        invalidate(song_dir)

        assert song_info(song_dir)["category"] == "바다"

    def test_meta_change_invalidates_the_cache(self, tmp_path):
        """meta.json만 바뀌어도 색인이 다시 읽어야 한다 (외부 편집 대응)."""
        import os

        from flow.services.song_index import song_info

        song_dir = tmp_path / "song_b"
        song_dir.mkdir()
        (song_dir / "song.json").write_text(
            '{"name": "song_b"}', encoding="utf-8-sig"
        )
        song_info(song_dir)  # 캐시 채우기

        meta = song_dir / "meta.json"
        meta.write_text('{"category": "노을"}', encoding="utf-8")
        stamp = meta.stat().st_mtime + 1  # mtime 해상도가 거친 파일시스템 대비
        os.utime(meta, (stamp, stamp))

        assert song_info(song_dir)["category"] == "노을"
