"""The blank-.skp template: missing / wrong / right file, download check,
and that export works once it is installed.
argv: <ingetrazo-src> <extension repo> <the original blank_v17.skp>"""
import os, sys, tempfile, pathlib
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
SRC, EXT, GOOD = [os.path.abspath(a) for a in sys.argv[1:4]]
home = tempfile.mkdtemp()
os.environ["SKP_DC_IMPORT_HOME"] = home
sys.path[:0] = [SRC, EXT]
from skp_dc_import import template, skp_export
import importlib
_create = importlib.import_module('skp_dc_import._vendor.openskp.create')

fails = []
def ok(cond, what):
    print(("PASS " if cond else "FAIL ") + what)
    if not cond: fails.append(what)

ok(template.status()[0] == template.MISSING, "missing at first")
ok(not template.apply(), "apply() false while missing")
try:
    skp_export.save_skp(None, os.path.join(home, "x.skp")); ok(False, "export refuses without template")
except RuntimeError as e:
    ok("settings" in str(e), "export refuses without template, points to settings")

bad = pathlib.Path(home, "other.skp"); bad.write_bytes(b"not the template")
ok(template.check(bad)[0] == template.BAD, "wrong file is BAD")
try:
    template.install_from_file(bad); ok(False, "wrong file rejected")
except ValueError:
    ok(True, "wrong file rejected")
ok(template.status()[0] == template.MISSING, "still missing after rejection")

# download: wrong content rejected, right content installed (file:// stands in for the network)
try:
    template.download(bad.as_uri()); ok(False, "download of wrong content rejected")
except ValueError:
    ok(True, "download of wrong content rejected")
ok(template.status()[0] == template.MISSING, "nothing stored from the bad download")
template.download(pathlib.Path(GOOD).as_uri())
ok(template.status()[0] == template.OK, "download of the right file installs it")
ok(template.apply() and _create._scaffold_path == str(template.configured_path()), "apply() points OpenSKP at it")

# the real thing: build a tiny document with the installed template
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
from PySide6.QtGui import QVector3D
from core.scene import Scene
from core.group import Group
from core.mesh import Mesh
m = Mesh()
P = lambda a, b, c: QVector3D(a, b, c)
for q in ([P(0,0,0), P(0,1,0), P(1,1,0), P(1,0,0)], [P(0,0,1), P(1,0,1), P(1,1,1), P(0,1,1)]):
    m.add_face(q)
scene = Scene()
scene.add_group(Group(m, name="caixa")) if hasattr(scene, "add_group") else scene.groups.append(Group(m, name="caixa"))
out = os.path.join(home, "box.skp")
skp_export.save_skp(scene, out)
ok(os.path.getsize(out) > 5000, "a scene exports with the downloaded template")
from skp_dc_import import reader
ok(reader.parse(out) is not None, "the export reads back")
print("FAILED" if fails else "ALL OK"); sys.exit(1 if fails else 0)
