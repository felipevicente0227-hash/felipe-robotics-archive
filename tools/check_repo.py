#!/usr/bin/env python3
"""Structural checks for this portfolio repo. Standard library only.

Run from the repo root:  python tools/check_repo.py

This exists because the failure mode of a portfolio repo is silent: a link
rots when a folder is renamed, and nothing complains until the person you
were trying to impress clicks it and gets a 404. These checks are cheap and
run on every push.

Checks (any failure exits 1):
  1. Every relative link in every README resolves to a file that exists.
  2. That match is case-sensitive, because GitHub serves paths case-
     sensitively even though Windows resolves them case-insensitively.
     Without this, a broken link passes locally and 404s once pushed.
  3. Every project folder linked from the root README has its own README.
  4. Every project README carries a "Tested conditions & limitations"
     section, so no project silently drops its honesty section.
  5. Every top-level folder is reachable from the root README, so a new
     project cannot be added and then left off the homepage.

Unfilled [__] placeholders are reported as information only and never fail
the build: they are deliberate markers for facts only the author can supply,
not defects.
"""

import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECTION = "Tested conditions & limitations"
SKIP_DIRS = {".git", ".github", "tools"}

# [label](target) or [label](<target with spaces>), image links included.
LINK_RE = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)>]*?)>?\s*\)")
PLACEHOLDER_RE = re.compile(r"\[[^\]\n]*__[^\]\n]*\]")

failures: list[str] = []
notes: list[str] = []


def fail(msg: str) -> None:
    failures.append(msg)


def resolves_case_sensitively(base: Path, target: str) -> bool:
    """True if every component of target matches the on-disk name exactly.

    Path.exists() is case-insensitive on Windows, so it happily confirms a
    link that GitHub will 404 on. Path.resolve() is worse than useless here:
    it rewrites the path to the real on-disk casing, erasing the very
    mismatch we are looking for. So walk the link's own components and
    compare each against the actual directory listing.
    """
    current = base
    for part in target.replace("\\", "/").split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            current = current.parent
            continue
        try:
            if part not in {e.name for e in current.iterdir()}:
                return False
        except (NotADirectoryError, FileNotFoundError, PermissionError):
            return False
        current = current / part
    return True


def readmes() -> list[Path]:
    found = []
    for path in ROOT.rglob("README.md"):
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        found.append(path)
    return sorted(found)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


# --- 1 & 2: every relative link resolves, case included ----------------------
linked_dirs: set[str] = set()
link_count = 0

for readme in readmes():
    text = readme.read_text(encoding="utf-8")
    for raw in LINK_RE.findall(text):
        target = urllib.parse.unquote(raw.split("#")[0].strip())
        if not target or target.startswith(("http://", "https://", "mailto:")):
            continue
        link_count += 1
        resolved = (readme.parent / target)
        if not resolved.exists():
            fail(f"dead link in {rel(readme)} -> {target}")
        elif not resolves_case_sensitively(readme.parent, target):
            fail(f"case mismatch in {rel(readme)} -> {target} (404s on GitHub)")
        elif readme.parent == ROOT and resolved.is_dir():
            linked_dirs.add(rel(resolved.resolve()))

# --- 3 & 4: project folders have a README, with the honesty section ----------
for d in sorted(linked_dirs):
    project_readme = ROOT / d / "README.md"
    if not project_readme.exists():
        fail(f"project folder linked from the homepage has no README: {d}")
        continue
    if SECTION not in project_readme.read_text(encoding="utf-8"):
        fail(f'{d}/README.md is missing its "{SECTION}" section')

# --- 5: no top-level project is missing from the homepage --------------------
for entry in sorted(ROOT.iterdir()):
    if not entry.is_dir() or entry.name in SKIP_DIRS or entry.name.startswith("."):
        continue
    name = rel(entry)
    # A container folder counts as covered when its children are linked
    # individually, which is how "more projects and competitions" is listed.
    covered = name in linked_dirs or any(d.startswith(name + "/") for d in linked_dirs)
    if not covered:
        fail(f"top-level folder not linked from the root README: {name}")

# --- information only --------------------------------------------------------
for readme in readmes():
    count = len(PLACEHOLDER_RE.findall(readme.read_text(encoding="utf-8")))
    if count:
        notes.append(f"{count:>3} placeholder(s) awaiting real data: {rel(readme)}")

# --- report ------------------------------------------------------------------
if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print(f"checked {link_count} local links across {len(readmes())} README files")

    if notes:
        print("\nplaceholders (informational, not failures):")
        for n in notes:
            print("  " + n)

    if failures:
        print(f"\n[FAIL] {len(failures)} problem(s):")
        for f in failures:
            print("  - " + f)
        sys.exit(1)

    print("\n[OK] all checks passed")
