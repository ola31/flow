"""변환 캐시 정리 테스트 — 같은 원본의 옛 mtime 캐시 자동 삭제."""
from __future__ import annotations

from pathlib import Path

from flow.services.slide_converter import _SOURCE_MARKER, _prune_stale_caches


def _cache_dir(base: Path, name: str, src: str | None) -> Path:
    d = base / name
    d.mkdir(parents=True)
    (d / "slide_0.png").write_bytes(b"png")
    if src is not None:
        (d / _SOURCE_MARKER).write_text(src, encoding="utf-8")
    return d


class TestPruneStaleCaches:
    def test_removes_old_versions_of_same_source(self, tmp_path):
        base = tmp_path / "cache"
        src_file = tmp_path / "deck.pptx"
        src_file.write_bytes(b"PK")
        src = str(src_file.resolve())

        old1 = _cache_dir(base, "hash_old1", src)
        old2 = _cache_dir(base, "hash_old2", src)
        other = _cache_dir(base, "hash_other", str(tmp_path / "other.pptx"))
        keep = _cache_dir(base, "hash_new", None)

        _prune_stale_caches(base, src_file, keep)

        assert not old1.exists() and not old2.exists()
        assert other.exists()  # 다른 파일의 캐시는 유지
        assert keep.exists()
        # 새 폴더에 원본 마커가 기록됨 (다음 편집 때 정리 대상이 되도록)
        assert (keep / _SOURCE_MARKER).read_text(encoding="utf-8") == src

    def test_keeps_markerless_legacy_dirs(self, tmp_path):
        base = tmp_path / "cache"
        src_file = tmp_path / "deck.pptx"
        src_file.write_bytes(b"PK")
        legacy = _cache_dir(base, "hash_legacy", None)  # 마커 없는 구버전
        keep = _cache_dir(base, "hash_new", None)

        _prune_stale_caches(base, src_file, keep)

        assert legacy.exists()  # 원본 불명 → 안전하게 유지
        assert keep.exists()
