#!/usr/bin/env bash
# End-to-end smoke test of a running stack, through the nginx proxy, the way a browser would use it.
# It needs no API key: without one the stack runs in demo mode, which replays recorded model output.
#
#   docker compose up -d --build --wait
#   BASE=http://localhost:8082 bash scripts/smoke.sh
set -euo pipefail

BASE="${BASE:-http://localhost:8082}"
HERE="$(cd "$(dirname "$0")" && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
# Relative file names inside the temp dir: a native Windows curl cannot read POSIX paths such as /tmp/...
cp "$HERE/../backend/evals/dataset/dev/dev-easy-01.pdf" "$tmp/other.pdf"
cd "$tmp"

ok() { echo "OK  $1"; }
fail() { echo "FAIL $1" >&2; exit 1; }
status() { curl -s -o /dev/null -w '%{http_code}' "$@"; }

# 1. frontend and API are both reachable through the one public address
curl -fsS "$BASE/" | grep -q "<app-root" || fail "frontend is not served"
ok "frontend is served"

curl -fsS "$BASE/api/v1/info" | python3 -c "import sys, json; d = json.load(sys.stdin); assert d['mode'] == 'demo', d" \
  || fail "API not reachable through the proxy, or not in demo mode"
ok "API reachable through the proxy (demo mode)"

# 2. a bundled sample goes through extraction and the validator flags its wrong total
curl -fsS "$BASE/api/v1/samples/german-wrong-total/pdf" -o sample.pdf
head -c 5 sample.pdf | grep -q '%PDF-' || fail "sample is not a PDF"

curl -fsS -F "file=@sample.pdf;type=application/pdf" "$BASE/api/v1/extractions" -o result.json
python3 - result.json . <<'PY' || fail "extraction result is not what a document with a wrong total should give"
import json, sys
result = json.load(open(sys.argv[1]))
assert result["needs_review"] is True, "must need review"
assert [i["code"] for i in result["issues"]] == ["total_mismatch"], result["issues"]
assert result["pages"] == 1 and len(result["document_id"]) >= 20
open(sys.argv[2] + "/doc_id", "w").write(result["document_id"])
e = result["extraction"]
corrected = dict(e, total=round(e["subtotal"] - e["discount_total"] + e["tax_total"], 2))
json.dump(corrected, open(sys.argv[2] + "/corrected.json", "w"))
json.dump(e, open(sys.argv[2] + "/original.json", "w"))
PY
ok "extraction flags the wrong total (needs_review, total_mismatch)"
doc_id="$(cat doc_id)"

# 3. the page image reaches the browser as a PNG. This is the request an nginx regex location for static
#    files once swallowed, because the URL ends in .png.
type="$(curl -s -o page.png -w '%{http_code} %{content_type}' "$BASE/api/v1/documents/$doc_id/pages/1.png")"
[ "$type" = "200 image/png" ] || fail "page image answered '$type'"
python3 -c "import sys; assert open(sys.argv[1], 'rb').read(8) == b'\x89PNG\r\n\x1a\n'" page.png || fail "page is not a PNG"
ok "page image is served through the proxy as a PNG"

# 4. re-validation, with no model call: the original still fails, the corrected total passes
post() { curl -fsS -X POST -H 'Content-Type: application/json' --data-binary "@$1" "$BASE/api/v1/validations"; }
post original.json | python3 -c "import sys, json; assert json.load(sys.stdin)['needs_review'] is True" || fail "original should still need review"
post corrected.json | python3 -c "import sys, json; assert json.load(sys.stdin)['needs_review'] is False" || fail "corrected total should pass"
ok "re-validation: original fails, corrected passes"

# 5. demo mode refuses anything that is not a bundled sample, with a readable message
code="$(status -F "file=@other.pdf;type=application/pdf" "$BASE/api/v1/extractions")"
[ "$code" = "422" ] || fail "a non-sample upload answered $code, expected 422"
ok "a non-sample document is refused (422)"

# 6. a non-PDF is rejected by content, whatever it claims to be
printf 'not a pdf' > fake.pdf
code="$(status -F "file=@fake.pdf;type=application/pdf" "$BASE/api/v1/extractions")"
[ "$code" = "415" ] || fail "fake PDF answered $code, expected 415"
ok "a file that only claims to be a PDF is rejected (415)"

# 7. delete frees the document at once
[ "$(status -X DELETE "$BASE/api/v1/documents/$doc_id")" = "204" ] || fail "delete did not answer 204"
[ "$(status "$BASE/api/v1/documents/$doc_id/pages/1.png")" = "404" ] || fail "deleted document is still served"
ok "delete removes the document"

echo "smoke test passed"
