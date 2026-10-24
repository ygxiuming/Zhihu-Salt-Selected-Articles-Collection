#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""目录页与元数据索引生成（scripts/migrate.py 与 scripts/sync/ 共用）。

安全模型与 migrate.py 一致：路径由 pathlib 从「已校验目录常量 +
plain_name 校验过的单一文件名」构建，读写均为 Path 对象方法。
"""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cleanlib import (SOURCES, escape_link_text, norm_title, parse_article,
                      pinyin_initial, preview_of)

REPO = Path(__file__).resolve().parent.parent
CATALOG_PREFIX = "目录-"


def plain_name(name: str) -> str:
    """校验单一文件名：不含路径分隔符、不是 "." / ".."，返回原名。"""
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        raise ValueError(f"非法文件名: {name!r}")
    return name


def safe_dir(rel: str) -> Path:
    """解析仓库根内的目录并校验边界；片段只能是代码常量。"""
    target = (REPO / rel).resolve()
    if target != REPO and REPO not in target.parents:
        raise ValueError(f"目录越出仓库根，已拒绝: {rel!r}")
    return target


def article_files():
    """遍历各源目录下的全部文章文件（排除目录页；未创建的源目录跳过）。"""
    for source in SOURCES:
        d = safe_dir(source)
        if not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            if p.is_file() and p.name.endswith(".md") \
                    and not p.name.startswith(CATALOG_PREFIX):
                yield source, p


def rebuild_index() -> list:
    """扫描全库文章的 front matter，重建元数据索引（t/s/u/c/p/i/k/v）。"""
    articles = []
    for source, p in article_files():
        try:
            raw = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raw = p.read_text(encoding="utf-8", errors="replace")
        parsed = parse_article(raw, source, p.stem)
        articles.append({
            "t": parsed["title"], "s": source, "u": parsed["source_url"],
            "c": parsed["column"], "p": f"{source}/{p.name}",
            "i": pinyin_initial(parsed["title"]),
            "k": norm_title(parsed["title"]),
            "v": preview_of([ln.strip() for ln in parsed["body_lines"]
                             if ln.strip()]),
        })
    return articles


def write_index(articles: list) -> None:
    data_dir = safe_dir("data")
    data_dir.mkdir(exist_ok=True)
    (data_dir / "articles_index.json").write_text(
        json.dumps({"generated": str(date.today()), "articles": articles},
                   ensure_ascii=False), encoding="utf-8")
    write_stats(articles)


def write_stats(articles: list) -> None:
    """生成小体积统计文件，供 README 动态徽章读取（shields.io JSON endpoint）。"""
    by_source = {}
    for a in articles:
        by_source[a["s"]] = by_source.get(a["s"], 0) + 1
    data_dir = safe_dir("data")
    data_dir.mkdir(exist_ok=True)
    (data_dir / "stats.json").write_text(
        json.dumps({"total": len(articles), "by_source": by_source,
                    "updated": str(date.today())},
                   ensure_ascii=False, indent=2), encoding="utf-8")


def write_catalog(articles: list) -> None:
    """重建目录页：每个源目录内放 目录-<首字母>.md，链接为同目录文件名。

    总览页为仓库根的 目录.md，链接指向子目录，全程无父级引用。
    """
    by_source = {}
    for a in articles:
        by_source.setdefault(a["s"], {}).setdefault(a["i"], []).append(a)
    for source, letters in by_source.items():
        src_dir = safe_dir(source)
        total = sum(len(v) for v in letters.values())
        letter_list = sorted(letters.keys())
        links = " ｜ ".join(f"[{L}](./{CATALOG_PREFIX}{L}.md)" for L in letter_list)
        (src_dir / f"{CATALOG_PREFIX}README.md").write_text(
            f"# {source} 目录\n\n共 **{total}** 篇，按拼音首字母分组：\n\n{links}\n",
            encoding="utf-8")
        for L, items in letters.items():
            items.sort(key=lambda a: a["t"])
            page = src_dir / f"{CATALOG_PREFIX}{plain_name(L)}.md"
            parts = [f"# {source} · {L}\n",
                     f"共 {len(items)} 篇 · [返回 {source} 目录](./{CATALOG_PREFIX}README.md)\n"]
            for a in items:
                fname = plain_name(a["p"].split("/", 1)[1])
                parts.append(f"## [{escape_link_text(a['t'])}](./{fname})\n")
                if a["u"]:
                    parts.append(f"[阅读原文]({a['u']})\n")
                if a["c"]:
                    parts.append(f"出自专栏：《{a['c']}》\n")
                if a["v"]:
                    parts.append(f"> {a['v']}\n")
            page.write_text("\n".join(parts), encoding="utf-8")
    overview = ["# 知乎盐选文章 · 总目录\n",
                "内链由文件系统自动生成并经校验脚本检查，指向同仓库文章文件。\n"]
    for source in sorted(by_source):
        total = sum(len(v) for v in by_source[source].values())
        overview.append(f"- [{source}](./{source}/{CATALOG_PREFIX}README.md)（{total} 篇）")
    (REPO / "目录.md").write_text("\n".join(overview) + "\n", encoding="utf-8")
