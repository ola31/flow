"""워크스페이스 폴더를 잘못 고른 경우의 처리.

워크스페이스 루트 대신 그 안의 library/ 나 projects/ 를 고르기 쉽다.
그대로 초기화하면 곡 폴더 안에 library/·projects/ 가 또 생긴다.
"""
from __future__ import annotations

import json

from flow.domain.workspace import Workspace
from flow.ui.workspace_dialog import classify_workspace_choice


def _song(ws: Workspace, name: str) -> None:
    d = ws.library_song_dir(name)
    d.mkdir(parents=True, exist_ok=True)
    (d / "song.json").write_text(json.dumps({"name": name}), encoding="utf-8-sig")


def _project(ws: Workspace, name: str) -> None:
    d = ws.project_dir(name)
    d.mkdir(parents=True, exist_ok=True)
    (d / "project.json").write_text(json.dumps({"name": name}), encoding="utf-8-sig")


class TestClassifyWorkspaceChoice:
    def test_workspace_root_opens(self, tmp_path):
        ws = Workspace.create(tmp_path / "ws")

        assert classify_workspace_choice(ws.root) == ("open", ws.root.resolve())

    def test_library_suggests_the_parent(self, tmp_path):
        ws = Workspace.create(tmp_path / "ws")
        _song(ws, "곡A")

        kind, target = classify_workspace_choice(ws.library_dir)

        assert kind == "parent"
        assert target == ws.root.resolve()

    def test_projects_suggests_the_parent(self, tmp_path):
        ws = Workspace.create(tmp_path / "ws")
        _project(ws, "주간")

        kind, target = classify_workspace_choice(ws.projects_dir)

        assert kind == "parent"
        assert target == ws.root.resolve()

    def test_bare_song_collection_is_refused(self, tmp_path):
        """상위도 워크스페이스가 아닌 곡 모음 — 여기서 초기화하면 안 된다."""
        loose = tmp_path / "곡모음"
        (loose / "곡A").mkdir(parents=True)
        (loose / "곡A" / "song.json").write_text("{}", encoding="utf-8-sig")

        assert classify_workspace_choice(loose) == ("inside", None)

    def test_empty_folder_is_an_init_candidate(self, tmp_path):
        empty = tmp_path / "새폴더"
        empty.mkdir()

        kind, target = classify_workspace_choice(empty)

        assert kind == "init"
        assert target == empty.resolve()

    def test_unrelated_folder_is_an_init_candidate(self, tmp_path):
        other = tmp_path / "문서"
        other.mkdir()
        (other / "메모.txt").write_text("x", encoding="utf-8")

        assert classify_workspace_choice(other)[0] == "init"
