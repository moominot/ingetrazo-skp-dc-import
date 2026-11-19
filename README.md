# SketchUp Dynamic Components for IngeTrazo

An [IngeTrazo](https://github.com/ingelibre/ingetrazo) extension to bring SketchUp **dynamic
components** in, use them, and make new ones, with the same rules SketchUp follows.

- **Import SketchUp keeping components…** opens a `.skp` with its component tree intact, every
  part a nested IngeTrazo component, and each part's Dynamic Components attributes, formulas and
  options kept, in SketchUp's own format.
- **Component Options**: the options a component shows its users (text fields, lists,
  read-only values, in their units). **Apply** redraws it: copies, hidden parts, sizes,
  positions, rotations and materials, as SketchUp would. Changing LenX/LenY/LenZ resizes it the
  way SketchUp's dialog does.
- **Component Attributes**: **Make dynamic**, then per part: attributes with a value or a
  `=formula`, the predefined ones (X, Y, Z, LenX…, RotX…, Hidden, Material, Copies…) or your
  own, and how each one shows to users (label, access, units, list choices).

Every change is one undo step. Version 0.2.0, for IngeTrazo 0.6 (Extension API 2).

## Install

Download `skp_dc_import-<version>.zip` from the
[releases](https://github.com/moominot/ingetrazo-skp-dc-import/releases) and unpack it in
IngeTrazo's plugins folder (**Extensions ▸ Open plugins folder**; `%APPDATA%\IngeTrazo\plugins\`
on Windows), so that `…/plugins/skp_dc_import/__init__.py` exists. Restart IngeTrazo.

The commands are in the **Extensions** menu and in the right-click menu of a selected
component. The two panels open from there (and from **Window ▸ Panels**).

## How close to SketchUp

The behaviour was taken from SketchUp 2026 itself: real components and synthetic probes,
redrawn by SketchUp's own Dynamic Components engine and compared part by part (every
placement's transform) with this extension's redraw. Some of what that showed:

- X/Y/Z, LenX/LenY/LenZ and RotX… are **live**: without a formula, a part keeps what its
  placement says (its nominal size × scale for a part with sub-parts).
- A part with sub-parts is redrawn at scale 1 and **stretches its contents** by new/old size;
  the sub-parts' own formulas then set what they control. Copies are not stretched.
- `IF` takes only a **positive** number as true; `IF(-1, a, b)` gives `b`.
- A part's `_lengthunits` is **its own**, not inherited: a part without it reads formulas in
  inches.
- Names resolve to the part itself, its ancestors, siblings and children only; anything
  further fails, and the attribute keeps its value (SketchUp does the same).
- A definition's `_inst__…` keys are a template for new copies, not formulas.

On four real components (about 1,900 formulas, up to three levels of nesting), the redraw
matched SketchUp's on every visible part, and on 23 of 24 option and size changes. The known
difference: a stair landing's base, which SketchUp leaves unstretched when the stair gets wider.

`tests_su/` holds the comparison scripts. They need SketchUp dumps of your own models (not
included), except `test_author_offline.py`, whose cabinet is built the same way in both
programs.

## Limits

- One way: components made or changed here are not written back to SketchUp as dynamic
  components (IngeTrazo's `.skp` export is off).
- Not supported: OnClick and animations, `FACEAREA`-style geometry functions, and the
  functions the formula interpreter lacks (see `skp_dc_import/dc/formula.py`).

## Why it carries its own OpenSKP

The OpenSKP bundled with IngeTrazo reads only each instance's attribute dictionaries; SketchUp
keeps a dynamic component's attributes on its definition. `skp_dc_import/_vendor/openskp` is
OpenSKP (MIT, © Ahsan Mehmood) with definition dictionaries added (upstream PR
[iamahsanmehmood/openskp#530](https://github.com/iamahsanmehmood/openskp/pull/530); commit in
`_vendor/OPENSKP_COMMIT`). When IngeTrazo bundles an OpenSKP that has them, the extension uses
that one instead.

## Credits and licence

GPL-3.0-or-later.

- The formula interpreter (`dc/formula.py`, `dc/messages.py`) comes from d1rty-pixel's
  [Dynamic Components for IngeTrazo](https://github.com/d1rty-pixel/ingetrazo-dynamic-components)
  (GPL-3.0), extended here.
- The vendored OpenSKP keeps its MIT licence (`_vendor/openskp/LICENSE`).
- Faces, materials and textures are read with IngeTrazo's own `.skp` adapter.
