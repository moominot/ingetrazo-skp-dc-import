# SketchUp files and Dynamic Components for IngeTrazo

Three [IngeTrazo](https://github.com/ingelibre/ingetrazo) extensions that share one data format
(SketchUp's own Dynamic Components attributes, kept in `group.ext["skp_dc_import"]`) and
install independently:

| Extension | Folder | What it does |
|---|---|---|
| **SketchUp files** | `skp_dc_import/` | Import a `.skp` keeping its component tree and its Dynamic Components data; export the document as a `.skp`. Carries OpenSKP; the export needs a blank `.skp` (see below). |
| **Dynamic components** | `dc_tools/` | Component Options, Component Attributes and the formula engine. Needs no `.skp` file and no OpenSKP. |

| **Components manager** | `asset_manager/` | A tray tab with the components in the drawing (preview, count, ⚙ on dynamic ones, *Select*) and a catalog of your own models (a folder of `.igz` with optional `.png` previews, *Insert*). |

None imports another. Installed together, you can import a `.skp`, edit its dynamic
components and export it back.

## SketchUp files (`skp_dc_import`)

- **Import SketchUp keeping components…** opens a `.skp` with its component tree intact, every
  part a nested IngeTrazo component, and each part's Dynamic Components attributes, formulas and
  options kept, in SketchUp's own format.
- **Export SketchUp (.skp) with dynamic components…** writes the document as a `.skp`
  (SketchUp 2017 format, which every later SketchUp opens) with its groups, components,
  materials and textures, and each part's Dynamic Components data: the components work as
  dynamic components in SketchUp, with their options.
- **SketchUp .skp settings…**: credits and the blank `.skp` the export needs.
- **?** (in the settings window and on the toolbar) opens a help window: import, export, the
  blank file, and what to do when something goes wrong.

## Dynamic components (`dc_tools`)

- **Component Options**: the options a component shows its users (text fields, lists,
  read-only values, in their units). Its **?** button opens the help at the Options section. **Apply** redraws it: copies, hidden parts, sizes,
  positions, rotations and materials, as SketchUp would. Changing LenX/LenY/LenZ resizes it the
  way SketchUp's dialog does.
- **Component Attributes**: **Make dynamic**, then per part: attributes with a value or a
  `=formula`, the predefined ones (X, Y, Z, LenX…, RotX…, Hidden, Material, Copies…) or your
  own, and how each one shows to users (label, access, units, list choices). The **?** button
  opens a help window: how the panel works, what each predefined attribute does, how to write
  formulas and every function with its syntax and an example.

Every change is one undo step. Versions: skp_dc_import 0.6.0, dc_tools 0.3.0, asset_manager 0.1.0, for IngeTrazo 0.6 (Extension API 2).

## Install

Download `skp_dc_import-<version>.zip` and/or `dc_tools-<version>.zip` from the
[releases](https://github.com/moominot/ingetrazo-skp-dc-import/releases) and unpack each in
IngeTrazo's plugins folder (**Extensions ▸ Open plugins folder**; `%APPDATA%\IngeTrazo\plugins\`
on Windows), so that `…/plugins/skp_dc_import/__init__.py` and/or `…/plugins/dc_tools/__init__.py`
exist. Restart IngeTrazo.

Each extension has its own toolbar and its commands in the **Extensions** menu; Options and
Attributes are also in the right-click menu of a selected component, and open as side-tray
panels (also from **Window ▸ Panels**).

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

## Export to SketchUp

`skp_dc_import/skp_export.py` is IngeTrazo's own `.skp` writer (`formats/skp_out.py`,
GPL-3.0), which IngeTrazo no longer ships enabled, adapted for dynamic components: every
definition carries its `dynamic_attributes` and every placement its own; hidden parts are
written hidden instead of left out; a part's nominal size goes on its definition and copies
are named «name copy 001», which is how SketchUp's Dynamic Components read them.

Checked by opening the exports in SketchUp 2026: four real components came back with every
attribute value and hidden flag identical, and, redrawn by SketchUp's own engine with options
changed, identical to the originals part by part; a cabinet made in IngeTrazo works in
SketchUp's Component Options (shelves 3 → 5 → 2 → 4).

**About the template.** OpenSKP's writer builds every `.skp` from a blank document,
`blank_v17.skp`, whose bytes came from Trimble's SketchUp SDK (OpenSKP explains it in
`create.py`: SketchUp's empty-document boilerplate, no one's creative work). IngeTrazo
stopped distributing it to ship only free pieces, so **this extension does not include it
either** (since 0.4.0). Importing works without it; to export, open **Extensions ▸ SketchUp
.skp settings…** and either press **Download from OpenSKP** (fixed commit, checked against its
SHA-256) or **Choose file…** with a copy you already have. Only that exact file works: the
writer's offsets are specific to its bytes, so a blank `.skp` saved from SketchUp (including
SketchUp for Web) is rejected. The file is kept in the extension's folder in the user's data
directory.

## Limits

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
- The `.skp` writer is IngeTrazo's `formats/skp_out.py` (GPL-3.0, © Marco Sumari Tellez and
  IngeTrazo contributors), adapted.
- The vendored OpenSKP keeps its MIT licence (`_vendor/openskp/LICENSE`).
- Faces, materials and textures are read with IngeTrazo's own `.skp` adapter.
