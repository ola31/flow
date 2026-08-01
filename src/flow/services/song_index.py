"""곡 폴더 메타데이터 인덱스 (mtime 키 캐시)

라이브러리 화면·"라이브러리에서 추가" 다이얼로그·홈 패널은 곡마다
`song.json` 파싱 + `slides.md` 전문 읽기 + `sheets/` 나열을 반복한다.
곡이 100개를 넘으면 화면 진입 때마다 수백 번의 디스크 I/O가 GUI 스레드에서
발생하고, 검색은 키 입력마다 그 전체를 다시 돌아 심하게 버벅인다.

이 모듈은 (폴더 mtime, song.json mtime, slides.md mtime)을 키로 결과를
캐시해 같은 정보를 두 번 읽지 않게 한다. 파일이 바뀌면 mtime이 달라져
자동으로 무효화되므로 명시적 갱신이 필요 없다 (이름 변경·삭제처럼 폴더
경로 자체가 바뀌는 경우만 `invalidate`).
"""

from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path
from typing import Any

from flow.domain.song import detect_slides_file

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp"}

# 워크스페이스 하나가 수백 곡이어도 전부 담기도록 넉넉히.
# 항목당 가사 문자열이 대부분이라 곡당 수 KB 수준.
_MAX_ENTRIES = 2048


def _mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


def _stamp(song_dir: Path) -> tuple:
    """캐시 유효성 판정용 mtime 지문. 접근 실패는 0.0으로 낮춘다.

    sheets/ 하위에 이미지를 추가해도 곡 폴더 mtime은 안 바뀌므로
    악보 폴더 mtime을 반드시 포함한다 (빠지면 곡 편집 후 돌아와도
    악보 수가 갱신되지 않는다).
    """
    return (
        _mtime(song_dir),
        _mtime(song_dir / "song.json"),
        _mtime(song_dir / "slides.md"),
        _mtime(song_dir / "sheets"),
        _mtime(song_dir / "sheet"),
    )


class SongIndex:
    """곡 폴더 → 메타데이터 dict 캐시.

    반환되는 dict의 키:
        name, path, sheet_count, first_sheet, has_ppt, has_md, lyrics,
        total_hotspots, mapped_hotspots
    """

    def __init__(self) -> None:
        self._cache: OrderedDict[Path, tuple[tuple, dict[str, Any]]] = OrderedDict()

    def get(self, song_dir: Path) -> dict[str, Any]:
        """곡 폴더 메타데이터 반환 (캐시 히트면 디스크 접근 없음)."""
        song_dir = Path(song_dir)
        stamp = _stamp(song_dir)
        hit = self._cache.get(song_dir)
        if hit is not None and hit[0] == stamp:
            self._cache.move_to_end(song_dir)
            return hit[1]

        info = _scan(song_dir)
        self._cache[song_dir] = (stamp, info)
        self._cache.move_to_end(song_dir)
        while len(self._cache) > _MAX_ENTRIES:
            self._cache.popitem(last=False)
        return info

    def invalidate(self, song_dir: Path | None = None) -> None:
        """폴더 경로가 바뀌는 변경(이름 변경·삭제) 후 캐시 제거."""
        if song_dir is None:
            self._cache.clear()
        else:
            self._cache.pop(Path(song_dir), None)


def _scan(song_dir: Path) -> dict[str, Any]:
    """곡 폴더를 실제로 읽어 메타데이터를 만든다 (가사 제외 — song_lyrics)."""
    result: dict[str, Any] = {"name": song_dir.name, "path": song_dir}

    sheet_count = 0
    first_sheet: Path | None = None
    for sub in ("sheets", "sheet"):
        d = song_dir / sub
        if d.is_dir():
            try:
                imgs = sorted(
                    f for f in d.iterdir()
                    if f.suffix.lower() in _IMAGE_SUFFIXES
                )
            except OSError:
                imgs = []
            sheet_count += len(imgs)
            if first_sheet is None and imgs:
                first_sheet = imgs[0]
    result["sheet_count"] = sheet_count
    result["first_sheet"] = first_sheet

    result["has_ppt"] = detect_slides_file(song_dir) is not None
    result["has_md"] = (song_dir / "slides.md").exists()
    result["name_lower"] = song_dir.name.lower()

    total_hs, mapped_hs = 0, 0
    song_json = song_dir / "song.json"
    if song_json.exists():
        try:
            with open(song_json, encoding="utf-8-sig") as f:
                data = json.load(f)
            for sheet_data in data.get("sheets", []):
                for h in sheet_data.get("hotspots", []):
                    total_hs += 1
                    if h.get("slide_mappings") or h.get("slide_index", -1) >= 0:
                        mapped_hs += 1
        except Exception:
            pass
    result["total_hotspots"] = total_hs
    result["mapped_hotspots"] = mapped_hs
    return result


_INDEX = SongIndex()

# 가사는 slides.md 전문을 읽어야 해서 곡당 비용이 가장 크다. 목록을 그리는
# 데는 필요 없고 가사 검색을 시작할 때만 쓰이므로 따로 지연 캐시한다 —
# "라이브러리에서 추가" 팝업을 여는 것만으로 전 곡의 slides.md를 읽지 않게.
_LYRICS: OrderedDict[Path, tuple[float, str, str]] = OrderedDict()


def song_info(song_dir: Path) -> dict[str, Any]:
    """프로세스 공용 인덱스에서 곡 메타데이터를 조회한다 (가사 제외)."""
    return _INDEX.get(song_dir)


def song_lyrics(song_dir: Path) -> tuple[str, str]:
    """(가사 원문, 소문자 사본) 반환. slides.md가 없으면 ("", "")."""
    from flow.services.markdown import read_song_lyrics

    song_dir = Path(song_dir)
    stamp = _mtime(song_dir / "slides.md")
    hit = _LYRICS.get(song_dir)
    if hit is not None and hit[0] == stamp:
        _LYRICS.move_to_end(song_dir)
        return hit[1], hit[2]

    lyrics = read_song_lyrics(song_dir)
    _LYRICS[song_dir] = (stamp, lyrics, lyrics.lower())
    _LYRICS.move_to_end(song_dir)
    while len(_LYRICS) > _MAX_ENTRIES:
        _LYRICS.popitem(last=False)
    return lyrics, lyrics.lower()


def invalidate(song_dir: Path | None = None) -> None:
    """공용 인덱스 캐시 무효화 (None이면 전체)."""
    _INDEX.invalidate(song_dir)
    if song_dir is None:
        _LYRICS.clear()
    else:
        _LYRICS.pop(Path(song_dir), None)
