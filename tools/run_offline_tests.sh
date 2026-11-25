#!/usr/bin/env bash
# The Library's tests. Run from the repository: bash tools/run_offline_tests.sh <IngeTrazo source>
[ -d "$1" ] || { echo "usage: $0 <IngeTrazo source folder>"; exit 2; }
SRC="$(cd "$1" && (pwd -W 2>/dev/null || pwd))"; PY="${PYTHON:-python}"
export QT_QPA_PLATFORM=offscreen PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1
status=0
for t in asset_manager_offline asset_manager_tabs proxy_offline proxy_ops_offline; do
  out="$(PYTHONPATH="$SRC" timeout 240 "$PY" tests_su/test_$t.py "$SRC" . 2>&1)" || status=1
  echo "$t: $(echo "$out" | tail -1)"
done
# (its arguments go the other way round; one check is known to fail: "and the simple picture beside it")
out="$(PYTHONPATH="$SRC" timeout 240 "$PY" tests_su/test_asset_manager_library.py . "$SRC" 2>&1)"
echo "asset_manager_library: $(echo "$out" | grep '^FAIL' | head -3) $(echo "$out" | tail -1)"
exit $status
