# SPDX-License-Identifier: GPL-3.0-or-later
"""«Not rendered» for any component: a stand-in that shows in the drawing,
translucent, and is left out of the render.

An Enscape plant or chair comes in from a .skp as a light envelope of the real
thing, which only the online library has. Such a component is a place-holder:
you swap it for a component of your own, or draw into it. This is the property
that says so, and it can be set on any component or group:

* ``group.ext["render_studio"]["hide_in_render"]`` — what Render Studio already
  reads (the symbol of an imported light uses it): the render leaves it out.
* ``group.material`` — the container's own paint turns translucent, so the
  stand-in reads as one (a face painted by itself keeps its own paint). What
  the group wore before is kept in ``ext["render_studio"]["stand_in"]`` and
  comes back when the property is cleared.

It belongs to the placement, not to its definition: a component put in place of
a stand-in is a new placement and renders; one you draw into stays a stand-in
until you clear the property.

No Qt here; the scene change is one undoable command.
"""
from __future__ import annotations

import copy

KEY = "render_studio"
HIDE = "hide_in_render"
SAVED = "stand_in"
#: The translucent paint of a stand-in: a soft green at 30 %.
PAINT = {"color": (0.45, 0.75, 0.55), "opacity": 0.3}
_CMD: dict = {}


def is_stand_in(group) -> bool:
    ext = getattr(group, "ext", None)
    block = ext.get(KEY) if isinstance(ext, dict) else None
    return isinstance(block, dict) and bool(block.get(HIDE))


def selected_groups(selection) -> list:
    """The groups among ``selection`` (a part picked inside one counts as its
    owner), once each."""
    out, seen = [], set()
    for e in selection or ():
        g = getattr(e, "owner", None) or e
        if hasattr(g, "children") and id(g) not in seen:
            seen.add(id(g))
            out.append(g)
    return out


def state_of(groups) -> bool | None:
    """True when all are stand-ins, False when none, None when mixed."""
    flags = {is_stand_in(g) for g in groups}
    return flags.pop() if len(flags) == 1 else None


def stand_in_state(group, on: bool):
    """The ``(ext, material)`` ``group`` takes to be, or stop being, a
    stand-in; the group is not touched."""
    ext = copy.deepcopy(group.ext) if isinstance(getattr(group, "ext", None), dict) else {}
    block = ext.get(KEY)
    block = dict(block) if isinstance(block, dict) else {}
    material = getattr(group, "material", None)
    if on:
        if SAVED not in block:
            block[SAVED] = {"material": copy.deepcopy(material)}
        block[HIDE] = True
        material = dict(PAINT)
    else:
        saved = block.pop(SAVED, None)
        block.pop(HIDE, None)
        if isinstance(saved, dict):
            material = copy.deepcopy(saved.get("material"))
    if block:
        ext[KEY] = block
    else:
        ext.pop(KEY, None)
    return (ext or None), material


def _command_class():
    cls = _CMD.get("cmd")
    if cls is not None:
        return cls
    from core.history import Command

    class StandInCommand(Command):
        """Set or clear the stand-in property on each group (ext + paint)."""

        keeps_paint = False

        def __init__(self, items):
            self.items = [list(it) for it in items]     # [group, ext, material]

        def _swap(self, scene):
            for it in self.items:
                g = it[0]
                was = (g.ext, g.material)
                g.ext, g.material = it[1], it[2]
                it[1], it[2] = was
            scene.version += 1

        def do(self, scene):
            self._swap(scene)

        def undo(self, scene):
            self._swap(scene)

    _CMD["cmd"] = StandInCommand
    return StandInCommand


def set_stand_in(viewport, groups, on: bool) -> int:
    """Make ``groups`` stand-ins (``on``) or ordinary again, one undo step.
    Returns how many changed."""
    items = []
    for g in groups:
        if is_stand_in(g) == bool(on):
            continue
        ext, material = stand_in_state(g, on)
        items.append((g, ext, material))
    if not items:
        return 0
    viewport.history.execute(_command_class()(items))
    try:
        from core.history import _dirty_group_chunks
        _dirty_group_chunks(viewport.scene)
    except Exception:  # noqa: BLE001
        pass
    for fn in ("notify_scene_changed", "update"):
        f = getattr(viewport, fn, None)
        if callable(f):
            f()
    return len(items)
