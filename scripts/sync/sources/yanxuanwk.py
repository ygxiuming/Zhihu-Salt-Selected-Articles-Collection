#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「盐选文库」适配器（yanxuanwk.com，静态归档，约 1.1 万篇，公开免登录）。

站点结构（2026-10 实测）：
- 列表：首页 `/`，分页 `/page/N/`，每页约 10 篇，新→旧，`rel=next` 翻页
- 文章：中文 slug 路径，`h1` 为标题，`//time/@datetime` 为日期，
  正文在 `div.article-content` 内一句一段
- 越界分页返回 404

策略与 yanshen 相同：从列表页（新→旧）扫描到断点为止，
按新→旧抓取；保存成功即推进断点；单篇 404 视为永久缺失，
推进断点后继续（HTTP 基座已含 3 次退避重试，瞬时故障风险低）。
"""
from lxml import etree

from base import (Article, SourceAdapter, load_progress, polite_get,
                  save_progress)
from cleanlib import clean_paragraphs

PAGE_CAP = 1400  # 当前约 1167 页，留余量


class YanxuanwkAdapter(SourceAdapter):
    name = "盐选文库"
    BASE = "https://www.yanxuanwk.com"

    def health(self) -> bool:
        try:
            r = polite_get(self.sess, f"{self.BASE}/", timeout=20)
            if r.status_code == 200:
                return True
            print(f"  [{self.name}] 健康检查失败: HTTP {r.status_code}")
            return False
        except Exception as exc:
            print(f"  [{self.name}] 健康检查失败（站点不可达，已跳过）: {exc}")
            return False

    def list_entries(self, page: int):
        """抓一页列表，返回 (entries, has_next)。entries 为 (标题, url)。"""
        url = f"{self.BASE}/" if page == 1 else f"{self.BASE}/page/{page}/"
        r = polite_get(self.sess, url, timeout=25)
        if r.status_code != 200:
            return [], False
        tree = etree.HTML(r.content)
        entries = []
        for block in tree.xpath("//article[.//h2//a]"):
            a = block.xpath(".//h2//a")[0]
            href = (a.get("href") or "").strip()
            title = a.xpath("string(.)").strip()
            if href and title:
                entries.append((title, self.join(href)))
        nxt = tree.xpath("//a[@rel=\"next\"]/@href")
        return entries, bool(nxt)

    def join(self, href: str) -> str:
        return href if href.startswith("http") else self.BASE + href

    def fetch_new(self):
        marker = load_progress("yanxuanwk").get("last_url", "")
        page, hit_marker = 1, False
        while page <= PAGE_CAP and not hit_marker:
            entries, has_next = self.list_entries(page)
            if not entries:
                break
            for title, u in entries:
                if u == marker:
                    hit_marker = True
                    break
                art = self.fetch_article(title, u)
                if art is None:
                    # 静态归档 404 视为永久缺失：推进断点后继续
                    save_progress("yanxuanwk", {"last_url": u})
                    continue
                yield art
            if hit_marker or not has_next:
                break
            page += 1
        if page > PAGE_CAP:
            print(f"  [{self.name}] 达到列表页安全上限 {PAGE_CAP}，停止")

    def fetch_article(self, listing_title: str, url: str):
        try:
            r = polite_get(self.sess, url, timeout=30)
        except Exception as exc:
            print(f"  [{self.name}] 请求失败 {url}: {exc}")
            return None
        if r.status_code != 200:
            return None
        tree = etree.HTML(r.content)
        h1 = tree.xpath("//h1//text()")
        title = (h1[0].strip() if h1 and h1[0].strip() else listing_title)
        dates = tree.xpath("//time/@datetime")
        date = dates[0].strip()[:10] if dates else ""
        ps = tree.xpath("//div[contains(@class, 'article-content')]//p")
        if not ps:
            ps = tree.xpath("//article//p")
        body_lines = ["".join(p.itertext()) for p in ps]
        paragraphs = clean_paragraphs(body_lines, self.name)
        if not paragraphs:
            return None
        return Article(title=title, source=self.name, source_url=url,
                       paragraphs=paragraphs, date=date)

    def after_save(self, art: Article, saved: bool):
        save_progress("yanxuanwk", {"last_url": art.source_url})
