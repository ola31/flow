"""곡 폴더의 부가 메타데이터 (`meta.json`).

분류(카테고리)를 `song.json`에 넣지 않는 이유: 그 파일은 프로젝트 저장,
단독 곡 저장, 곡 관리 다이얼로그, 인라인 곡 생성 등 여섯 경로에서 통째로
다시 쓰이고, 각 writer는 자기가 아는 키(`name`/`sheets`/`show_sheet_names`)만
남긴다. 분류를 그 안에 두면 구버전 Flow가 프로젝트를 한 번 저장하는 것만으로
값이 조용히 사라진다. 구버전이 존재조차 모르는 파일에 따로 두면 그 일이
일어날 수 없다.

읽기는 `services.song_index`가 mtime 캐시로 감싼다 — 목록을 그릴 때마다
직접 부르지 말고 `song_info(song_dir)["category"]`를 쓸 것.
"""

from __future__ import annotations

import json
from pathlib import Path

META_FILENAME = "meta.json"
_VERSION = 1


def _read(song_dir: Path) -> dict:
    """meta.json을 dict로 읽는다. 없거나 깨졌으면 빈 dict."""
    path = Path(song_dir) / META_FILENAME
    try:
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def read_category(song_dir: Path) -> str:
    """곡의 분류. 파일이 없거나 읽을 수 없으면 빈 문자열."""
    value = _read(song_dir).get("category", "")
    return value if isinstance(value, str) else ""


def set_category(song_dir: Path, category: str) -> None:
    """분류를 기록한다. 빈 문자열이면 해제.

    읽고-수정-쓰기로 처리한다 — 나중에 태그 같은 키가 이 파일에 들어와도
    서로 지우지 않게 하기 위해서다.
    """
    data = _read(song_dir)
    data["version"] = _VERSION
    if category:
        data["category"] = category
    else:
        data.pop("category", None)

    path = Path(song_dir) / META_FILENAME
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    from flow.services import song_index

    song_index.invalidate(Path(song_dir))
