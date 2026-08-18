#!/usr/bin/env bash
# Build the LaTeX source archive the journal asks for as the manuscript file.
#
# The portal wants an editable format, not a PDF: "LaTeX documents with figures
# and tables compressed into a .zip format. We'll compile these into a PDF for
# peer review."
#
# The layout deliberately mirrors upload/paper.zip, the archive that passed the
# technical check for v1.1 - everything under a top-level paper/ folder, with
# figures/ beside main.tex, and no PDF of the manuscript. main.bbl is included
# so the bibliography resolves even if the compiler does not run bibtex.
#
# The marked-up copy is NOT in here. It goes in the related-files slot, because
# the manuscript itself must be clean of highlights.
#
# Usage:  bash submission/make_paper_zip.sh
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$PWD"
OUT="$ROOT/submission/paper.zip"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

mkdir -p "$STAGE/paper/figures"
cp "$ROOT/paper/main.tex"       "$STAGE/paper/"
cp "$ROOT/paper/main.bbl"       "$STAGE/paper/"
cp "$ROOT/paper/references.bib" "$STAGE/paper/"
cp "$ROOT/paper/sn-jnl.cls"     "$STAGE/paper/"
cp "$ROOT/paper/sn-basic.bst"   "$STAGE/paper/"
cp "$ROOT"/figures/*.pdf        "$STAGE/paper/figures/"

rm -f "$OUT"
(cd "$STAGE" && zip -q -r "$OUT" paper)

echo "  $OUT"
echo "  $(unzip -l "$OUT" | tail -1 | awk '{print $2}') files, $(du -h "$OUT" | cut -f1)"

# A zip that does not compile on their machine is worse than no zip, so prove it
# builds from a clean extract with nothing else on the path.
CHECK="$(mktemp -d)"
trap 'rm -rf "$STAGE" "$CHECK"' EXIT
(cd "$CHECK" && unzip -q "$OUT" && cd paper \
   && latexmk -pdf -interaction=nonstopmode main.tex >build.log 2>&1)
PAGES=$(pdfinfo "$CHECK/paper/main.pdf" | awk '/Pages/{print $2}')
UNDEF=$(grep -c undefined "$CHECK/paper/main.log" || true)
echo "  clean-room build: ${PAGES} pages, ${UNDEF} undefined references"
