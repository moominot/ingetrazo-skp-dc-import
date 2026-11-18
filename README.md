# SketchUp import keeping components (IngeTrazo extension)

**Extensions ▸ Import SketchUp keeping components…** brings a `.skp` into IngeTrazo with:

- its **component tree intact**: every group and component placement becomes a nested
  IngeTrazo component instance, repeated parts share one geometry;
- each part's **SketchUp Dynamic Components data** — the definition's attributes, formulas and
  options, and the instance's current values — in `group.ext["skp_dc_import"]`;
- materials, textures, tags (layers), soft and loose edges and hidden parts, read with
  IngeTrazo's own `.skp` adapter.

Phase 1: components arrive exactly as SketchUp saved them. Re-evaluating formulas when an option
changes is the next step.

## Install

Copy the `skp_dc_import` folder into IngeTrazo's plugins folder
(`%APPDATA%\IngeTrazo\plugins\` on Windows) and restart IngeTrazo.

## Why it carries its own OpenSKP

The OpenSKP bundled with IngeTrazo reads only each instance's attribute dictionaries; SketchUp
keeps a dynamic component's attributes on its definition. `skp_dc_import/_vendor/openskp` is
OpenSKP (MIT, © Ahsan Mehmood) with definition dictionaries added (upstream PR
iamahsanmehmood/openskp#530; commit in `_vendor/OPENSKP_COMMIT`). When IngeTrazo bundles an
OpenSKP that has them, the extension uses that one instead.

## Licence

GPL-3.0-or-later. The vendored OpenSKP keeps its MIT licence (`_vendor/openskp/LICENSE`).
