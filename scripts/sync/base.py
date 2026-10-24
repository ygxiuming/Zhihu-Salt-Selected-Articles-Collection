#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""同步框架基座：HTTP 会话、限速重试、断点进度、跨源去重、文章落盘。

所有 sync 适配器继承 SourceAdapter 并实现 fetch_new()。
"""
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalog import (REPO, plain_name, rebuild_index, safe_dir, write_catalog,
                     write_index)
from cleanlib import build_markdown, norm_title, normalize_filename

PROGRESS_DIR = safe_dir("data") / "progress"
RATE_SECONDS = float(os.environ.get("SYNC_RATE", "1.0") or "1.0")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


@dataclass
class Article:
    title: str
    source: str
    source_url: str
    paragraphs: list = field(default_factory=list)
    column: str = ""
    date: str = ""


def session() -> requests.Session:
    """带重试/退避的 requests 会话；调用方自行控制每次请求间限速。"""
    s = requests.Session()
    s.headers.update({"User-Agent": UA,
                      "Accept-Language": "zh-CN,zh;q=0.9"})
    retry = Retry(total=3, backoff_factor=2,
                  status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=("GET",))
    s.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=4))
    s.mount("http://", HTTPAdapter(max_retries=retry, pool_maxsize=4))
    return s


def polite_get(sess: requests.Session, url: str, timeout: int = 25):
    """限速 GET：两次请求之间至少间隔 RATE_SECONDS 秒。"""
    time.sleep(RATE_SECONDS)
    return sess.get(url, timeout=timeout)


def load_progress(source: str) -> dict:
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    p = PROGRESS_DIR / f"{source}.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            return {}
    return {}


def save_progress(source: str, data: dict) -> None:
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    (PROGRESS_DIR / f"{plain_name(source)}.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8")


def load_known_titles() -> set:
    """已收录标题指纹集合（跨源去重）。"""
    idx = REPO / "data" / "articles_index.json"
    if not idx.exists():
        return set()
    data = json.loads(idx.read_text(encoding="utf-8"))
    return {a["k"] for a in data.get("articles", []) if a.get("k")}


def load_known_urls() -> set:
    """已收录原文 URL 集合（列表扫描去重，配合标题指纹双保险）。"""
    idx = REPO / "data" / "articles_index.json"
    if not idx.exists():
        return set()
    data = json.loads(idx.read_text(encoding="utf-8"))
    return {a["u"] for a in data.get("articles", []) if a.get("u")}


def existing_file(source: str, title: str) -> bool:
    """按规范化文件名判断是否已存在同名文章（标题去重之外的兜底）。"""
    stem = normalize_filename(title)
    return (safe_dir(source) / f"{stem}.md").exists()


def unique_name(source: str, title: str, source_url: str) -> str:
    """目标文件名；重名时用源文章 ID 后缀区分。"""
    stem = normalize_filename(title)
    base = safe_dir(source)
    if not (base / f"{stem}.md").exists():
        return f"{stem}.md"
    m = re.search(r"/[aAuU]?/(\d+)", source_url or "")
    suffix = f"（a{m.group(1)}）" if m else f"（{int(time.time()) % 100000}）"
    return f"{stem}{suffix}.md"


class SourceAdapter:
    """源适配器基类。fetch_new 依次产出 Article，自行处理断点与停止条件。"""
    name = "base"
    enabled = True

    def __init__(self, limit: int = 0):
        self.limit = limit          # 本次最多抓取篇数；0 = 不限
        self.sess = session()
        self.known = load_known_titles()
        self.known_urls = load_known_urls()
        self.written = 0
        self.skipped = 0
        self.failed = 0

    def already_known(self, title: str, url: str) -> bool:
        """URL 或标题指纹命中即视为已收录。"""
        if url and url in self.known_urls:
            return True
        key = norm_title(title)
        return bool(key) and key in self.known

    def health(self) -> bool:
        """源站可达性检查；不可达返回 False 并整体跳过。"""
        return self.enabled

    def fetch_new(self):
        """生成器：产出待保存的 Article（已按需限速）。"""
        raise NotImplementedError

    def process(self) -> dict:
        """执行同步：抓取→去重→落盘→推进断点，返回统计。

        无论新增还是跳重，都调用 after_save 推进断点，
        避免重复文章导致每日空转。
        """
        if not self.health():
            return {"source": self.name, "status": "跳过（源站不可达或未启用）",
                    "written": 0, "skipped": 0, "failed": 0}
        for art in self.fetch_new():
            try:
                key = norm_title(art.title)
                if art.source_url in self.known_urls or (key and key in self.known):
                    self.skipped += 1
                    saved = False
                else:
                    self.write_article(art)
                    if key:
                        self.known.add(key)
                    if art.source_url:
                        self.known_urls.add(art.source_url)
                    self.written += 1
                    saved = True
                self.after_save(art, saved)
            except Exception as exc:  # 单篇失败不阻塞整批
                self.failed += 1
                print(f"  [{self.name}] 保存失败 {art.title}: {exc}")
            if self.limit and self.written >= self.limit:
                print(f"  [{self.name}] 达到本次上限 {self.limit}，停止")
                break
        return {"source": self.name, "status": "完成",
                "written": self.written, "skipped": self.skipped,
                "failed": self.failed}

    def write_article(self, art: Article):
        name = unique_name(art.source, art.title, art.source_url)
        src_dir = safe_dir(art.source)
        src_dir.mkdir(parents=True, exist_ok=True)
        target = src_dir / plain_name(name)
        meta = {"title": art.title, "source": art.source,
                "source_url": art.source_url}
        if art.column:
            meta["column"] = art.column
        if art.date:
            meta["date"] = art.date
        target.write_text(build_markdown(meta, art.paragraphs), encoding="utf-8")

    def after_save(self, art: Article, saved: bool):
        """子类钩子：每篇处理完（无论新增或跳重）后推进断点进度。"""


def finalize(summary: list) -> str:
    """全部源跑完后：重建索引与目录页，返回 GitHub Step Summary 文本。"""
    articles = rebuild_index()
    write_index(articles)
    write_catalog(articles)
    lines = ["## 同步结果", "", "| 来源 | 状态 | 新增 | 跳重 | 失败 |",
             "|---|---|---|---|---|"]
    for row in summary:
        lines.append(f"| {row['source']} | {row['status']} | {row['written']} "
                     f"| {row['skipped']} | {row['failed']} |")
    lines += ["", f"全库总计 **{len(articles)}** 篇"]
    return "\n".join(lines)
