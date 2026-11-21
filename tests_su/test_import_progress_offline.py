"""The progress window of an import: its stages, the .skp import with and
without it (same result), and a model dragged from a file being read only
after the drop. Offscreen.
argv: <ingetrazo-src> <extension repo> <a .skp>"""
import os, sys, time
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
SRC, EXT, SKP = [os.path.abspath(a) for a in sys.argv[1:4]]
sys.path[:0] = [SRC, EXT]
from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt
from PySide6.QtWidgets import QApplication, QWidget
qa = QApplication.instance() or QApplication([])
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent, QVector3D
from core.scene import Scene
from core.history import History
import skp_dc_import
from skp_dc_import import progress as P, reader as _r, builder as _b
# As IngeTrazo loads it: the manager finds the .skp extension by this name.
sys.modules["ingetrazo_plugin_skp_dc_import"] = skp_dc_import
sys.modules["ingetrazo_plugin_skp_dc_import.reader"] = _r
sys.modules["ingetrazo_plugin_skp_dc_import.builder"] = _b
from asset_manager import place, progress as AP

fails = []
def ok(c, w):
    print(("PASS " if c else "FAIL ") + w)
    if not c: fails.append(w)

# --- the window ----------------------------------------------------------------------
seen = []
with P.window(None, "Importing…") as cb:
    ok(P.current() is cb, "the window's callback is the current one")
    inner = P.scaled(cb, 0.5, 1.0, "Half")
    inner(0.5)
    v = P.in_thread(lambda: (time.sleep(0.6), 42)[1], cb, "Reading x…")
    ok(v == 42, "in_thread hands back the result")
    try:
        P.in_thread(lambda: 1 / 0, cb, "Reading y…")
        ok(False, "in_thread raises what the work raised")
    except ZeroDivisionError:
        ok(True, "in_thread raises what the work raised")
    dlg = next(w for w in QApplication.topLevelWidgets() if w.windowTitle() == "IngeTrazo")
    ok(dlg.isVisible(), "the window shows once the work takes longer than a moment")
ok(P.current() is None and not dlg.isVisible(), "closed after, and nothing current")
calls = []
probe = lambda f, t=None: calls.append(f)
AP._current = probe
with AP.stage(0.2, 0.6):
    AP.current()(0.5)
AP._current = None
ok(abs(calls[0] - 0.4) < 1e-9, "stage() scales what is reported inside it")

# --- the .skp import with and without the window ------------------------------------
class VP:
    def __init__(self):
        self.scene = Scene(); self.history = History(self.scene); self.prepared = []
    def notify_scene_changed(self): self.scene.version += 1
    def update(self): pass
    def prepare_drawing(self, progress=None):
        for i in range(5):
            progress(i / 5, "Preparing the drawing…")
        self.prepared.append(True)

plain = VP()
rep0 = skp_dc_import.import_file(plain, SKP)
ok(not plain.prepared, "without a window: no extra stage (Console, AI bridge)")
vp = VP(); marks = []
with P.window(None, "Importing…") as cb:
    def spy(f, t=None):
        marks.append((f, t)); cb(f, t)
    rep = skp_dc_import.import_file(vp, SKP, progress=spy)
ok({k: v for k, v in rep.items()} == {k: v for k, v in rep0.items()}, "the same import with the window")
fr = [f for f, _t in marks if f is not None]
ok(fr == sorted(fr) and fr[-1] == 1.0, f"the bar only moves forward, to 100 % ({len(fr)} steps)")
texts = " | ".join(sorted({t for _f, t in marks if t}))
ok("Reading" in texts and "Building the parts" in texts and "Preparing the drawing" in texts,
   f"its stages: {texts}")
ok(vp.prepared == [True], "the drawing is prepared while the window is up")
ok(len(vp.history.undo_stack) == 1, "still one undo step")

# --- a model from a file is read after the drop ----------------------------------------
class Snap:
    def __init__(self, p): self.point = p; self.kind = "on_face"
class Win(QWidget):
    def __init__(self): super().__init__(); self.tools = []
    def _activate_tool(self, name): self.tools.append(name)
class DVP(QWidget):
    def __init__(self, win, scene):
        super().__init__(win); self.scene = scene; self.history = History(scene); self.tool = None
    def set_active_tool(self, t): self.tool = t
    def _snap_at(self, x, y, mods): return Snap(QVector3D(x / 10.0, y / 10.0, 0))
    def flash_status(self, *a): pass
    def notify_scene_changed(self): pass
    def end_group_edit(self): pass
    def window(self): return self.parentWidget()
win = Win(); dvp = DVP(win, Scene()); win.viewport = dvp
drop = place.DropOnView(win)
drop.watch_all()
built = []

def build():
    built.append(AP.current() is not None)
    return place.group_from_file(dvp, SKP), QVector3D(0, 0, 0)

drop.begin(place.from_file(build))
mime = QMimeData(); mime.setData(place.MIME, b"1")
for ev in (QDragEnterEvent(QPoint(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier),
           QDragMoveEvent(QPoint(20, 20), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)):
    drop.eventFilter(dvp, ev)
ok(not built and dvp.tool is None, "nothing is read while the drag is under way")
ev = QDropEvent(QPointF(30, 40), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
ok(drop.eventFilter(dvp, ev) and ev.isAccepted(), "the drop is accepted")
drop.end()
ok(not built, "…and read only once the drop is over")
t0 = time.time()
while not built and time.time() - t0 < 60:
    qa.processEvents(); time.sleep(0.02)
while len(dvp.scene.groups) == 0 and time.time() - t0 < 120:
    qa.processEvents(); time.sleep(0.02)
ok(built == [True], "read with the progress window up")
g = dvp.scene.groups[-1] if dvp.scene.groups else None
o = g.xform.map(QVector3D()) if g is not None and g.xform is not None else None
ok(o is not None and abs(o.x() - 3.0) < 1e-6 and abs(o.y() - 4.0) < 1e-6,
   "placed where it was dropped, in one undo step" if o is None else f"placed where it was dropped ({o.x():.2f}, {o.y():.2f})")
ok(len(dvp.history.undo_stack) == 1, "one undo step")
print("FAILED" if fails else "ALL OK"); sys.exit(1 if fails else 0)
