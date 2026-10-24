#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""仓库校验：目录内链、文件名兼容性、front matter 完整性、内容残留。

用法：uv run python scripts/validate.py
退出码：0 = 全部通过，1 = 存在问题（问题清单打印到 stdout）。
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cleanlib import SOURCES

REPO = Path(__file__).resolve().parent.parent
CATALOG_PREFIX = "目录-"
ILLEGAL = set('\\/:*?"<>|')
RESIDUE = ("&emsp;", "&ensp;", "&nbsp;", "备案号")

problems = {"bad_filename": [], "missing_frontmatter": [], "content_residue": [],
            "broken_catalog_link": [], "uncataloged_articles": []}


def check_filenames():
    for source in SOURCES:
        d = REPO / source
        if not d.is_dir():
            continue
        for p in d.iterdir():
            n = p.name
            if n.endswith(" .md") or n.startswith(".") or n != n.strip() \
                    or (set(n) & ILLEGAL):
                problems["bad_filename"].append(f"{source}/{n}")


def parse_front_matter(p: Path):
    try:
        text = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None, text
    if not text.startswith("---"):
        return None, text
    meta = {}
    for line in text.split("\n")[1:]:
        s = line.strip()
        if s == "---":
            return meta, text
        m = re.match(r'([A-Za-z_]+):\s*"(.*)"\s*$', s)
        if m:
            meta[m.group(1)] = m.group(2)
    return meta, text


def check_articles():
    stems = set()
    for source in SOURCES:
        d = REPO / source
        for p in sorted(d.glob("*.md")):
            if p.name.startswith(CATALOG_PREFIX):
                continue
            stems.add((source, p.name))
            meta, text = parse_front_matter(p)
            if not meta or "title" not in meta or "source" not in meta:
                problems["missing_frontmatter"].append(f"{source}/{p.name}")
            residue = [r for r in RESIDUE if r in text]
            if residue or re.search(r"(?m)^<br\b", text):
                problems["content_residue"].append(f"{source}/{p.name}: {residue}")
    return stems


def md_links(text: str):
    for m in re.finditer(r"\]\((\./[^)]+)\)", text):
        yield m.group(1)


def check_catalog_links(stems):
    """校验所有目录页内链均可解析为实际文章文件。"""
    catalog_files = []
    for source in SOURCES:
        catalog_files += list((REPO / source).glob(f"{CATALOG_PREFIX}*.md"))
    catalog_files.append(REPO / "目录.md")
    linked = set()
    for cf in catalog_files:
        base = cf.parent
        for link in md_links(cf.read_text(encoding="utf-8")):
            target = (base / link).resolve()
            if not target.is_file():
                problems["broken_catalog_link"].append(f"{cf.name} → {link}")
            elif target.suffix == ".md" and not target.name.startswith(CATALOG_PREFIX):
                linked.add((target.parent.name, target.name))
    missing = stems - linked
    if missing:
        problems["uncataloged_articles"] = sorted(f"{s}/{n}" for s, n in missing)[:50]
        problems["uncataloged_articles"].append(f"（共 {len(missing)} 篇未收录）")


def main():
    check_filenames()
    stems = check_articles()
    check_catalog_links(stems)
    total = sum(len(v) for v in problems.values())
    for key, items in problems.items():
        print(f"[{'FAIL' if items else 'PASS'}] {key}: {len(items)}")
        for item in items[:10]:
            print(f"    - {item}")
    counts = {s: len(list((REPO / s).glob('*.md'))) for s in SOURCES}
    print(f"文章总数: {sum(counts.values())} {counts}")
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
