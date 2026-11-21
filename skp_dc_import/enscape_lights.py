# SPDX-License-Identifier: GPL-3.0-or-later
"""Enscape's lights in a .skp, as Render Studio lights.

Enscape (the SketchUp plug-in) puts each light on a component named
``Enscape.PointLight``, ``Enscape.SpotLight``, ``Enscape.LinearLight``,
``Enscape.RectangularLight`` or ``Enscape.DiskLight``. What makes it a light is
an attribute dictionary ``Enscape.Light`` whose key ``LightData`` holds a small
XML text, e.g.::

    <SketchupLight xsi:type="SketchupSpotLight">
      <Luminosity>1000</Luminosity>
      <BeamAngle>1.0471975511965976</BeamAngle>
    </SketchupLight>

* ``Luminosity`` is in lumens.
* ``BeamAngle`` is in radians (the cone's full angle).
* A point light's ``LightSourceRadius`` is in metres; the other lengths
  (``Length``, ``Width``, a disk's ``LightSourceRadius``) are SketchUp's
  internal inches.
* Enscape has no colour or temperature for a light: it is white.
* The light sits at the component's origin and shines along its own +Z (the
  symbol's cone opens that way); a rectangle's width runs along X and its
  length along Y.
* A linear light is a tube along Y that shines in every direction. Blender
  has no such light, so it comes in as four thin area lights round the tube
  (facing +Z, -Z, +X, -X), a quarter of the lumens each.

No Qt and no XML parser here: the file is untrusted input and only a handful
of numbers are read from it, so they are picked out with a pattern.
"""
from __future__ import annotations

import math
import re
import uuid

#: The attribute dictionary and key Enscape keeps a light's data under.
DICT = "Enscape.Light"
KEY = "LightData"
#: Where Render Studio keeps a light that rides on an object (``group.ext``).
LIGHTS_KEY = "render_studio"

_INCH = 0.0254
_TYPE = re.compile(r'xsi:type\s*=\s*"Sketchup(\w+?)Light"')
_TAGS = ("Luminosity", "LightSourceRadius", "BeamAngle", "Length", "Width")
#: How thin a linear light is, metres (Enscape gives it only a length).
_LINE_THICKNESS = 0.02


def _number(text: str, tag: str):
    m = re.search(r"<%s>\s*([-+0-9.eE]+)\s*</%s>" % (tag, tag), text)
    if not m:
        return None
    try:
        v = float(m.group(1))
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def parse(xml_text) -> dict | None:
    """One Render Studio light (in the component's own axes) from Enscape's
    ``LightData`` text; None when it is not a light we know."""
    if not isinstance(xml_text, str):
        return None
    m = _TYPE.search(xml_text)
    if not m:
        return None
    kind = m.group(1)
    v = {t: _number(xml_text, t) for t in _TAGS}
    lm = v["Luminosity"]
    light = {
        "id": uuid.uuid4().hex[:8],
        "on": True,
        "pos": [0.0, 0.0, 0.0],
        "dir": [0.0, 0.0, 1.0],
        "unit": "lm",
        "power": max(0.0, lm) if lm is not None else 1000.0,
        "kelvin": None,
        "color": [1.0, 1.0, 1.0],
        "shadow": True,
    }
    if kind == "Point":
        light.update(type="point", name="Point light")
        if v["LightSourceRadius"] is not None:
            light["radius"] = v["LightSourceRadius"]
    elif kind == "Spot":
        light.update(type="spot", name="Spot light")
        if v["BeamAngle"] is not None:
            light["spot_angle"] = math.degrees(v["BeamAngle"])
    elif kind == "Linear":
        length = (v["Length"] or 39.37007874015748) * _INCH
        # A tube along Y that shines all round: lights_of() splits it in four.
        light.update(type="area", name="Linear light", shape="rectangle",
                     size=_LINE_THICKNESS, size_y=length, _tube=True)
    elif kind == "Rectangular":
        light.update(type="area", name="Rectangular light", shape="rectangle",
                     size=(v["Width"] or 39.37007874015748) * _INCH,
                     size_y=(v["Length"] or 39.37007874015748) * _INCH)
    elif kind == "Disk":
        radius = (v["LightSourceRadius"] or 19.68503937007874) * _INCH
        light.update(type="area", name="Disk light", shape="disk",
                     size=2.0 * radius, size_y=2.0 * radius)
    else:
        return None
    return light


def _light_data(entity):
    dicts = getattr(entity, "attribute_dictionaries", None) or {}
    block = dicts.get(DICT)
    if isinstance(block, dict):
        return block.get(KEY)
    return None


def _tube(light: dict) -> list:
    """An Enscape linear light is a tube that shines in every direction.
    Render Studio (Blender) has no such light, so it is four thin area lights
    set round the tube's axis (local Y), facing +Z, -Z, +X and -X, each with a
    quarter of the lumens: the sum shines all round, like the tube."""
    length, thick = light["size_y"], light["size"]
    out = []
    for i, (direction, along_y) in enumerate((((0, 0, 1), True), ((0, 0, -1), True),
                                              ((1, 0, 0), False), ((-1, 0, 0), False))):
        part = dict(light, id=uuid.uuid4().hex[:8],
                    name="Linear light %d/4" % (i + 1),
                    dir=[float(c) for c in direction],
                    pos=[c * thick / 2.0 for c in direction],
                    power=light["power"] / 4.0)
        # An area light's width runs along x and its length along y; for a
        # light facing ±Z these are world X and Y, for one facing ±X, -Y and Z.
        part["size"], part["size_y"] = (thick, length) if along_y else (length, thick)
        out.append(part)
    return out


def lights_of(definition, instance) -> list:
    """The Enscape light of a placement (its own data first, else its
    definition's): a list of Render Studio lights (one, or four for a tube)."""
    for entity in (instance, definition):
        light = parse(_light_data(entity)) if entity is not None else None
        if light is not None:
            return _tube(light) if light.pop("_tube", False) else [light]
    return []


def with_lights(ext, lights) -> dict:
    """``group.ext`` with ``lights`` added under Render Studio's key."""
    ext = dict(ext) if isinstance(ext, dict) else {}
    block = dict(ext.get(LIGHTS_KEY) or {}) if isinstance(ext.get(LIGHTS_KEY), dict) else {}
    block["lights"] = list(block.get("lights") or []) + list(lights)
    # The component is only Enscape's symbol of the light: it stays in the
    # drawing, and Render Studio leaves it out of the render.
    block["hide_in_render"] = True
    ext[LIGHTS_KEY] = block
    return ext
