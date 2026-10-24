#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「知乎搬运工」适配器（zhbyg.top/a/{id}，ID 递增，站点不稳定）。

策略：从断点 ID +1 起逐个尝试；连续 MAX_MISSES 次失败视为已到最新。
重试由 HTTP 基座处理（3 次退避重试），最终失败视为永久缺失并推进断点，
避免每日空转重试。
"""
from lxml import etree

from base import (Article, SourceAdapter, load_progress, polite_get,
                  save_progress)
from cleanlib import clean_paragraphs


class ZhbygAdapter(SourceAdapter):
    name = "知乎搬运工"
    BASE = "https://www.zhbyg.top"
    MAX_MISSES = 30

    def health(self) -> bool:
        try:
            r = polite_get(self.sess, f"{self.BASE}/", timeout=15)
            return r.status_code == 200
        except Exception as exc:
            print(f"  [{self.name}] 健康检查失败（站点常失联，已跳过）: {exc}")
            return False

    def fetch_new(self):
        last_id = int(load_progress("zhbyg").get("last_id", 0))
        nid = last_id + 1
        misses = 0
        while misses < self.MAX_MISSES:
            if self.limit and self.attempts >= self.limit:
                print(f"  [{self.name}] 达到本次上限 {self.limit}，停止")
                break
            self.attempts += 1
            art = self.fetch_article(nid)
            if art is None:
                misses += 1
                save_progress("zhbyg", {"last_id": nid})  # 永久缺失也推进
                nid += 1
                continue
            misses = 0
            yield art
            nid += 1
        if misses >= self.MAX_MISSES:
            print(f"  [{self.name}] 连续 {misses} 次失败，视为已到最新")

    def fetch_article(self, nid: int):
        url = f"{self.BASE}/a/{nid}"
        try:
            r = polite_get(self.sess, url, timeout=25)
        except Exception as exc:
            print(f"  [{self.name}] 请求失败 {url}: {exc}")
            return None
        if r.status_code != 200:
            return None
        tree = etree.HTML(r.content)
        titles = tree.xpath("/html/body/div[2]/div/article/h1/text()") \
            or tree.xpath("//article/h1/text()")
        if not titles:
            return None
        title = titles[0].strip()
        ps = tree.xpath("/html/body/div[2]/div/article/div[2]/p") \
            or tree.xpath("//article//p")
        body_lines = ["".join(p.itertext()) for p in ps]
        paragraphs = clean_paragraphs(body_lines, "知乎搬运工")
        if not paragraphs:
            return None
        return Article(title=title, source=self.name, source_url=url,
                       paragraphs=paragraphs)

    def __init__(self, limit: int = 0):
        super().__init__(limit)
        self.attempts = 0

    def after_save(self, art: Article, saved: bool):
        m = re_last_id(art.source_url)
        if m:
            save_progress("zhbyg", {"last_id": int(m.group(1))})


def re_last_id(url: str):
    import re
    return re.search(r"/a/(\d+)", url)
