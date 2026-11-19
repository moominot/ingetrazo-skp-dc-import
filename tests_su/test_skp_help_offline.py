"""Help of the SketchUp files extension. argv: <ingetrazo-src> <extension repo> [png dir]"""
import os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["SKP_DC_IMPORT_HOME"] = tempfile.mkdtemp()
SRC, EXT = [os.path.abspath(a) for a in sys.argv[1:3]]
PNG = sys.argv[3] if len(sys.argv) > 3 else None
sys.path[:0] = [SRC, EXT]
from PySide6.QtWidgets import QApplication, QToolButton
qa = QApplication.instance() or QApplication([])
from skp_dc_import import help_text, ui_help, ui_settings, template

fails = []
def ok(c, w):
    print(("PASS " if c else "FAIL ") + w)
    if not c: fails.append(w)

page = help_text.html()
ok(all(f'name="{a}"' in page for a in ("files", "import", "export", "template", "problems")), "all sections have an anchor")
ok(template.FILE_NAME in page, "the help names the template file the code uses")
ok(all(t in page for t in ("Download from OpenSKP", "Choose file…", ".skp 2017", "one undo step")),
   "names the controls and formats")
# the messages the help quotes are the ones the code produces
ok("Could not import" in open(os.path.join(EXT, "skp_dc_import", "__init__.py")).read(), "«Could not import» is a real message")
ok(template.check("/nonexistent.skp")[1].startswith("No blank .skp at"), "«No blank .skp at» is a real message")
bad = os.path.join(os.environ["SKP_DC_IMPORT_HOME"], "x.skp"); open(bad, "wb").write(b"zz")
ok("is not the expected file" in template.check(bad)[1], "«is not the expected file» is a real message")

d = ui_settings.SettingsDialog()
btns = [b for b in d.findChildren(QToolButton) if b.text() == "?"]
ok(len(btns) == 1 and btns[0].toolTip(), "the settings window has a ? button")
btns[0].click(); qa.processEvents()
h = ui_help._dialog
ok(h is not None and h.isVisible() and "Import .skp keeping components" in h.view.toPlainText(), "it opens the help")
ok(h.view.verticalScrollBar().value() > 0, "scrolled to the blank-file section")
h.find.setText("firewall"); qa.processEvents()
ok(h.view.textCursor().selectedText().lower() == "firewall", "search finds a word")
if PNG:
    h.find.setText(""); h.goto("files"); h.view.verticalScrollBar().setValue(0); qa.processEvents()
    h.grab().save(os.path.join(PNG, "skp_help.png"))
print("FAILED" if fails else "ALL OK"); sys.exit(1 if fails else 0)
