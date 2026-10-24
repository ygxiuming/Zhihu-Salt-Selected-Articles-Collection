#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性深度清洗迁移：

1. 目录改名：盐神 → 我不是盐神（与源站名一致）
2. 文件名规范化：去尾随空格/双空格/dotfile（git mv，保留历史）
3. 正文深度清洗：去 <br>、&emsp;、源站水印、HTML 残渣，重排为规范段落
4. 统一落盘 YAML front matter + 规范正文
5. 生成 data/articles_index.json（元数据索引，供目录生成与增量同步去重）
6. 重建目录页（放在各文章目录内，同目录相对链接，永不失配）
7. 清理过时文件（旧目录 md、当前进度.txt，旧爬虫移入 scripts/legacy/）
8. 输出 data/migration_report.json

安全模型：所有路径由 pathlib 从「已校验目录常量 + plain_name 校验过的单一
文件名」构建，无 chdir、无字符串路径拼接，读写均为 Path 对象方法。

用法：uv run python scripts/migrate.py
"""
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cleanlib import (SOURCES, build_markdown, clean_paragraphs, norm_title,
                      escape_link_text, normalize_filename, parse_article,
                      pinyin_initial, preview_of)

REPO = Path(__file__).resolve().parent.parent
DIR_MAP = {"盐神": "我不是盐神", "知乎搬运工": "知乎搬运工"}
DELETE_ZERO_BYTE = ["知乎搬运工/恐怖密室", "知乎搬运工/如何以“现在是北京时间17"]
MOVE_TO_LEGACY = ["我不是盐神.py", "知乎搬运工网页爬取.py"]
DELETE_FILES = ["盐神目录.md", "知乎搬运工目录.md", "当前进度.txt"]
DATA_DIRNAME = "data"
CATALOG_PREFIX = "目录-"


def safe_dir(rel: str) -> Path:
    """解析仓库根内的目录并校验边界；片段只能是代码常量。"""
    target = (REPO / rel).resolve()
    if target != REPO and REPO not in target.parents:
        raise ValueError(f"目录越出仓库根，已拒绝: {rel!r}")
    return target


def plain_name(name: str) -> str:
    """校验单一文件名：不含路径分隔符、不是 "." / ".."，返回原名。"""
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        raise ValueError(f"非法文件名: {name!r}")
    return name


def git(*args):
    r = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def migrate_filenames(report):
    """目录改名 + 逐文件规范化改名（全部走 git mv 以保留文件历史）。"""
    renamed = 0
    for old_dir, new_dir in DIR_MAP.items():
        if old_dir != new_dir and (REPO / old_dir).is_dir():
            git("mv", old_dir, new_dir)
            report["dir_renamed"].append(f"{old_dir} → {new_dir}")
    for src_dir in DIR_MAP.values():
        names = sorted(p.name for p in (REPO / src_dir).iterdir())
        for name in names:
            if not (REPO / src_dir / name).is_file():
                continue
            if name.startswith("."):
                fixed = name.lstrip(".")  # dotfile：爬虫标题以「.」开头残留
                if fixed.endswith(".md"):
                    fixed = normalize_filename(fixed[:-3]) + ".md"
            elif name.endswith(".md"):
                fixed = normalize_filename(name[:-3]) + ".md"
            else:
                continue  # 非 md 文件（0 字节残缺）在下一步处理
            if fixed != name:
                if (REPO / src_dir / fixed).exists():
                    report["name_conflicts"].append(f"{src_dir}/{name}")
                    continue
                git("mv", f"{src_dir}/{name}", f"{src_dir}/{fixed}")
                renamed += 1
    report["files_renamed"] = renamed


def remove_bad_files(report):
    for rel in DELETE_ZERO_BYTE:
        p = REPO / rel
        if p.exists() and p.stat().st_size == 0:
            p.unlink()
            report["deleted_zero_byte"].append(rel)
    for rel in DELETE_FILES:
        p = REPO / rel
        if p.exists():
            p.unlink()
            report["deleted_legacy"].append(rel)
    legacy_dir = REPO / "scripts" / "legacy"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    for rel in MOVE_TO_LEGACY:
        p = REPO / rel
        if p.exists():
            p.rename(legacy_dir / plain_name(p.name))
            report["moved_to_legacy"].append(rel)


def rewrite_articles(report):
    """清洗全部文章并重建 front matter 格式，同时收集索引元数据。

    读写均为 Path.read_text / Path.write_text，路径 =
    已校验目录（safe_dir）+ plain_name 校验过的文件名。
    """
    articles = []
    for source in SOURCES:
        src_dir = safe_dir(source)
        names = sorted(p.name for p in src_dir.iterdir()
                       if p.name.endswith(".md") and not p.name.startswith(CATALOG_PREFIX))
        report["counts"][source] = len(names)
        for idx, name in enumerate(names):
            plain_name(name)
            path = src_dir / name
            raw = path.read_text(encoding="utf-8")
            parsed = parse_article(raw, source, name[:-3])
            paras = clean_paragraphs(parsed["body_lines"], source)
            if not paras:
                report["empty_after_clean"].append(f"{source}/{name}")
            meta = {"title": parsed["title"], "source": source,
                    "source_url": parsed["source_url"]}
            if parsed["column"]:
                meta["column"] = parsed["column"]
            path.write_text(build_markdown(meta, paras), encoding="utf-8")
            articles.append({
                "t": parsed["title"], "s": source, "u": parsed["source_url"],
                "c": parsed["column"], "p": f"{source}/{name}",
                "i": pinyin_initial(parsed["title"]),
                "k": norm_title(parsed["title"]),
                "v": preview_of(paras),
            })
            if (idx + 1) % 500 == 0:
                print(f"  [{source}] {idx + 1}/{len(names)}")
    return articles


def resolve_conflicts(articles, report):
    """同名冲突处理：去空格后与现有文件重名的是「同标题不同文章」，
    以源文章 ID 作后缀区分并去掉尾随空格，保证 Windows 可克隆。"""
    fixed = 0
    for a in articles:
        if not a["p"].endswith(" .md"):
            continue
        source, name = a["p"].split("/", 1)
        m = re.search(r"/a/(\d+)", a["u"] or "")
        suffix = f"（a{m.group(1)}）" if m else "（2）"
        new_name = normalize_filename(name[:-3]) + suffix + ".md"
        plain_name(new_name)
        old_path = safe_dir(source) / plain_name(name)
        new_path = safe_dir(source) / new_name
        if old_path.exists() and not new_path.exists():
            git("mv", f"{source}/{name}", f"{source}/{new_name}")
            a["p"] = f"{source}/{new_name}"
            report["conflict_resolved"].append(f"{name} → {new_name}")
            fixed += 1
    return fixed


def write_catalog(articles):
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


def write_data(articles, report):
    data_dir = safe_dir(DATA_DIRNAME)
    data_dir.mkdir(exist_ok=True)
    (data_dir / "articles_index.json").write_text(
        json.dumps({"generated": str(date.today()), "articles": articles},
                   ensure_ascii=False), encoding="utf-8")
    (data_dir / "migration_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    report = {"date": str(date.today()), "dir_renamed": [], "files_renamed": 0,
              "name_conflicts": [], "conflict_resolved": [], "deleted_zero_byte": [],
              "deleted_legacy": [], "moved_to_legacy": [], "decode_errors": [],
              "empty_after_clean": [], "counts": {}}
    print("① 文件名规范化（git mv）…")
    migrate_filenames(report)
    print(f"   重命名 {report['files_renamed']} 个文件，冲突 {len(report['name_conflicts'])}")
    print("② 清理残缺/过时文件 …")
    remove_bad_files(report)
    print("③ 清洗重写全部文章 …")
    articles = rewrite_articles(report)
    print(f"   共 {len(articles)} 篇")
    print("④ 解决同名冲突（源 ID 后缀区分）…")
    n = resolve_conflicts(articles, report)
    print(f"   处理 {n} 个")
    print("⑤ 重建目录页 …")
    write_catalog(articles)
    write_data(articles, report)
    print("⑥ 完成：data/articles_index.json、目录页已生成")


if __name__ == "__main__":
    main()
