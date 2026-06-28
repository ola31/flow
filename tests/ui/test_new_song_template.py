from __future__ import annotations

from flow.services.markdown import Frontmatter, parse


def test_new_song_template_uses_default_frontmatter():
    """새 곡 마크다운 템플릿은 formatter 설정을 덮어쓰지 않고 전부 디폴트를 쓴다."""
    from flow.ui.main_window import _default_song_markdown

    fm = parse(_default_song_markdown("곡A")).frontmatter
    d = Frontmatter()
    assert fm.main_size == d.main_size
    assert fm.sub_size == d.sub_size
    assert fm.background == d.background
    assert fm.main_color == d.main_color
    assert fm.sub_color == d.sub_color
    # 제목/플레이스홀더는 들어가야 함
    assert "곡A" in _default_song_markdown("곡A")
