# SPDX-License-Identifier: GPL-3.0-or-later
"""A parsed .skp → IngeTrazo groups that keep the file's component tree.

IngeTrazo's own .skp import flattens each top-level object into one group,
which is right for reference geometry but loses what a dynamic component is
made of: its parts. Here every placement becomes a ``Group`` over a mesh
SHARED by every placement of the same definition (IngeTrazo's component
instances: ``xform`` + ``children``, the same model its importer uses for
repeated components), nested as deep as the file nests them.

Each placement that carries Dynamic Components data keeps it in
``group.ext[KEY]``: the definition's dictionary (attributes, formulas,
options) and the instance's own (current values), as SketchUp stores them.

Faces, materials, textures, soft and loose edges are read with IngeTrazo's own
.skp adapter (``formats.skp_openskp``), so they come in exactly as its import
brings them.
"""
from __future__ import annotations

from pathlib import Path

from . import reader

KEY = "skp_dc_import"
_MAX_DEPTH = 32


def _mesh_from(faces, soft_edges, loose_edges):
    """A Mesh from ``(outer, holes, attrs)`` faces in local metres, with the
    file's soft edges marked and its loose lines added (the per-face path of
    ``formats.skp.apply_payload``)."""
    from PySide6.QtGui import QVector3D
    from core.mesh import Mesh

    def q(p):
        return p if hasattr(p, "x") else QVector3D(p[0], p[1], p[2])

    mesh = Mesh()
    for outer, holes, attrs in faces:
        try:
            face = mesh.add_face([q(p) for p in outer],
                                 [[q(p) for p in h] for h in holes] if holes else None)
        except Exception:  # noqa: BLE001 - a degenerate polygon is skipped
            continue
        if attrs:
            face.attrs.update(attrs)
            if not isinstance(face.attrs.get("layer", ""), str):
                # Some newer files give a face's layer as openSKP's internal
                # number (IVAR+set-up.skp: 170280742), not a name. A layer
                # that is not a name broke IngeTrazo's layers panel while it
                # painted its swatch, and Qt aborted a moment later.
                del face.attrs["layer"]
    for a, b in soft_edges or ():
        va, vb = mesh.vertex_at(q(a)), mesh.vertex_at(q(b))
        if va is None or vb is None or va is vb:
            continue
        edge = mesh.find_edge(va, vb)
        if edge is not None:
            edge.soft = True
    for a, b in loose_edges or ():
        try:
            mesh.add_edge(q(a), q(b))
        except ValueError:          # both ends weld to one vertex
            continue
    return mesh


class _FrontUnpainted:
    """A face seen as unpainted on its back, for IngeTrazo's face adapter
    (which otherwise turns a front-unpainted, back-painted face round)."""

    __slots__ = ("_face",)

    def __init__(self, face):
        self._face = face

    def __getattr__(self, name):
        if name == "back_material_id":
            return None
        return getattr(self._face, name)


def _sketchup_sided_faces(so, defn, identity, attr_map):
    """A definition's own faces with SketchUp's two-sided paint: a face
    unpainted on its FRONT keeps that side unpainted (it shows the part's
    paint, which a Material formula sets) and its painted back travels as
    ``attrs["back"]``. IngeTrazo's import instead turns such a face round so
    its painted back fronts, which hides the part's paint: right for plain
    models, wrong for a part whose material a formula drives."""
    pos_m, raw_l, meta = so._defn_geom(defn)
    out = []
    if not meta:
        return out
    wl = so._world_points(pos_m, identity)
    for face, s0, s1, hs in meta:
        back = attr_map.get(getattr(face, "back_material_id", None))
        special = getattr(face, "material_id", None) is None and back is not None
        entry = so._face_entry(_FrontUnpainted(face) if special else face,
                               wl, raw_l, s0, s1, hs, attr_map, None, None, False)
        if entry is None:
            continue
        if special:
            outer, holes, attrs = entry
            attrs = dict(attrs or {})
            attrs["back"] = dict(back)
            entry = (outer, holes, attrs)
        out.append(entry)
    return out


def _register_materials(scene, materials, attr_map) -> None:
    """The file's named materials into the scene registry; a name taken by a
    different recipe lands as «name (2)» and the shared face attrs follow."""
    if not materials:
        return
    from core.materials import Material, register
    if getattr(scene, "materials", None) is None:
        scene.materials = {}
    remap = {}
    for raw in materials:
        mat = Material.from_dict(raw)
        if not mat.name:
            continue
        final = register(scene.materials, mat)
        if final != mat.name:
            remap[mat.name] = final
    if remap:
        for attrs in attr_map.values():
            if attrs.get("mat") in remap:
                attrs["mat"] = remap[attrs["mat"]]


def _register_layers(scene, model, so) -> None:
    from core.layers import Layer
    known = {ly.name for ly in scene.layers}
    for rec in so.file_layer_records(model):
        if rec.get("name") and rec["name"] not in known:
            scene.layers.append(Layer(rec["name"], visible=rec.get("visible", True)))
            known.add(rec["name"])


def build(scene, model, path) -> dict:
    """Add ``model`` (an OpenSKP ``SkpModel`` read from ``path``) to
    ``scene`` keeping its component tree. Returns a report dict. Call it
    inside a command (``SnapshotImport``) so it is one undo step."""
    from PySide6.QtGui import QMatrix4x4
    from core.group import Group
    from formats import openskp_compat
    from formats import skp_openskp as so

    path = Path(path)
    defs = getattr(model, "definitions", {}) or {}
    by_id = {getattr(d, "id", None): d for d in defs.values()}
    root = getattr(model, "root", None)

    attr_map, materials = so._material_attrs(model, str(path))
    records = so.file_layer_records(model)
    so._hidden_tags = openskp_compat.hidden_tags(
        r["name"] for r in records if not r["visible"])
    version = "".join(ch for ch in str(getattr(model, "version", "") or "").lstrip("{")
                      if ch.isdigit() or ch == ".").split(".")[0]
    if not (version.isdigit() and int(version) < 21):
        # 2021+ files: the same per-side projected-texture detection the
        # importer runs (classic files carry the real flag).
        for d in [root, *defs.values()]:
            if d is not None:
                so._mark_projected_faces(d, attr_map)
    _register_materials(scene, materials, attr_map)
    _register_layers(scene, model, so)

    identity = QMatrix4x4()
    meshes: dict = {}
    report = {"placements": 0, "dynamic": 0, "definitions": set(),
              "dynamic_roots": [], "faces": 0}

    def mesh_for(defn, inherited, painted_by_formula=False):
        key = (id(defn), inherited, painted_by_formula)
        mesh = meshes.get(key)
        if mesh is None:
            faces, soft, loose = [], [], []
            if painted_by_formula:
                faces = _sketchup_sided_faces(so, defn, identity, attr_map)
            else:
                # by_id={} : only THIS definition's faces; its instances
                # are placed as children instead of being flattened in.
                so._collect(defn, identity, {}, attr_map, faces, 0, frozenset(),
                            inherited=inherited)
            so._soft_edge_segments(defn, identity, soft)
            so._loose_edge_segments(defn, identity, loose)
            mesh = _mesh_from(faces, soft, loose)
            meshes[key] = mesh
            report["faces"] += len(mesh.faces)
        return mesh

    def place(inst, inherited, depth, top):
        defn = by_id.get(getattr(inst, "ref_idx", None))
        if defn is None or depth > _MAX_DEPTH:
            return None
        # The instance's paint stays ON the part (IngeTrazo, like SketchUp,
        # shows a container's paint on every unpainted face below it), so a
        # Material formula that repaints the part shows; the faces are not
        # baked with it, and every placement shares one mesh.
        definition_da = reader.dynamic_attributes(defn)
        instance_da = reader.dynamic_attributes(inst)
        painted = bool(str(instance_da.get("_material_formula") or
                           definition_da.get("_material_formula") or "").strip())
        group = Group(mesh_for(defn, None, painted),
                      name=getattr(inst, "name", "") or getattr(defn, "name", "") or None)
        mid = getattr(inst, "material_id", None)
        if mid is not None and attr_map.get(mid):
            group.material = dict(attr_map[mid])
        group.xform = so._matrix(inst.matrix)
        group.component = not getattr(defn, "is_group", False)
        layer = getattr(inst, "layer", "") or ""
        if isinstance(layer, str) and layer and layer != "Layer0":
            group.layer = layer
        group.hidden = bool(getattr(inst, "hidden", False))
        report["placements"] += 1
        report["definitions"].add(id(defn))
        if definition_da or instance_da:
            report["dynamic"] += 1
            group.ext = {KEY: {
                "definition": getattr(defn, "name", "") or "",
                "definition_guid": getattr(defn, "guid", "") or "",
                "instance_guid": getattr(inst, "guid", "") or "",
                "is_group": bool(getattr(defn, "is_group", False)),
                "definition_attributes": definition_da,
                "instance_attributes": instance_da,
            }}
            if top:
                report["dynamic_roots"].append(group.name)
        kids = [place(c, None, depth + 1, False)
                for c in getattr(defn, "instances", []) or []]
        group.adopt([k for k in kids if k is not None])
        return group

    added = []
    model_da = reader.dynamic_attributes(model)
    if root is not None and model_da:
        # A dynamic component saved as its own file: the file IS the
        # component. SketchUp keeps its top-level attributes, formulas and
        # options (what the parts call «Name!Attr») on the MODEL, and
        # importing the file inserts ONE component of it whose definition
        # takes them. Placing the parts loose instead would leave them
        # without their parent: every formula that refers to it breaks.
        name = str(model_da.get("_name") or "").strip() or path.stem
        wrapper = Group(mesh_for(root, None), name=name)
        wrapper.xform = QMatrix4x4()
        wrapper.component = True
        wrapper.ext = {KEY: {
            "definition": path.stem,
            "definition_guid": "",
            "instance_guid": "",
            "is_group": False,
            "definition_attributes": model_da,
            "instance_attributes": {},
        }}
        report["placements"] += 1
        report["dynamic"] += 1
        report["dynamic_roots"].append(name)
        kids = [place(inst, None, 1, False)
                for inst in getattr(root, "instances", []) or []]
        wrapper.adopt([k for k in kids if k is not None])
        added.append(wrapper)
    elif root is not None:
        loose = mesh_for(root, None)
        if loose.faces or loose.edges:
            added.append(Group(loose, name=path.stem))
        for inst in getattr(root, "instances", []) or []:
            g = place(inst, None, 0, True)
            if g is not None:
                added.append(g)
    scene.groups.extend(added)
    scene.version += 1
    report["groups"] = len(added)
    report["definitions"] = len(report["definitions"])
    report["meshes"] = len(meshes)
    return report
