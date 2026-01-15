from PySide6.QtGui import QUndoCommand
from flow.domain.score_sheet import ScoreSheet
from flow.domain.hotspot import Hotspot

class AddHotspotCommand(QUndoCommand):
    def __init__(self, score_sheet: ScoreSheet, hotspot: Hotspot, index: int | None = None, undo_cb=None, redo_cb=None):
        super().__init__(f"핫스팟 추가")
        self.score_sheet = score_sheet
        self.hotspot = hotspot
        self.index = index
        self.undo_cb = undo_cb
        self.redo_cb = redo_cb

    def undo(self):
        self.score_sheet.remove_hotspot(self.hotspot.id)
        if self.undo_cb: self.undo_cb()

    def redo(self):
        self.score_sheet.add_hotspot(self.hotspot, self.index)
        if self.redo_cb: self.redo_cb()

class RemoveHotspotCommand(QUndoCommand):
    def __init__(self, score_sheet: ScoreSheet, hotspot: Hotspot, undo_cb=None, redo_cb=None):
        super().__init__(f"핫스팟 삭제")
        self.score_sheet = score_sheet
        self.hotspot = hotspot
        self.old_order = hotspot.order
        self.undo_cb = undo_cb
        self.redo_cb = redo_cb

    def undo(self):
        self.score_sheet.add_hotspot(self.hotspot, self.old_order)
        if self.undo_cb: self.undo_cb()

    def redo(self):
        self.score_sheet.remove_hotspot(self.hotspot.id)
        if self.redo_cb: self.redo_cb()

class MoveHotspotCommand(QUndoCommand):
    def __init__(self, hotspot: Hotspot, old_pos: tuple[int, int], new_pos: tuple[int, int], update_cb):
        super().__init__(f"핫스팟 이동")
        self.hotspot = hotspot
        self.old_pos = old_pos
        self.new_pos = new_pos
        self.update_cb = update_cb

    def undo(self):
        self.hotspot.x, self.hotspot.y = self.old_pos
        self.update_cb()

    def redo(self):
        self.hotspot.x, self.hotspot.y = self.new_pos
        self.update_cb()

class MapSlideCommand(QUndoCommand):
    def __init__(self, hotspot: Hotspot, verse_index: int, old_slide: int, new_slide: int, update_cb):
        v_name = "후렴" if verse_index == 5 else f"{verse_index + 1}절"
        super().__init__(f"슬라이드 매핑 변경 ({v_name})")
        self.hotspot = hotspot
        self.verse_index = verse_index
        self.old_slide = old_slide
        self.new_slide = new_slide
        self.update_cb = update_cb

    def undo(self):
        self.hotspot.set_slide_index(self.old_slide, self.verse_index)
        self.update_cb()

    def redo(self):
        self.hotspot.set_slide_index(self.new_slide, self.verse_index)
        self.update_cb()
