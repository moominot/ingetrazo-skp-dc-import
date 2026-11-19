# SPDX-License-Identifier: GPL-3.0-or-later
"""IngeTrazo groups ⇄ the evaluator: redraw an imported dynamic component.

:func:`redraw_group` reads an imported component (``group.ext[KEY]`` on its
placements, as the importer leaves it), redraws it with :mod:`.redraw` and
returns a NEW group tree: the caller swaps it for the old one inside one
command, so undo puts the old one back whole. Meshes are shared with the old
tree, except the own faces of a part whose contents stretched (baked, as
SketchUp bakes them into the group).

Units: IngeTrazo works in metres, SketchUp's dictionaries in inches.
"""
from __future__ import annotations

import copy as _copy

from .evaluate import _num
from .model import Part, part_name
from .redraw import LEN, decompose, live_value, redraw

KEY = "skp_dc_import"
M_PER_IN = 0.0254


# ---- matrices -----------------------------------------------------------------

def _rows_from_q(q):
    """QMatrix4x4 (metres) → 4×4 row-major list (inches)."""
    d = q.data()                                   # column-major
    m = [[d[c * 4 + r] for c in range(4)] for r in range(4)]
    for r in range(3):
        m[r][3] /= M_PER_IN
    return m


def _q_from_rows(m):
    from PySide6.QtGui import QMatrix4x4
    vals = []
    for r in range(4):
        for c in range(4):
            v = m[r][c]
            if c == 3 and r < 3:
                v *= M_PER_IN
            vals.append(float(v))
    return QMatrix4x4(*vals)


# ---- the part tree -----------------------------------------------------------

def _merged(group) -> dict:
    data = (group.ext or {}).get(KEY) or {}
    attrs = dict(data.get("definition_attributes") or {})
    attrs.update(data.get("instance_attributes") or {})
    attrs["__hidden__"] = bool(getattr(group, "hidden", False))
    return attrs


def _bounds(group, visible_only: bool):
    """The group's own frame bounds (metres): its mesh and, for a part with
    sub-parts, theirs (skipping hidden ones when asked)."""
    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3

    def add(p):
        for i, v in enumerate((p.x(), p.y(), p.z())):
            lo[i] = min(lo[i], v)
            hi[i] = max(hi[i], v)

    def walk(g, m):
        for v in g.mesh.vertices:
            pos = getattr(v, "position", v)
            add(m.map(pos) if m is not None else pos)
        for c in g.children or ():
            if visible_only and getattr(c, "hidden", False):
                continue
            cm = c.xform if m is None else m * c.xform
            walk(c, cm)

    walk(group, None)
    if lo[0] == float("inf"):
        return (0.0, 0.0, 0.0)
    return tuple((hi[i] - lo[i]) / M_PER_IN for i in range(3))


_IDENTITY = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0],
             [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]


def part_tree(group, parent: Part | None = None, edits: dict | None = None) -> Part:
    """The evaluator's view of ``group``'s tree. ``edits`` ({id(group): key
    changes}, see :mod:`.author`) are applied to the attributes read."""
    from .author import DELETE
    attrs = _merged(group)
    for k, v in ((edits or {}).get(id(group)) or {}).items():
        if v is DELETE:
            attrs.pop(k, None)
        else:
            attrs[k] = v
    data = (group.ext or {}).get(KEY) or {}
    part = Part(part_name(attrs, group.name), attrs, parent, [], group)
    # A classic group (no matrix: its mesh in its parent's frame) reads as
    # placed at the identity; it is written back as such an instance.
    part.xform = (_rows_from_q(group.xform) if group.xform is not None
                  else [row[:] for row in _IDENTITY])
    part.base = _bounds(group, visible_only=bool(group.children))
    part.definition = data.get("definition") or group.name or ""
    part.children = [part_tree(c, part, edits) for c in (group.children or ())]
    return part


def is_dynamic_root(group) -> bool:
    data = (group.ext or {}).get(KEY)
    return bool(data and (data.get("definition_attributes") or data.get("instance_attributes")))


# ---- options -------------------------------------------------------------------

def resize_root(root: Part, axis: str, value_in: float) -> None:
    """LenX/LenY/LenZ typed in the options: like SketchUp's dialog, the
    component is scaled so its live size is the value; the redraw then lays
    out its parts for it."""
    live = live_value(root, axis)
    if not live or live <= 1e-9 or root.xform is None:
        return
    f = value_in / live
    i = LEN.index(axis)
    root.xform = [[root.xform[r][c] * (f if c == i else 1.0) for c in range(4)]
                  for r in range(4)]


# ---- back to groups --------------------------------------------------------------

def _value_for_store(v):
    n = _num(v)
    return n if isinstance(n, float) else ("" if v is None else str(v))


def _material_attrs(scene, name):
    """The paint for a part whose Material attribute names ``name``: the
    document's material of that name (case-insensitive), else None."""
    registry = getattr(scene, "materials", None) or {}
    want = str(name).strip().lower()
    for key, mat in registry.items():
        if str(key).strip().lower() == want:
            attrs = getattr(mat, "face_attrs", None)
            return attrs() if callable(attrs) else None
    return None


def redraw_group(root_group, options: dict | None = None, scene=None, edits=None):
    """A new group tree for ``root_group`` redrawn with ``options``
    ({attribute: value}, lengths in INCHES as SketchUp stores them; LenX,
    LenY, LenZ resize the component). ``scene`` resolves Material values
    to the document's materials. ``edits`` ({id(group): key changes}) are
    authoring changes to parts of the tree (see :mod:`.author`), written
    into the new tree. Returns (new root group, evaluator)."""
    from PySide6.QtGui import QMatrix4x4
    from core.group import Group, transformed_mesh

    from .author import apply_changes, new_dynamic_data
    edits = edits or {}
    root = part_tree(root_group, None, edits)
    overrides = {}
    for k, v in (options or {}).items():
        k = k.lower()
        if k in LEN:
            n = _num(v)
            if isinstance(n, float):
                resize_root(root, k, n)
        else:
            overrides[(root, k)] = v
    placed, ev = redraw(root, overrides)

    def build(node, is_root=False):
        tmpl = node.source.handle                       # the group this part was read from
        g = Group(tmpl.mesh, name=tmpl.name)
        for attr in ("layer", "ifc", "billboard", "material", "axes", "locked", "text3d"):
            if hasattr(tmpl, attr):
                setattr(g, attr, _copy.deepcopy(getattr(tmpl, attr)))
        g.component = tmpl.component
        g.hidden = bool(node.hidden)
        if node.material and scene is not None:
            # A Material formula paints the part, as SketchUp paints the
            # instance: faces left with the default material show it.
            paint = _material_attrs(scene, node.material)
            if paint is not None:
                g.material = paint
        if node.xform is not None:
            g.xform = _q_from_rows(node.xform)
        cs = node.content_scale
        if any(abs(v - 1.0) > 1e-9 for v in cs):
            # The part's own faces stretch with its contents (SketchUp bakes
            # this into the definition; a private copy of the mesh here).
            s = QMatrix4x4()
            s.scale(*cs)
            g.mesh = transformed_mesh(tmpl.mesh, s)
        ext = _copy.deepcopy(tmpl.ext) if tmpl.ext else {}
        data = ext.get(KEY)
        changes = edits.get(id(tmpl))
        if changes:
            if data is None:          # a plain part gets its first attribute
                data = ext[KEY] = new_dynamic_data(tmpl.name or "")
                data["instance_attributes"].pop("_lengthunits", None)
            apply_changes(data, changes)
        if data is not None:
            inst = data.setdefault("instance_attributes", {})
            part = node.part
            for attr in _attrs_to_store(part, ev):
                inst[attr] = _value_for_store(ev.value(part, attr))
            if node.copy:
                inst["copy"] = float(node.copy)
            if part.children:
                # Laid out for its new size: that is now its nominal size.
                for a in LEN:
                    v = _num(ev.value(part, a))
                    if isinstance(v, float):
                        inst[f"_{a}_nominal"] = v
            if is_root:
                for (_p, a), v in overrides.items():   # the user's options
                    inst[a] = _value_for_store(v)
        g.ext = ext or None
        g.adopt([build(c) for c in node.children])
        if g.xform is None and node.xform is not None:
            g.xform = _q_from_rows(node.xform)
        return g

    return build(placed, is_root=True), ev


def _attrs_to_store(part: Part, ev):
    """The attributes the redraw set: every one with a formula, plus the
    predefined geometric ones the part carries."""
    names = set()
    for k in part.attrs:
        if k.startswith("_") and k.endswith("_formula") and not k.startswith("_inst_"):
            if str(part.attrs[k] or "").strip():
                names.add(k[1:-8])
    return sorted(names)


# ---- making a component dynamic ---------------------------------------------------

def _clone(g):
    """A new group sharing ``g``'s mesh, with copies of its properties and
    of its sub-tree (so the swap is one clean undo step)."""
    from core.group import Group
    n = Group(g.mesh, name=g.name)
    for attr in ("layer", "ifc", "billboard", "material", "axes", "locked",
                 "text3d", "hidden", "component", "xform", "ext"):
        if hasattr(g, attr):
            v = getattr(g, attr)
            if attr == "xform" and v is not None:
                from PySide6.QtGui import QMatrix4x4
                v = QMatrix4x4(v)
            else:
                v = _copy.deepcopy(v) if attr in ("ext", "material", "ifc", "axes") else v
            setattr(n, attr, v)
    n.adopt([_clone(c) for c in (g.children or ())])
    return n


def make_dynamic_tree(group, name: str | None = None, units: str = "CENTIMETERS"):
    """A copy of ``group`` that is a dynamic component (SketchUp's
    «Make dynamic»), to swap in for it. A classic group gets its axes at its
    bounding box's lower corner first, as a SketchUp component has them, so
    LenX/LenY/LenZ stretch it from there."""
    from PySide6.QtGui import QMatrix4x4, QVector3D
    from core.group import transformed_mesh
    from .author import new_dynamic_data
    new = _clone(group)
    lo = [float("inf")] * 3

    def walk(g, m):
        for v in g.mesh.vertices:
            p = getattr(v, "position", v)
            p = m.map(p) if m is not None else p
            for i, c in enumerate((p.x(), p.y(), p.z())):
                lo[i] = min(lo[i], c)
        for c in g.children or ():
            if c.xform is None:
                walk(c, m)
            else:
                walk(c, c.xform if m is None else m * c.xform)

    walk(group, None)                      # in the group's OWN frame
    if lo[0] != float("inf") and max(abs(v) for v in lo) > 1e-9:
        # Axes to the lower corner of what it holds (where a SketchUp
        # component has them), the group staying where it is in the model.
        to_corner, back = QMatrix4x4(), QMatrix4x4()
        to_corner.translate(QVector3D(*lo))
        back.translate(QVector3D(-lo[0], -lo[1], -lo[2]))
        if group.mesh.vertices:
            new.mesh = transformed_mesh(group.mesh, back)
        for c in new.children or ():
            c.xform = back * c.xform if c.xform is not None else QMatrix4x4(back)
        new.xform = (QMatrix4x4(group.xform) * to_corner) if group.xform is not None else to_corner
        new.axes = None
    ext = dict(new.ext or {})
    data = ext.get(KEY)
    if data is None:
        data = ext[KEY] = new_dynamic_data(name or group.name or "Component", units)
    elif name:
        data.setdefault("instance_attributes", {})["_name"] = name
    new.ext = ext
    return new
