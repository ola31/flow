from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from flow.domain.workspace import Workspace
from flow.repository.project_repository import ProjectRepository
from flow.services.markdown import (
    PatchType, SlidePatch, apply_patches, apply_patches_to_text, parse, slide_hash,
)


def test_source_apply_preserves_all_slide_attributes():
    text = '# Song\n\n## Verse :: subtitle\n\n{main_size: 72}\noriginal\n> special\n\nuntouched\n'
    spec = parse(text)
    patch = SlidePatch('p', PatchType.EDIT, 'edited', slide_hash('original'), 0, 't', 'live')
    result = apply_patches_to_text(text, [patch])
    assert '## Verse :: subtitle' in result
    assert parse(result) == apply_patches(spec, [patch])
    assert apply_patches_to_text(text, []) == text


@pytest.mark.parametrize('rename_library', [False, True])
def test_rename_respects_local_override(tmp_path, rename_library):
    ws = Workspace.create(tmp_path / 'ws')
    library = ws.library_song_dir('same')
    local = ws.project_dir('A') / 'songs' / 'same'
    for folder in (library, local):
        folder.mkdir(parents=True)
        (folder / 'song.json').write_text(json.dumps({'name': 'same', 'sheets': []}))
    for name in ('A', 'B'):
        folder = ws.project_dir(name)
        folder.mkdir(exist_ok=True)
        (folder / 'project.json').write_text(json.dumps({
            'id': name, 'name': name, 'selected_songs': [{'name': 'same'}],
            'song_order': ['same'],
        }))
    repo = ProjectRepository(ws.projects_dir)
    repo.rename_song_folder(library if rename_library else local, 'new', workspace=ws)
    for name in ('A', 'B'):
        songs = repo.load_from_workspace(ws, name).selected_songs
        assert len(songs) == 1
        assert songs[0].name == ('new' if (name == 'B') == rename_library else 'same')


def window_method(name, namespace=None):
    # Isolate these control-flow checks from PPT/COM and GUI initialization.
    source = Path(__file__).parents[2] / 'src/flow/ui/main_window.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'MainWindow')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    namespace = namespace or {}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), 'exec'), namespace)
    return namespace[name]


def test_cancelled_or_failed_save_blocks_navigation(monkeypatch):
    import flow.ui.dialogs as dialogs
    monkeypatch.setattr(dialogs, 'flow_save_changes', lambda _: dialogs.SAVE)
    fake = SimpleNamespace(_is_dirty=True, _undo_stack=SimpleNamespace(isClean=lambda: False),
                           _save_project=lambda: None)
    assert window_method('_check_unsaved_changes')(fake) is False
    fake._save_project = lambda: setattr(fake, '_is_dirty', False)
    fake._undo_stack.isClean = lambda: True
    assert window_method('_check_unsaved_changes')(fake) is True


@pytest.mark.parametrize('kind', ['project', 'song'])
@pytest.mark.parametrize('relation', ['same', 'parent', 'child'])
def test_save_as_rejects_overlapping_paths(tmp_path, kind, relation):
    source = tmp_path / 'original'
    source.mkdir()
    marker = source / 'keep.txt'
    marker.write_text('original')
    target = {'same': source, 'parent': tmp_path, 'child': source / 'child'}[relation]
    def unexpected(*args, **kwargs):
        pytest.fail('Overlapping path reached a filesystem mutation')
    notices = []
    ns = {
        'Path': Path,
        'shutil': SimpleNamespace(rmtree=unexpected, copytree=unexpected),
        'QMessageBox': SimpleNamespace(warning=lambda *args: notices.append(args)),
        'QFileDialog': SimpleNamespace(
            getSaveFileName=lambda *args: (str(target) + '.json', ''),
            getExistingDirectory=lambda *args: str(target.parent)),
        'QInputDialog': SimpleNamespace(getText=lambda *args, **kwargs: (target.name, True)),
    }
    song = SimpleNamespace(name='song', project_dir=source)
    fake = SimpleNamespace(_project=SimpleNamespace(name='project', selected_songs=[song]),
                           _project_path=source / 'project.json', _is_standalone=False,
                           _repo=ProjectRepository(tmp_path))
    method = '_save_project_as' if kind == 'project' else '_save_standalone_song_as'
    window_method(method, ns)(fake)
    assert notices
    assert marker.read_text() == 'original'
