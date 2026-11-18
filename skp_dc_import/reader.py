# SPDX-License-Identifier: GPL-3.0-or-later
"""Reading a .skp with its Dynamic Components data.

The OpenSKP that IngeTrazo bundles reads only each instance's own attribute
dictionaries. SketchUp keeps a dynamic component's attributes, formulas and
options on the component's DEFINITION, so this extension carries its own copy
of OpenSKP (``_vendor/openskp``, MIT) with ``Definition.attribute_dictionaries``
(upstream PR iamahsanmehmood/openskp#530). Once IngeTrazo bundles an OpenSKP
that has it, :func:`openskp_module` prefers the bundled one.
"""
from __future__ import annotations

import dataclasses
import math

DA = "dynamic_attributes"


def _has_definition_dicts(module) -> bool:
    try:
        fields = {f.name for f in dataclasses.fields(module.model.Definition)}
    except Exception:  # noqa: BLE001 - any odd build: use ours
        return False
    return "attribute_dictionaries" in fields


def openskp_module():
    """The OpenSKP to read with: IngeTrazo's when it already reads definition
    dictionaries, else the copy shipped with this extension."""
    try:
        import openskp as bundled  # IngeTrazo's own
        if _has_definition_dicts(bundled):
            return bundled
    except Exception:  # noqa: BLE001
        pass
    from ._vendor import openskp as vendored
    return vendored


def parse(path):
    """The parsed ``SkpModel`` of ``path``."""
    return openskp_module().SkpFile.open(str(path)).parse()


def json_safe(value):
    """``value`` as something the .igz (JSON) keeps: tuples become lists,
    non-finite floats and unknown objects become strings."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    return str(value)


def dynamic_attributes(entity) -> dict:
    """The ``dynamic_attributes`` dictionary of an instance or definition,
    JSON-safe ({} when it has none)."""
    dicts = getattr(entity, "attribute_dictionaries", None) or {}
    return json_safe(dicts.get(DA) or {})
