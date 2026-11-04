#!/usr/bin/python3
# SPDX-License-Identifier: BSD-2-Clause
# Copyright (c) 2026 The Blueberry Pie OS Authors
"""usage: gen-wcwidth.py UCD-DIR [OUTPUT]

Writes xo_wcwidth.h from UnicodeData.txt and EastAsianWidth.txt in UCD-DIR.
OUTPUT is debian/xo_wcwidth.h by default.
"""
import os
import re
import sys

ZERO_CATEGORIES = {"Mn", "Me", "Cf"}
ONE_WIDE = {0x00AD}
ZERO_EXTRA = {0x200B}
JAMO_BLOCKS = [(0x1160, 0x11FF), (0xD7B0, 0xD7FF)]
WIDE_CLASSES = {"W", "F"}


def categories(path):
    found = {}
    first = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            fields = line.split(";")
            if len(fields) < 3:
                continue
            code, name, cat = int(fields[0], 16), fields[1], fields[2]
            if name.endswith(", First>"):
                first = code
                continue
            start = first if name.endswith(", Last>") else code
            first = None
            for c in range(start, code + 1):
                found[c] = cat
    return found


def east_asian_width(path):
    widths = {}
    missing = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"#\s*@missing:\s*([0-9A-Fa-f.]+)\s*;\s*(\w+)", line)
            if m:
                missing.append((m.group(1), m.group(2)))
                continue
            data = line.split("#", 1)[0].strip()
            if not data:
                continue
            span, value = (x.strip() for x in data.split(";"))
            lo, _, hi = span.partition("..")
            for c in range(int(lo, 16), int(hi or lo, 16) + 1):
                widths[c] = value
    defaults = {}
    for span, value in missing:
        lo, _, hi = span.partition("..")
        for c in range(int(lo, 16), int(hi or lo, 16) + 1):
            defaults[c] = value
    defaults.update(widths)
    return defaults


def unicode_years(path):
    with open(path, encoding="utf-8") as f:
        head = f.read(2000)
    m = re.search(r"(?:©|\(c\))\s*(?:(\d{4})-)?(\d{4})", head, re.I)
    if not m:
        sys.exit("gen-wcwidth.py: no copyright year in %s" % path)
    return "1991-" + m.group(2)


def intervals(points):
    out = []
    for c in sorted(points):
        if out and out[-1][1] == c - 1:
            out[-1][1] = c
        else:
            out.append([c, c])
    return out


def table(name, spans):
    lines = ["static const unsigned int %s[][2] = {" % name]
    for i in range(0, len(spans), 4):
        row = ", ".join("{ 0x%x, 0x%x }" % (lo, hi) for lo, hi in spans[i:i + 4])
        lines.append("\t" + row + ",")
    lines.append("};")
    return lines


FUNCTIONS = """\
static int
xo_wcw_lookup(unsigned int c, const unsigned int (*t)[2], size_t n)
{
	size_t lo = 0, hi = n;

	while (lo < hi) {
		size_t mid = lo + (hi - lo) / 2;

		if (c < t[mid][0])
			hi = mid;
		else if (c > t[mid][1])
			lo = mid + 1;
		else
			return 1;
	}
	return 0;
}

static int
xo_wcwidth(wchar_t ucs)
{
	if (ucs == 0)
		return 0;
	if (ucs < 0x20 || (ucs >= 0x7f && ucs < 0xa0))
		return -1;
	if (xo_wcw_lookup((unsigned int)ucs, xo_wcw_zero, sizeof(xo_wcw_zero) / sizeof(xo_wcw_zero[0])))
		return 0;
	if (xo_wcw_lookup((unsigned int)ucs, xo_wcw_wide, sizeof(xo_wcw_wide) / sizeof(xo_wcw_wide[0])))
		return 2;
	return 1;
}
"""


def main():
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__.strip())
    ucd = sys.argv[1]
    here = os.path.dirname(os.path.abspath(__file__))
    output = sys.argv[2] if len(sys.argv) == 3 else os.path.join(here, "xo_wcwidth.h")
    cats = categories(os.path.join(ucd, "UnicodeData.txt"))
    eaw_path = os.path.join(ucd, "EastAsianWidth.txt")
    eaw = east_asian_width(eaw_path)

    zero = {c for c, cat in cats.items() if cat in ZERO_CATEGORIES} - ONE_WIDE
    zero |= ZERO_EXTRA
    for lo, hi in JAMO_BLOCKS:
        if any(lo <= c <= hi for c in cats):
            zero |= set(range(lo, hi + 1))
    wide = {c for c, w in eaw.items() if w in WIDE_CLASSES} - zero

    text = [
        "/* SPDX-License-Identifier: BSD-2-Clause AND Unicode-3.0 */",
        "/* Copyright (c) 2026 The Blueberry Pie OS Authors */",
        "/* Copyright (c) %s Unicode, Inc. */" % unicode_years(eaw_path),
        "",
        "#include <stddef.h>",
        "#include <wchar.h>",
        "",
    ]
    text += table("xo_wcw_zero", intervals(zero)) + [""]
    text += table("xo_wcw_wide", intervals(wide)) + [""]
    with open(output, "w", encoding="ascii") as f:
        f.write("\n".join(text) + "\n" + FUNCTIONS)


if __name__ == "__main__":
    main()
