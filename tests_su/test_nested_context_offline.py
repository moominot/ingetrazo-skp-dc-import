"""A dynamic component inside another group, edited while that group is
open: the panels find it, Apply and the attribute edits redraw it in place
(inside the open group, not at the top level), and undo/redo put it back.
argv: <ingetrazo-src> <extension repo>"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
SRC, EXT = [os.path.abspath(a) for a in sys.argv[1:3]]
sys.path[:0] = [SRC, EXT]
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
from PySide6.QtGui import QVector3D, QMatrix4x4
from core.group import Group
from core.history import History
from core.mesh import Mesh
from core.scene import Scene
from dc_tools import ui, ui_author
from dc_tools.dc import apply as A, author as AU

CM = 0.01
fails = []


def check(ok, what):
    print(("OK " if ok else "BAD"), what)
    if not ok:
        fails.append(what)


def box(w, d, h):
    m = Mesh()
    P = lambda a, b, c: QVector3D(a * CM, b * CM, c * CM)
    for quad in ([P(0,0,0), P(0,d,0), P(w,d,0), P(w,0,0)], [P(0,0,h), P(w,0,h), P(w,d,h), P(0,d,h)],
                 [P(0,0,0), P(w,0,0), P(w,0,h), P(0,0,h)], [P(0,d,0), P(0,d,h), P(w,d,h), P(w,d,0)],
                 [P(0,0,0), P(0,0,h), P(0,d,h), P(0,d,0)], [P(w,0,0), P(w,d,0), P(w,d,h), P(w,0,h)]):
        m.add_face(quad)
    return m


def part(name, x, y, z, w, d, h):
    g = Group(box(w, d, h), name=name)
    t = QMatrix4x4(); t.translate(QVector3D(x * CM, y * CM, z * CM))
    g.xform = t
    return g


def cabinet():
    root = Group(Mesh(), name="armari")
    root.adopt([part("lateral", 0, 0, 0, 1.8, 40, 100), part("lateral2", 78.2, 0, 0, 1.8, 40, 100),
                part("prestatge", 1.8, 0, 50, 76.4, 40, 1.8)])
    root.xform = None
    root = A.make_dynamic_tree(root, "armari")
    L, R, S = root.children
    edits = {
        id(root): {**AU.set_changes("n", value="3"),
                   "_n_access": "TEXTBOX", "_n_formlabel": "Prestatges"},
        id(R): {"_name": "lateral2", **AU.set_changes("x", formula="parent!lenx-lenx")},
        id(S): {"_name": "prestatge",
                **AU.set_changes("x", formula="1.8"), **AU.set_changes("lenx", formula="parent!lenx-3.6"),
                **AU.set_changes("copies", formula="parent!n-1"),
                **AU.set_changes("z", formula="(copy+1)*parent!lenz/parent!n")},
    }
    return A.redraw_group(root, {}, None, edits)[0]


class VP:
    def __init__(self, scene):
        self.scene = scene
        self.history = History(scene)
    def update(self): pass


class FakeApp:
    def __init__(self, vp): self.viewport = vp


def shelves(g):
    return sum(1 for c in g.children if (AU.merged(c).get("_name") or c.name) == "prestatge")


scene = Scene()
arm = cabinet()
t = QMatrix4x4(); t.translate(QVector3D(2.0, 1.0, 0.0))
arm.xform = t * arm.xform if arm.xform is not None else t
room = Group(box(300, 300, 1), name="habitacio")
room.adopt([arm])
t2 = QMatrix4x4(); t2.translate(QVector3D(5.0, 0.0, 0.0))
room.xform = t2
scene.groups.append(room)
vp = VP(scene)
check(shelves(arm) == 3, "cabinet built with 3 shelves (n=3)")

# --- opened the room, selected the cabinet --------------------------------------
scene.begin_group_edit(room)
scene.selection.add(arm)
check(ui.selected_root(scene) is arm, "Options: finds the dynamic component inside the open group")
check(ui_author.selected_top(scene) is arm, "Attributes: finds the component inside the open group")

panel = ui.OptionsPanel(FakeApp(vp))
panel.show_group(ui.selected_root(scene))
rows = {opt.label: w for opt, w, _ in panel.rows}
check("Prestatges" in rows, "Options: shows the cabinet's option")
rows["Prestatges"].setText("5")
panel.apply()
print("   status:", panel.status.text())
new = panel.group
check(new is not None and new is not arm, "Apply: redrawn")
check(new in room.children and arm not in room.children, "Apply: the new tree took its place inside the open group")
check(new not in scene.groups and room in scene.groups, "Apply: nothing added at the top level")
check(new is not None and shelves(new) == 5, "Apply: 5 shelves (n=5)")
check(scene.edit_group is room, "Apply: the group stays open")
check(new in scene.selection and arm not in scene.selection, "Apply: the selection follows")

vp.history.undo()
check(arm in room.children and new not in room.children, "Undo: the old cabinet is back")
vp.history.redo()
check(new in room.children and arm not in room.children, "Redo: the redrawn one again")

# --- the Attributes panel, same context ------------------------------------------
scene.selection.clear(); scene.selection.add(new)
apanel = ui_author.AttributesPanel(FakeApp(vp))
apanel.show_root(ui_author.selected_top(scene), ())
check(apanel.root is new, "Attributes: shows the component inside the open group")
before = new
apanel._commit(AU.set_changes("n", value="2"), "n=2")
after = apanel.root
check(after is not before and after in room.children and after not in scene.groups,
      "Attributes edit: redrawn in place inside the open group")
check(after is not None and shelves(after) == 2, "Attributes edit: 2 shelves (n=2)")
vp.history.undo()
check(before in room.children and after not in room.children, "Attributes edit: undo")

# --- a plain group made dynamic while inside another group -----------------------
plain = part("caixa", 10, 10, 0, 20, 20, 20)
scene.end_group_edit()
room.adopt(list(room.children) + [plain])
scene.begin_group_edit(room)
scene.selection.add(plain)
check(ui_author.selected_top(scene) is plain, "Make dynamic: finds a plain group inside the open group")
apanel.show_root(plain, ())
ui_author.QInputDialog.getText = staticmethod(lambda *a, **k: ("caixa", True))
apanel.make_dynamic()
made = apanel.root
check(made is not plain and made in room.children and A.is_dynamic_root(made),
      "Make dynamic: swapped in place inside the open group")

# --- back at the top level --------------------------------------------------------
scene.end_group_edit()
scene.selection.clear(); scene.selection.add(room)
check(ui.selected_root(scene) is None, "Top level: a plain group is not a dynamic component")

# --- a dynamic component inside an open DYNAMIC component -------------------------
from core.group import iter_placements


def world_boxes(g):
    """Every placement's world box corners (cm), by name: where things are."""
    out = []
    for pg, m in iter_placements(g):
        if not pg.mesh.vertices:
            continue
        pts = [(m.map(v.position) if m is not None else v.position) for v in pg.mesh.vertices]
        lo = [round(min(getattr(p, a)() for p in pts) / CM, 2) for a in ("x", "y", "z")]
        hi = [round(max(getattr(p, a)() for p in pts) / CM, 2) for a in ("x", "y", "z")]
        out.append((pg.name, lo, hi))
    return sorted(out)


def height(g):
    """The side boards' height (cm): what LenZ sets."""
    b = [b for b in world_boxes(g) if b[0] == "lateral"][0]
    return b[2][2] - b[1][2]


scene2 = Scene()
cab = cabinet()
t = QMatrix4x4(); t.translate(QVector3D(0.5, 0.0, 0.0))
cab.xform = t * cab.xform
kit = Group(box(200, 60, 2), name="cuina")
kit.adopt([cab])
kit = A.make_dynamic_tree(kit, "cuina")
kit, ev = A.redraw_group(kit, {}, None, {
    id(kit): {**AU.set_changes("alt", value=str(120 / 2.54)), "_alt_units": "CENTIMETERS"},
    id(kit.children[0]): AU.set_changes("lenz", formula="parent!alt"),
})
check(not ev.errors, f"kitchen: built without formula errors {ev.errors}")
place = QMatrix4x4(); place.translate(QVector3D(3.0, 2.0, 0.0)); place.rotate(90, 0, 0, 1)
kit.xform = place * kit.xform
scene2.groups.append(kit)
vp2 = VP(scene2)
cab = kit.children[0]
check(abs(height(cab) - 120) < 0.01, f"kitchen: cabinet 120 cm high from parent!alt ({height(cab)})")
before_boxes = world_boxes(kit)

scene2.begin_group_edit(kit)
scene2.selection.add(cab)
check(ui.selected_root(scene2) is cab, "nested: Options finds the cabinet inside the open kitchen")
p2 = ui.OptionsPanel(FakeApp(vp2))
p2.show_group(ui.selected_root(scene2))
rows = {opt.label: w for opt, w, _ in p2.rows}
rows["Prestatges"].setText("4")
p2.apply()
cab2 = p2.group
print("   status:", p2.status.text())
check(cab2 is not cab and cab2 in kit.children, "nested: redrawn in place inside the open kitchen")
check(shelves(cab2) == 4, "nested: 4 shelves")
check(abs(height(cab2) - 120) < 0.01, f"nested: still 120 cm high ({height(cab2)})")
sides = lambda g: [b for b in world_boxes(g) if b[0].startswith("lateral")]
check(sides(cab2) == [b for b in before_boxes if b[0].startswith("lateral")],
      "nested: the cabinet stays where it was in the world (rotated, moved kitchen)")

# A formula that needs the parent: only right if Parent resolves.
a2 = ui_author.AttributesPanel(FakeApp(vp2))
scene2.selection.clear(); scene2.selection.add(cab2)
a2.show_root(ui_author.selected_top(scene2), ())
a2._commit(AU.set_changes("lenz", formula="parent!alt-20"), "lenz")
cab3 = a2.root
print("   status:", a2.status.text())
check(cab3 in kit.children and abs(height(cab3) - 100) < 0.01,
      f"nested: LenZ = parent!alt-20 gives 100 cm ({height(cab3)})")

# Out of the kitchen, its own redraw agrees with what was done inside it.
scene2.end_group_edit()
inside = world_boxes(kit)
again, ev = A.redraw_group(kit, {}, scene2)
check(world_boxes(again) == inside, "nested: redrawing the whole kitchen changes nothing")

print("FAILED:" if fails else "ALL OK", len(fails) or "")
sys.exit(1 if fails else 0)
