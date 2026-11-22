# SPDX-License-Identifier: GPL-3.0-or-later
"""Enscape's library objects in a .skp, as stand-ins.

A plant, a tree or a chair from Enscape's online library (Chaos Cosmos) comes
into the .skp as a component named after it («Creeper Plant 064: English Ivy
Glacier») whose definition has an attribute dictionary ``Enscape.Asset``::

    {"Id": "7aeb1ef7-7ac2-449f-be81-ad9b8543246f", "Source": "REMOTE"}

The file holds no geometry of the real object: only a light envelope that
Enscape swaps for it while rendering, and nothing local has it. So here it
comes in as a *stand-in*: the envelope stays in the drawing, translucent, and
the render leaves it out (``ext["render_studio"]["hide_in_render"]``, the same
mark an Enscape light's symbol gets). The user swaps it for a component of their
own or draws into it, and clears the property when the real thing is there. The
library Id and name are kept in ``ext["enscape_asset"]``.
"""
from __future__ import annotations

import copy

DICT = "Enscape.Asset"
#: Where the library data stays on the group.
KEY = "enscape_asset"
#: Render Studio's block of ``group.ext`` and the marks in it (see
#: ``asset_manager.stand_in``, which clears or sets them from the menu).
RS_KEY = "render_studio"
HIDE = "hide_in_render"
SAVED = "stand_in"
#: A soft green at 30 %: how a stand-in shows in the drawing.
PAINT = {"color": (0.45, 0.75, 0.55), "opacity": 0.3}
#: Face attrs that make a face's paint (core.mesh.PAINT_KEYS) and its back's.
_PAINT = ("color", "mat", "texture", "opacity")


def asset_of(definition, instance=None) -> dict | None:
    """``{"id", "source"}`` of the Enscape library object a placement is (its
    own data first, else its definition's), or None."""
    for entity in (instance, definition):
        dicts = getattr(entity, "attribute_dictionaries", None) or {}
        block = dicts.get(DICT)
        if isinstance(block, dict) and (block.get("Id") or block.get("Source")):
            return {"id": str(block.get("Id") or ""), "source": str(block.get("Source") or "")}
    return None


def strip_paint(mesh) -> None:
    """The envelope's own colours mean nothing (it stands in for something
    else): drop them so the stand-in's translucent paint shows on every face."""
    for face in getattr(mesh, "faces", ()) or ():
        attrs = getattr(face, "attrs", None)
        if isinstance(attrs, dict):
            for k in [k for k in attrs if k in _PAINT or k.startswith("back_")]:
                attrs.pop(k, None)


def with_stand_in(ext, asset: dict, material) -> dict:
    """``group.ext`` with the library data and the stand-in marks added;
    ``material`` is the paint the placement wore (kept to give back)."""
    ext = dict(ext) if isinstance(ext, dict) else {}
    ext[KEY] = dict(asset)
    block = ext.get(RS_KEY)
    block = dict(block) if isinstance(block, dict) else {}
    block[HIDE] = True
    block.setdefault(SAVED, {"material": copy.deepcopy(material)})
    ext[RS_KEY] = block
    return ext
