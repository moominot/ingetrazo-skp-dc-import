# SPDX-License-Identifier: GPL-3.0-or-later
"""What the drawing holds: its components, grouped by definition, with a
count and whether they are dynamic. Pure Python over the scene: no Qt."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

#: Where the dynamic-components extensions keep the .skp attributes.
DC_KEY = "skp_dc_import"
_UNIQUE_SUFFIX = re.compile(r"#\d+$")


@dataclass
class Entry:
    name: str
    key: tuple = ()
    dynamic: bool = False
    instances: list = field(default_factory=list)   # the Group objects

    @property
    def count(self) -> int:
        return len(self.instances)

    @property
    def sample(self):
        return self.instances[0]


def is_dynamic(group) -> bool:
    """A component carrying dynamic attributes (its own or its
    definition's)."""
    data = (getattr(group, "ext", None) or {}).get(DC_KEY)
    if not isinstance(data, dict):
        return False
    return bool(data.get("definition_attributes") or data.get("instance_attributes"))


def is_component(group) -> bool:
    is_comp = getattr(group, "is_component", None)
    return bool((callable(is_comp) and is_comp()) or is_dynamic(group))


def display_name(group) -> str:
    data = (getattr(group, "ext", None) or {}).get(DC_KEY)
    name = ""
    if isinstance(data, dict):
        name = str(data.get("definition") or "")
    return name or str(getattr(group, "name", "") or "Component")


def definition_key(group) -> tuple:
    """What makes two placements «the same component». Copies share their
    prototype mesh; a dynamic component is redrawn into a new tree on each
    change of options, so it is known by its definition's name instead
    («Barana#2», the name a redrawn copy gets in a .skp, is still «Barana»)."""
    if is_dynamic(group):
        return ("dc", _UNIQUE_SUFFIX.sub("", display_name(group)).strip().lower())
    return ("mesh", id(getattr(group, "mesh", None)))


def walk(groups, seen=None):
    """Every group of ``groups`` and below, each once, without going inside
    a dynamic component: its parts (the slats of a railing, the leaves of a
    door) are driven by the component and are not components to manage."""
    seen = set() if seen is None else seen
    for g in groups or ():
        if id(g) in seen:
            continue
        seen.add(id(g))
        yield g
        if not is_dynamic(g):
            yield from walk(getattr(g, "children", None), seen)


def components_in(scene) -> list[Entry]:
    """Every component placement of the scene (nested ones included, but
    not the parts inside a dynamic component), grouped by definition;
    dynamic ones flagged. Sorted by name."""
    found: dict[tuple, Entry] = {}
    for g in walk(getattr(scene, "groups", ())):
        if not is_component(g):
            continue
        key = definition_key(g)
        e = found.get(key)
        if e is None:
            e = found[key] = Entry(display_name(g), key)
        e.instances.append(g)
        e.dynamic = e.dynamic or is_dynamic(g)
    return sorted(found.values(), key=lambda e: e.name.lower())


def context_members(scene) -> list:
    """The groups the user can select where they are editing: the top-level
    ones, or the parts of the open group."""
    ctx = getattr(scene, "edit_group", None)
    if ctx is None:
        return list(getattr(scene, "groups", None) or [])
    return list(getattr(ctx, "children", None) or [])


def instances_of(scene, key: tuple) -> tuple[list, int]:
    """(the placements of ``key`` that can be selected where the user is
    editing, how many there are in the whole model)."""
    here = [g for g in context_members(scene) if is_component(g) and definition_key(g) == key]
    total = sum(1 for g in walk(getattr(scene, "groups", ()))
                if is_component(g) and definition_key(g) == key)
    return here, total


def selected_component(selection):
    """The one component selected (a part picked inside a group counts as
    its top-level owner), else None."""
    found = None
    for e in selection or ():
        g = getattr(e, "owner", None) or e
        if not hasattr(g, "children") or not is_component(g):
            continue
        if found is not None and found is not g:
            return None
        found = g
    return found
