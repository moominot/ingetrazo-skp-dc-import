# SPDX-License-Identifier: GPL-3.0-or-later
"""The text behind the «?» buttons of the SketchUp files extension."""
from __future__ import annotations

from . import template


def html() -> str:
    return f"""
<a name="files"></a>
<h3>.skp files: how it works</h3>
<p>This extension opens <b>.skp</b> files <i>keeping their components</i> (and the dynamic component data they
carry), and saves your drawing as a <b>.skp</b> again. To <i>edit</i> dynamic components (options, attributes,
formulas) use the separate <b>Dynamic components</b> extension; both read and write the same data, so you can
import a .skp, edit it there and export it back.</p>

<a name="import"></a>
<h4>Import .skp keeping components…</h4>
<ol>
<li>Choose <b>Extensions ▸ Import .skp keeping components…</b> (or the <b>In</b> button of the toolbar).</li>
<li>Pick the .skp file. The cursor shows it is working; big files take a moment.</li>
<li>A summary says how many components and groups came in, how many of them have dynamic attributes, and lists the
dynamic components.</li>
</ol>
<p>What you get:</p>
<ul>
<li>Every group and component is a <b>nested component</b> of IngeTrazo, as deep as the file nests them. Repeated
parts <b>share</b> their geometry (one definition, many placements).</li>
<li>Each part that is a dynamic component keeps its dynamic attributes, formulas and options, exactly as the
file stores them.</li>
<li>A <b>dynamic component saved as its own file</b> (a library component, saved on its own from the program
it was made in) comes in as <b>one component</b> holding its parts, as that program inserts it, with the top-level attributes,
formulas and options the parts refer to (<i>Name!Attr</i>). Files of every .skp version, 2020 and older
included.</li>
<li>Faces, materials, textures, soft edges and loose edges come in as with IngeTrazo's own .skp import.</li>
<li>The whole import is <b>one undo step</b>.</li>
</ul>
<p>IngeTrazo's own .skp import flattens each top-level object into a single group, which is fine for reference
geometry but loses the parts a component is made of; this one keeps them. If a file cannot be read, a message names
the file and the reason, and the drawing is left as it was.</p>

<a name="export"></a>
<h4>Export .skp with dynamic components…</h4>
<ol>
<li>Make sure the <b>blank file</b> is ready (see below). If it is not, the export opens the settings window first.</li>
<li>Choose <b>Extensions ▸ Export .skp with dynamic components…</b> (or the <b>Out</b> button).</li>
<li>Choose the name and place; the <i>.skp</i> ending is added if you leave it out.</li>
</ol>
<p>What is written:</p>
<ul>
<li>A <b>.skp 2017</b> format file, which every later version opens.</li>
<li>Groups and components: a component used several times is stored once and placed several times.</li>
<li>Materials, with their textures embedded; layers as tags; faces with holes.</li>
<li>For each part, its <b>dynamic component</b> data, so the components keep working as dynamic components,
with their options. Parts that a dynamic component hides are written hidden, not left out.</li>
</ul>

<a name="template"></a>
<h4>The blank file (needed to export)</h4>
<p>To write a .skp, OpenSKP starts from an empty .skp document, <code>{template.FILE_NAME}</code> (about 5.8 KB,
made with the format's own SDK). This extension does <b>not</b> include it, so that only free pieces are distributed. You get
it once; <b>importing works without it</b>. Open <b>Extensions ▸ .skp settings…</b>:</p>
<table cellspacing='0' cellpadding='3' width='100%'>
<tr><td valign='top'><b>✔ / ✖ / ⚠</b></td><td>The state: ready, missing, or a file that is not the right one.</td></tr>
<tr><td valign='top'><b>Download from OpenSKP</b></td><td>Fetches the file from the OpenSKP project at a fixed commit and checks it
against its SHA-256 before keeping it. If the download fails, the message gives the address so you can get it
yourself.</td></tr>
<tr><td valign='top'><b>Choose file…</b></td><td>Uses a copy you already have. It must be <b>exactly</b> that file:
the writer depends on its bytes, so any other blank .skp, even an empty one saved by a modeler, is rejected.</td></tr>
</table>
<p>The file is kept in this extension's folder in your user data directory. A build of the extension that already
carries the file shows «Included with this build» and needs nothing more.</p>

<a name="problems"></a>
<h4>If something goes wrong</h4>
<ul>
<li><b>«Could not import …»</b>: the file could not be read; the reason follows. Try opening it in the program it
comes from and saving it again.</li>
<li><b>«No blank .skp at …»</b>: export needs the blank file: use <b>Download from OpenSKP</b> or <b>Choose file…</b>.</li>
<li><b>«is not the expected file»</b>: the chosen file is not the original; use the download.</li>
<li><b>The download fails</b>: you may be offline or behind a firewall; download the file from the address shown and use
<b>Choose file…</b>.</li>
<li><b>Dynamic components do not respond after importing</b>: install the <b>Dynamic components</b> extension (it
provides Component Options and Component Attributes).</li>
</ul>
<p><small>Credits: the formula interpreter is d1rty-pixel's <i>Dynamic Components for IngeTrazo</i> (GPL-3.0); the
.skp writer comes from IngeTrazo's <code>formats/skp_out.py</code>; OpenSKP is © Ahsan Mehmood (MIT). This extension is
GPL-3.0-or-later.</small></p>
"""
