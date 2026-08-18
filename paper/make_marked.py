#!/usr/bin/env python3
"""Generate main-marked.tex by diffing main.tex against the submitted version.

The marked-up copy shows the editor exactly what changed in this revision.
Earlier versions of this script carried a hand-written list of added passages,
which went stale every time the text moved. This one derives the markup from a
real diff against ../../upload/paper/main.tex (the file that was submitted), so
it cannot drift out of date.

Granularity is the sentence for ordinary prose and the whole environment for
floats: a table or figure that changed anywhere is coloured entirely, because
colouring individual cells would break the alignment.

Usage:  python3 make_marked.py
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUBMITTED = HERE.parent / "upload" / "paper" / "main.tex"
CURRENT = HERE / "main.tex"
OUTPUT = HERE / "main-marked.tex"

MARKUP_COLOUR = r"\definecolor{markup}{RGB}{0,100,0}"
BANNER = (
    r"\noindent{\small\textbf{Marked-up revision.} "
    r"{\color{markup}Text in this colour is new or rewritten for this revision.} "
    r"Black text is unchanged from the submitted version.}\par\medskip"
)

# Lines opening an environment whose contents are coloured as a unit.
FLOAT_OPEN = re.compile(r"^\s*\\begin\{(table|figure|table\*|figure\*)\}")
FLOAT_CLOSE = re.compile(r"^\s*\\end\{(table|figure|table\*|figure\*)\}")

# A line that is entirely one command taking one braced argument, e.g. \abstract{...}.
WRAPPER = re.compile(r"^(\\[a-zA-Z]+\*?(?:\[[^\]]*\])?\{)(.*)(\})\s*$")

HEADING = re.compile(r"^(\\(?:sub)*section\*?\{)(.+?)(\}.*)$")

ITEM = re.compile(r"^(\s*\\item\s+)(.*)$")

# Never split a sentence in the middle of one of these.
ABBREVIATIONS = ("e.g.", "i.e.", "cf.", "Fig.", "Eq.", "vs.", "approx.", "et al.")


def split_sentences(text: str) -> list[str]:
    """Split prose into sentences, never inside braces, brackets, or math."""
    parts, start, depth, math = [], 0, 0, False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            i += 2
            continue
        if ch == "$":
            math = not math
        elif not math:
            if ch in "{[":
                depth += 1
            elif ch in "}]":
                depth -= 1
            elif ch in ".!?" and depth == 0:
                nxt = text[i + 1 : i + 2]
                if nxt in (" ", "") and not text[: i + 1].endswith(ABBREVIATIONS):
                    parts.append(text[start : i + 1])
                    start = i + 2
                    i += 2
                    continue
        i += 1
    if start < len(text):
        parts.append(text[start:])
    return [p for p in parts if p.strip()]


def units_of(line: str) -> tuple[str, list[str], str]:
    """Break one source line into (prefix, comparable units, suffix)."""
    if not line.strip() or line.lstrip().startswith("%"):
        return line, [], ""
    if line.lstrip().startswith("\\begin") or line.lstrip().startswith("\\end"):
        return line, [], ""
    if "&" in line or line.rstrip().endswith("\\\\"):
        return "", [line], ""  # table row: compared, but coloured via its float

    heading = HEADING.match(line)
    if heading:
        return heading.group(1), [heading.group(2)], heading.group(3)

    item = ITEM.match(line)
    if item:
        return item.group(1), split_sentences(item.group(2)), ""

    wrapper = WRAPPER.match(line)
    if wrapper and wrapper.group(2).count("{") == wrapper.group(2).count("}"):
        return wrapper.group(1), split_sentences(wrapper.group(2)), wrapper.group(3)

    return "", split_sentences(line), ""


def normalise(unit: str) -> str:
    """Whitespace-insensitive key for comparing units across the two versions."""
    return " ".join(unit.split())


def main() -> None:
    old_lines = SUBMITTED.read_text().splitlines()
    new_lines = CURRENT.read_text().splitlines()

    # Only the body is marked; preamble differences are not editorial content.
    def body_start(lines: list[str]) -> int:
        for n, line in enumerate(lines):
            if line.startswith("\\abstract{"):
                return n
        return 0

    old_from, new_from = body_start(old_lines), body_start(new_lines)

    # Flatten both versions into comparable units, remembering where each came from.
    def flatten(lines: list[str], start: int) -> tuple[list[str], list[tuple[int, int]]]:
        keys: list[str] = []
        origin: list[tuple[int, int]] = []
        for n, line in enumerate(lines[start:], start):
            _, parts, _ = units_of(line)
            for k, part in enumerate(parts):
                keys.append(normalise(part))
                origin.append((n, k))
        return keys, origin

    old_keys, _ = flatten(old_lines, old_from)
    new_keys, new_origin = flatten(new_lines, new_from)

    changed: set[tuple[int, int]] = set()
    matcher = difflib.SequenceMatcher(None, old_keys, new_keys, autojunk=False)
    for tag, _, _, j1, j2 in matcher.get_opcodes():
        if tag in ("insert", "replace"):
            changed.update(new_origin[j1:j2])

    # A float that changed anywhere is coloured whole: colouring single cells
    # would put braces around the & alignment characters and break the table.
    float_ranges: list[tuple[int, int]] = []
    open_at = None
    for n, line in enumerate(new_lines):
        if FLOAT_OPEN.match(line):
            open_at = n
        elif FLOAT_CLOSE.match(line) and open_at is not None:
            float_ranges.append((open_at, n))
            open_at = None
    in_float = {n: rng for rng in float_ranges for n in range(rng[0], rng[1] + 1)}
    dirty_floats = {in_float[n] for n, _ in changed if n in in_float}

    out = list(new_lines)
    for n, line in enumerate(new_lines):
        if n < new_from or n in in_float:
            continue
        prefix, parts, suffix = units_of(line)
        if not parts:
            continue
        rebuilt = [
            "{\\color{markup}" + part + "}" if (n, k) in changed else part
            for k, part in enumerate(parts)
        ]
        out[n] = prefix + " ".join(rebuilt) + suffix

    for start, _ in sorted(dirty_floats, reverse=True):
        out.insert(start + 1, "\\color{markup}")

    text = "\n".join(out)
    # The colour goes in the preamble and the banner after \maketitle, so the
    # marked copy paginates identically to main.pdf instead of losing page one.
    text = text.replace("\\begin{document}", MARKUP_COLOUR + "\n\\begin{document}", 1)
    text = text.replace("\\maketitle", "\\maketitle\n\n" + BANNER + "\n", 1)
    OUTPUT.write_text(text + "\n")

    print(f"  units compared : {len(old_keys)} submitted -> {len(new_keys)} current")
    print(f"  sentences marked: {len(changed) - sum(1 for n, _ in changed if n in in_float)}")
    print(f"  floats marked   : {len(dirty_floats)} of {len(float_ranges)}")


if __name__ == "__main__":
    main()
