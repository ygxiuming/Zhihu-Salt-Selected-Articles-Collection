#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「我不是盐神」适配器（onehu.xyz，Hexo 站点，活跃更新）。

策略：从 /archives/ 归档页（新→旧）扫描到上次断点为止，
按新→旧顺序抓取文章；每篇保存成功即推进断点，中断不丢进度。
"""
import re

from lxml import etree

from base import (Article, SourceAdapter, load_progress, polite_get,
                  save_progress)

PAGE_CAP = 600  # 归档页安全上限（当前约 417 页）


class YanshenAdapter(SourceAdapter):
    name = "我不是盐神"
    BASE = "https://onehu.xyz"

    def health(self) -> bool:
        try:
            r = polite_get(self.sess, f"{self.BASE}/archives/", timeout=25)
            return r.status_code == 200
        except Exception as exc:
            print(f"  [{self.name}] 健康检查失败: {exc}")
            return False

    def list_archive(self, marker_url: str):
        """扫描归档页，返回 (title, url) 列表（新→旧），到断点即停。"""
        entries, next_url, pages = [], f"{self.BASE}/archives/", 0
        while next_url and pages < PAGE_CAP:
            pages += 1
            r = polite_get(self.sess, next_url, timeout=25)
            if r.status_code != 200:
                break
            tree = etree.HTML(r.content)
            for a in tree.xpath("//a[./time and ./div]"):
                href = (a.get("href") or "").strip()
                if not href:
                    continue
                url = urllib_join(self.BASE, href)
                title = (a.xpath("./div/text()") or [""])[0].strip()
                if title and url != marker_url:
                    entries.append((title, url))
                elif url == marker_url:
                    return entries, True
            nxt = tree.xpath('//a[@rel="next"]/@href')
            next_url = urllib_join(self.BASE, nxt[0]) if nxt else None
        return entries, False

    def fetch_new(self):
        marker = load_progress("yanshen").get("last_url", "")
        entries, hit_marker = self.list_archive(marker)
        if marker and not hit_marker:
            print(f"  [{self.name}] 警告：归档中未找到断点 {marker}，按全量处理")
        for title, url in entries:
            art = self.fetch_article(title, url)
            if art is None:
                # 抓取失败即停止本轮：断点未推进，下次运行从此重试
                print(f"  [{self.name}] 抓取失败，本轮停止：{url}")
                break
            yield art

    def fetch_article(self, listing_title: str, url: str):
        try:
            r = polite_get(self.sess, url, timeout=30)
        except Exception as exc:
            print(f"  [{self.name}] 请求失败 {url}: {exc}")
            return None
        if r.status_code != 200:
            return None
        tree = etree.HTML(r.content)
        titles = tree.xpath("//article//h1/text()")
        title = (titles[0].strip() if titles and titles[0].strip()
                 else listing_title)
        dates = tree.xpath("//article//time/@datetime")
        date = re.sub(r"T.*", "", dates[0]) if dates else ""
        ps = tree.xpath("//*[@id='board']/article/div[1]/p")
        if not ps:
            ps = tree.xpath("//article//p")
        body_lines = ["".join(p.itertext()) for p in ps]
        paragraphs = clean_article(body_lines)
        if not paragraphs:
            return None
        return Article(title=title, source=self.name, source_url=url,
                       paragraphs=paragraphs, date=date)

    def after_save(self, art: Article, saved: bool):
        save_progress("yanshen", {"last_url": art.source_url})


def urllib_join(base: str, href: str) -> str:
    if href.startswith("http"):
        return href
    return base + ("" if href.startswith("/") else "/") + href


def clean_article(body_lines):
    """复用清洗库：去水印/实体/分页行，重组段落。"""
    from cleanlib import clean_paragraphs
    return clean_paragraphs(body_lines, "我不是盐神")
