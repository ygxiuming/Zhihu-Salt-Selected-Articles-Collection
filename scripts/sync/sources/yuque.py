#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""语雀「知乎盐选库」导入适配器（yuque.com/dayuyu-ualcu/azo1ge，1036 篇精选，已停更）。

访问门槛（2026-10 实测）：知识库需语雀账号登录 + 文档密码，匿名不可读。
启用方式：浏览器登录并解锁后，把会话 Cookie 配置为环境变量 YUQUE_COOKIE
（CI 上为同名仓库 Secret）。

内容形态：每个文档就是一篇文章的完整镜像（API 的 sourcecode 字段为
语雀导出的 markdown），直接全文导入，无需回源 onehu/zhbyg。

接口：
- 知识库落地页 → appData.book.toc（1036 个文档 slug 与标题）
- GET /api/docs/{slug}?book_id=…&mode=markdown → data.sourcecode
"""
import json
import os
import re
import urllib.parse

from base import Article, SourceAdapter, load_progress, polite_get, save_progress
from cleanlib import clean_markdown_source

BOOK_URL = "https://www.yuque.com/dayuyu-ualcu/azo1ge"
_APPDATA_RE = re.compile(
    r"window\.appData = JSON\.parse\(decodeURIComponent\(\"(.*?)\"\)\)", re.S)


class YuqueAdapter(SourceAdapter):
    name = "语雀盐选库"
    enabled = bool(os.environ.get("YUQUE_COOKIE"))

    def __init__(self, limit: int = 0):
        super().__init__(limit)
        self.sess.headers["Cookie"] = os.environ.get("YUQUE_COOKIE", "")
        self.sess.headers["Referer"] = BOOK_URL

    def health(self) -> bool:
        if not self.enabled:
            print(f"  [{self.name}] 跳过：未设置 YUQUE_COOKIE"
                  "（浏览器登录语雀并解锁知识库后，把 Cookie 配置为 Secret 即可启用）")
            return False
        try:
            r = polite_get(self.sess, BOOK_URL, timeout=25)
        except Exception as exc:
            print(f"  [{self.name}] 健康检查失败（已跳过）: {exc}")
            return False
        if r.status_code != 200 or "window.appData" not in r.text:
            print(f"  [{self.name}] 未取得知识库数据（Cookie 可能过期，HTTP {r.status_code}）")
            return False
        return True

    def toc_entries(self):
        """返回 [(标题, 文档页 URL)]，按目录顺序。"""
        r = polite_get(self.sess, BOOK_URL, timeout=25)
        m = _APPDATA_RE.search(r.text)
        if not m:
            return []
        data = json.loads(urllib.parse.unquote(m.group(1)))
        book = data.get("book") or {}
        self.book_id = book.get("id")
        toc = book.get("toc") or []
        if isinstance(toc, str):
            toc = json.loads(toc)
        out = []
        for item in toc:
            if item.get("type") == "DOC" and item.get("url") and item.get("title"):
                out.append((item["title"].strip(),
                            f"{BOOK_URL}/{item['url']}"))
        return out

    def fetch_source(self, slug: str) -> str:
        r = polite_get(self.sess,
                       f"https://www.yuque.com/api/docs/{slug}"
                       f"?book_id={self.book_id}&merge_dynamic_data=false&mode=markdown",
                       timeout=30)
        if r.status_code != 200:
            return ""
        d = (r.json() or {}).get("data") or {}
        return d.get("sourcecode") or ""

    def fetch_new(self):
        entries = self.toc_entries()
        if not entries:
            print(f"  [{self.name}] 目录为空，结束")
            return iter([])
        progress = load_progress("yuque")
        empty = set(progress.get("empty", []))
        print(f"  [{self.name}] 知识库共 {len(entries)} 篇文档"
              f"（历史空文档 {len(empty)}）")
        for title, url in entries:
            if self.already_known(title, url):
                continue
            slug = url.rsplit("/", 1)[-1]
            if slug in empty:
                continue
            md = self.fetch_source(slug)
            paragraphs = clean_markdown_source(md)
            if not paragraphs:
                # 已停更库中相当部分文档为空（仅图片/已清空），
                # 记入 empty 集合避免每轮重拉
                empty.add(slug)
                save_progress("yuque", {"empty": sorted(empty)})
                print(f"  [{self.name}] 正文为空，跳过并记录：{title}")
                continue
            # 语雀文档标题与知乎问题一致，正文首段常与标题重复
            if paragraphs and paragraphs[0] == title:
                paragraphs = paragraphs[1:]
            date = ""
            yield Article(title=title, source=self.name, source_url=url,
                          paragraphs=paragraphs, date=date)
