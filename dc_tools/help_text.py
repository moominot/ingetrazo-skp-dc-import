# SPDX-License-Identifier: GPL-3.0-or-later
"""The text behind the «?» button of the Component Attributes panel.

The function reference is data (``FUNCTIONS``), and the test checks that it
covers every function the formula engine knows, so the help cannot fall
behind the code.
"""
from __future__ import annotations

from html import escape

from .i18n import localized_text, tr

# (function, syntax, what it does, example)
FUNCTIONS = (
    ("Logic", (
        ("IF", "IF(condition, then, else)",
         "Gives <i>then</i> when the condition is true, otherwise <i>else</i> (FALSE if you leave it out). "
         "True means TRUE or a <b>positive</b> number: 0 and negatives are false.",
         "IF(parent!n>3, 1, 0)"),
        ("AND", "AND(a, b, …)", "True when all the arguments are true.", "AND(lenx>10, leny>10)"),
        ("OR", "OR(a, b, …)", "True when at least one argument is true.", "OR(hidden, n=0)"),
        ("NOT", "NOT(a)", "The opposite: true becomes false.", "NOT(parent!door_open)"),
        ("CHOOSE", "CHOOSE(index, a, b, …)",
         "The argument at position <i>index</i>, counting from 1 (the first one after the index is 1). "
         "An index out of range is an error.", "CHOOSE(type, 60, 80, 100)"),
    )),
    ("Numbers", (
        ("MIN", "MIN(a, b, …)", "The smallest.", "MIN(lenx, 200)"),
        ("MAX", "MAX(a, b, …)", "The largest.", "MAX(parent!leny-5, 10)"),
        ("ABS", "ABS(x)", "Absolute value (drops the sign).", "ABS(x-parent!x)"),
        ("ROUND", "ROUND(x, digits)",
         "Rounds to <i>digits</i> decimals (0 if omitted), halves going up. Negative digits round to tens, hundreds…",
         "ROUND(parent!lenx/3, 1)"),
        ("FLOOR", "FLOOR(x, multiple)", "Rounds down to a multiple of <i>multiple</i> (1 if omitted).", "FLOOR(lenx, 2.5)"),
        ("CEILING", "CEILING(x, multiple)", "Rounds up to a multiple of <i>multiple</i> (1 if omitted).", "CEILING(lenx, 2.5)"),
        ("INT", "INT(x)", "Rounds down to the whole number below (INT(-1.5) is -2).", "INT(parent!lenz/35)"),
        ("MOD", "MOD(n, d)", "The remainder of n ÷ d; it has the sign of <i>d</i>.", "MOD(copy, 2)"),
        ("SQRT", "SQRT(x)", "Square root (an error for a negative number).", "SQRT(lenx^2+leny^2)"),
        ("PI", "PI()", "3.14159…", "PI()*lenx"),
    )),
    ("Angles (in degrees)", (
        ("SIN", "SIN(angle)", "Sine of an angle in degrees.", "SIN(rotx)"),
        ("COS", "COS(angle)", "Cosine of an angle in degrees.", "COS(rotx)"),
        ("TAN", "TAN(angle)", "Tangent in degrees (an error at 90° and 270°).", "TAN(30)"),
        ("ASIN", "ASIN(x)", "Angle in degrees whose sine is x; x must be between -1 and 1.", "ASIN(0.5)"),
        ("ACOS", "ACOS(x)", "Angle in degrees whose cosine is x; x must be between -1 and 1.", "ACOS(0.5)"),
        ("ATAN", "ATAN(x)", "Angle in degrees whose tangent is x.", "ATAN(lenz/lenx)"),
        ("RADIANS", "RADIANS(deg)", "Degrees to radians.", "RADIANS(90)"),
        ("DEGREES", "DEGREES(rad)", "Radians to degrees.", "DEGREES(PI())"),
    )),
    ("Text", (
        ("LEN", "LEN(text)", "How many characters it has.", "LEN(name)"),
        ("LEFT", "LEFT(text, n)", "The first n characters (1 if omitted).", "LEFT(name, 3)"),
        ("RIGHT", "RIGHT(text, n)", "The last n characters (1 if omitted).", "RIGHT(name, 2)"),
        ("MID", "MID(text, start, n)", "n characters from position <i>start</i> (the first character is 1).", "MID(name, 2, 3)"),
        ("CONCATENATE", "CONCATENATE(a, b, …)", "Joins texts and numbers into one text. The same as the <b>&amp;</b> operator.",
         "CONCATENATE(\"Door \", lenx)"),
        ("VALUE", "VALUE(text)", "Turns a text such as \"12.5\" into a number.", "VALUE(parent!code)"),
        ("LOWER", "LOWER(text)", "To lower case.", "LOWER(name)"),
        ("UPPER", "UPPER(text)", "To upper case.", "UPPER(name)"),
        ("TRIM", "TRIM(text)", "Removes spaces at the ends and doubled spaces inside.", "TRIM(name)"),
    )),
)

FUNCTION_NAMES = tuple(sorted(f[0] for _g, rows in FUNCTIONS for f in rows))

PREDEFINED = (
    ("X, Y, Z", "Where the part sits, measured from its parent's origin, along each axis."),
    ("LenX, LenY, LenZ", "The size of the part along each axis. Changing them stretches the part and what it holds, "
                         "the way dynamic components work."),
    ("RotX, RotY, RotZ", "Rotation of the part around each axis, in degrees."),
    ("Hidden", "The part is hidden when the value is true (TRUE or a positive number, so 1)."),
    ("Material", "The name of the material the part is painted with."),
    ("Copies", "How many <b>extra</b> copies of the part to make (Copies = 3 gives four parts in all). "
               "Inside a formula, <code>copy</code> is the number of the part being drawn: 0 for the original, "
               "1, 2, 3… for the copies; use it to place each copy, e.g. "
               "<code>Z = (copy+1)*parent!lenz/parent!n</code>."),
    ("Name", "The part's name. It is what other formulas use to refer to it (<code>Shelf!lenx</code>)."),
    ("Summary, Description, ItemCode", "Free text kept with the component (for lists, reports…). They do not change its shape."),
)


def _functions_html() -> str:
    out = []
    for group, rows in FUNCTIONS:
        out.append(f"<h4>{escape(tr(group))}</h4><table cellspacing='0' cellpadding='3' width='100%'>")
        for _name, syntax, text, example in rows:
            out.append(
                f"<tr><td valign='top'><code><b>{escape(syntax)}</b></code></td>"
                f"<td valign='top'>{tr(text)}<br><i>{tr('e.g.')}</i> <code>={escape(example)}</code></td></tr>")
        out.append("</table>")
    return "".join(out)


def html() -> str:
    pre = "".join(f"<tr><td valign='top'><b>{escape(n)}</b></td><td valign='top'>{tr(t)}</td></tr>"
                  for n, t in PREDEFINED)
    translated = localized_text("help")
    if translated is not None:
        return translated.replace("{PREDEFINED}", pre).replace("{FUNCTIONS}", _functions_html())
    return f"""
<a name="options"></a>
<h3>Component Options: how it works</h3>
<p>A <b>dynamic component</b> shows its users a few <b>options</b>: the number of shelves, the width, a door
type… This panel is where they change them. When you apply, the component is <b>redrawn</b> following the dynamic
component rules: copies, hidden parts, sizes, positions, rotations and materials are recomputed from the options
and the formulas. The options come from the component's author: a component imported from a .skp file brings its own, and
one made here gets them in <i>Component Attributes ▸ Options…</i>.</p>

<h4>How to use it</h4>
<ol>
<li><b>Select</b> a dynamic component in the drawing. The panel follows the selection; its title shows the
component's name and how many options it has. (If the title asks you to select one, the selection is not a dynamic
component.)</li>
<li><b>Change</b> the options you want (see below).</li>
<li>Press <b>Apply</b> (or Enter in a text box). The component is redrawn, as <b>one undo step</b>.</li>
</ol>

<h4>The panel</h4>
<table cellspacing='0' cellpadding='3' width='100%'>
<tr><td valign='top'><b>Text box</b></td><td>An option you type: a number (in the option's own units, such as cm) or
a text. A value that is not a number is reported and nothing is applied.</td></tr>
<tr><td valign='top'><b>List</b></td><td>An option you pick from a drop-down list. A choice may carry a formula, which
is worked out when you apply.</td></tr>
<tr><td valign='top'><b>Read-only value</b></td><td>An option the author lets you see but not change (a computed price
or size, for example). It is shown as text.</td></tr>
<tr><td valign='top'><b>Apply</b></td><td>Redraws the component with the options you changed (only those are sent).
One undo step.</td></tr>
<tr><td valign='top'><b>Revert</b></td><td>Puts back the values the component has now, discarding what you typed.</td></tr>
<tr><td valign='top'><b>Message line</b></td><td>Under the buttons. <i>Redrawn</i> when it worked. If some formulas could not
be evaluated it says so: those attributes keep their value.</td></tr>
</table>
<p><b>Sizes.</b> If an option is LenX, LenY or LenZ, changing it resizes the component the way a dynamic component is resized:
the part is stretched and what it holds follows, then the formulas of its sub-parts set what they control.</p>
<p>Open the panel from <b>Extensions ▸ Dynamic component options…</b>, from the toolbar, or from the right-click menu
of a dynamic component.</p>

<a name="attributes"></a>
<h3>Component Attributes: how it works</h3>
<p>A <b>dynamic component</b> is a component whose size, position, copies, visibility or material are
<i>computed</i> from attributes and formulas, the way dynamic components in .skp files are. This panel is where you
create and edit those attributes. The data is stored in the .skp format's own way, so a component made here keeps working
when exported to .skp (with the .skp files extension).</p>

<h4>In five steps</h4>
<ol>
<li><b>Select</b> a component or group in the drawing (the panel follows the selection).</li>
<li>Pick the <b>units</b> its formulas are written in and press <b>Make dynamic</b>.</li>
<li>In the tree, choose the <b>part</b> (the component or one of its sub-parts) you want to edit.</li>
<li><b>Add attribute</b>: choose a predefined one (X, LenX, Copies…) or <i>Custom…</i> for your own (a letter
first, then letters, digits or _).</li>
<li>Type a <b>value</b> in the <i>Value or =formula</i> column, or a formula starting with <b>=</b>. The
<i>Result</i> column shows what it gives right now. The drawing redraws when you press Enter.</li>
</ol>
<p>Every change is one undo step.</p>

<h4>The panel</h4>
<table cellspacing='0' cellpadding='3' width='100%'>
<tr><td valign='top'><b>Title</b></td><td>The component being edited.</td></tr>
<tr><td valign='top'><b>Make dynamic</b> + units</td><td>Gives the selected component or group dynamic attributes. The units
(centimeters, millimeters, meters, inches, feet) are the ones its <b>formulas</b> use for lengths: a formula
<code>=4</code> in a centimeters component is 4 cm.</td></tr>
<tr><td valign='top'><b>Tree</b></td><td>The component and its sub-parts. Each part has its own attributes.</td></tr>
<tr><td valign='top'><b>Table</b></td><td><i>Attribute</i>: its name (in <b>bold</b> if users can see it in Component
Options). <i>Value or =formula</i>: a fixed value, or a formula. <i>Result</i>: the computed value; <b>?</b> means
the formula has an error, and the attribute then keeps its previous value.</td></tr>
<tr><td valign='top'><b>Add attribute</b></td><td>Adds a predefined attribute (see below) or a custom one.</td></tr>
<tr><td valign='top'><b>Delete</b></td><td>Removes the selected attribute from the part.</td></tr>
<tr><td valign='top'><b>Options…</b></td><td>How the attribute shows to the people who use the component, in
Component Options: <i>Display label</i> (the text they see); <i>Access</i> (not visible, view only, a textbox, or a
list); <i>Display in</i> (units); and, for a list, its <i>List options</i>: pairs of label and value (the value
may be a formula, <code>=something</code>). That is what makes an attribute an <b>option</b> the user can change.</td></tr>
</table>

<h4>Predefined attributes</h4>
<table cellspacing='0' cellpadding='3' width='100%'>{pre}</table>

<h4>Writing formulas</h4>
<p>A formula starts with <b>=</b>. Without it, what you type is a fixed value.</p>
<ul>
<li><b>Other attributes.</b> A bare name is an attribute of the <b>same part</b>: <code>=lenx/2</code>.
<code>Name!attr</code> is the attribute of another part: <code>=parent!lenx-3.6</code>,
<code>=Shelf!z+2</code>. <code>parent</code> is the part that holds this one; <code>self</code> is this part.
Other names are found among the part itself, its ancestors, its siblings and its children, and nothing further.</li>
<li><b>Operators.</b> <code>+ − * / ^</code> (power) · <code>&amp;</code> joins text · comparisons
<code>= &lt;&gt; &lt; &gt; &lt;= &gt;=</code> (give true or false) · parentheses.</li>
<li><b>Values.</b> Numbers (<code>3.5</code>), text in quotes (<code>"oak"</code>), <code>TRUE</code> and <code>FALSE</code>.</li>
<li><b>Units.</b> A formula sees lengths in <i>its own</i> component's units, and its result is converted back.
Angles are in degrees.</li>
<li><b>True and false.</b> Only TRUE or a <b>positive</b> number is true. <code>IF(0, a, b)</code> and
<code>IF(-1, a, b)</code> give b.</li>
<li><b>Errors.</b> If a formula fails (unknown name, division by zero, an argument out of range…) the attribute keeps
its previous value and the <i>Result</i> shows <b>?</b>.</li>
</ul>

<h4>Example: a cabinet with N shelves</h4>
<p>On the cabinet: attribute <code>n</code> = 3, set as an option so users can change it (Options… ▸ Access: textbox).
On the <i>Shelf</i> part: <code>Copies</code> = <code>=parent!n-1</code>, <code>LenX</code> =
<code>=parent!lenx-3.6</code> and <code>Z</code> = <code>=(copy+1)*parent!lenz/parent!n</code>.
Changing <i>n</i> in Component Options redraws the cabinet with that many shelves, evenly spaced.</p>

<h4>Functions</h4>
{_functions_html()}
<p><small>Names are not case sensitive. Not supported: OnClick and animations, and functions that read the
geometry (such as face area).</small></p>
"""
