# SPDX-License-Identifier: GPL-3.0-or-later
"""What the drawing holds: its components, grouped by name, with a count and
whether they are dynamic. Pure Python over the scene: no Qt."""
from __future__ import annotations

from dataclasses import dataclass, field

#: Where the dynamic-components extensions keep SketchUp's attributes.
DC_KEY = "skp_dc_import"


@dataclass
class Entry:
    name: str
    dynamic: bool = False
    instances: list = field(default_factory=list)   # the Group objects

    @property
    def count(self) -> int:
        return len(self.instances)

    @property
    def sample(self):
        return self.instances[0]


def is_dynamic(group) -> bool:
    """A component carrying Dynamic Components attributes (its own or its
    definition's)."""
    data = (getattr(group, "ext", None) or {}).get(DC_KEY)
    if not isinstance(data, dict):
        return False
    return bool(data.get("definition_attributes") or data.get("instance_attributes"))


def display_name(group) -> str:
    data = (getattr(group, "ext", None) or {}).get(DC_KEY)
    name = ""
    if isinstance(data, dict):
        name = str(data.get("definition") or "")
    return name or str(getattr(group, "name", "") or "Component")


def components_in(scene) -> list[Entry]:
    """Every component placement of the scene (nested ones included),
    grouped by name; dynamic ones flagged. Sorted by name."""
    from core.purge import iter_groups
    found: dict[str, Entry] = {}
    for g in iter_groups(getattr(scene, "groups", ())):
        is_comp = getattr(g, "is_component", None)
        if not ((callable(is_comp) and is_comp()) or is_dynamic(g)):
            continue
        name = display_name(g)
        e = found.setdefault(name, Entry(name))
        e.instances.append(g)
        e.dynamic = e.dynamic or is_dynamic(g)
    return sorted(found.values(), key=lambda e: e.name.lower())
