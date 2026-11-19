"""The «?» help: covers every function, its examples parse, its claims hold,
the button opens it. argv: <ingetrazo-src> <extension repo> [png dir]"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
SRC, EXT = [os.path.abspath(a) for a in sys.argv[1:3]]
PNG = sys.argv[3] if len(sys.argv) > 3 else None
sys.path[:0] = [SRC, EXT]
from PySide6.QtWidgets import QApplication
qa = QApplication.instance() or QApplication([])
from dc_tools import help_text, ui_author, ui, ui_help
from dc_tools.dc import formula as F
from dc_tools.dc import author as AU

fails = []
def ok(c, w):
    print(("PASS " if c else "FAIL ") + w)
    if not c: fails.append(w)

ok(set(help_text.FUNCTION_NAMES) == set(F.FUNCTIONS), "help documents exactly the functions the engine has"
   + ("" if set(help_text.FUNCTION_NAMES) == set(F.FUNCTIONS) else f" (diff {set(help_text.FUNCTION_NAMES) ^ set(F.FUNCTIONS)})"))
bad = []
for _g, rows in help_text.FUNCTIONS:
    for name, syntax, _t, example in rows:
        try: F.parse(example)
        except Exception as e: bad.append((example, str(e)))
        if not syntax.upper().startswith(name): bad.append((name, "syntax does not start with name"))
ok(not bad, f"every example parses and every syntax starts with its name {bad}")
names = [n for n, _u in AU.PREDEFINED]
page = help_text.html()
ok(all(AU.LABELS[n] in page for n in names), "every predefined attribute is mentioned")

def ev(src, **vals):
    return F.evaluate(F.parse(src), lambda node, attr: vals.get(attr, 0.0))
checks = {
    "IF(0,1,2)": 2.0, "IF(-1,1,2)": 2.0, "IF(1,1,2)": 1.0, "CHOOSE(2,10,20,30)": 20.0,
    "ROUND(2.5)": 3.0, "ROUND(1.26,1)": 1.3, "FLOOR(7,2.5)": 5.0, "CEILING(7,2.5)": 7.5,
    "INT(-1.5)": -2.0, "MOD(5,-3)": -1.0, "MID(\"abcdef\",2,3)": "bcd", "LEFT(\"abc\")": "a",
    "RIGHT(\"abc\")": "c", "\"a\"&1": "a1", "ASIN(0.5)": 30.0,
}
for src, want in checks.items():
    got = ev(src)
    ok(got == want or (isinstance(got, float) and abs(got - want) < 1e-9), f"{src} = {want!r} (got {got!r})")
ok(ev("IF(0,1)") is False, "IF without else gives FALSE")
try: ev("ASIN(2)"); ok(False, "ASIN(2) is an error")
except F.FormulaError: ok(True, "ASIN(2) is an error")

from PySide6.QtWidgets import QWidget
class App: pass
panel = ui_author.AttributesPanel(App())
ok(panel.help_btn.text() == "?" and panel.help_btn.toolTip(), "panel has a ? button with a tooltip")
panel.help_btn.click(); qa.processEvents()
dlg = ui_help._dialog
ok(dlg is not None and dlg.isVisible() and "Functions" in dlg.view.toPlainText() and "ROUND" in dlg.view.toPlainText(), "the button opens the help")
sb = dlg.view.verticalScrollBar()
attr_pos = sb.value()
ok(attr_pos > 0, f"the attributes button scrolls to its section ({attr_pos})")
panel.help_btn.click(); ok(ui_help._dialog is dlg, "reuses the same window")
opts = ui.OptionsPanel(App())
ok(opts.help_btn.text() == "?" and opts.help_btn.toolTip(), "Component Options panel has a ? button")
opts.help_btn.click(); qa.processEvents()
ok(ui_help._dialog is dlg and sb.value() < attr_pos, "its button opens the same window at the options section (above attributes)")
page = help_text.html()
ok('name="options"' in page and page.index('name="options"') < page.index('name="attributes"'), "both anchors present, options first")
ok(all(w in page for w in ("Apply", "Revert", "Text box", "List", "Read-only", "one undo step")), "options help names every control")
dlg.find.setText("CHOOSE"); qa.processEvents()
ok(dlg.view.textCursor().selectedText().lower() == "choose", "search finds the word (any case)")
if PNG:
    dlg.find.setText(""); dlg.view.verticalScrollBar().setValue(0); dlg.grab().save(os.path.join(PNG, "help1.png"))
    dlg.view.verticalScrollBar().setValue(dlg.view.verticalScrollBar().maximum() // 2); dlg.grab().save(os.path.join(PNG, "help2.png"))
print("FAILED" if fails else "ALL OK"); sys.exit(1 if fails else 0)
