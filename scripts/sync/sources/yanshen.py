#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「我不是盐神」适配器（onehu.xyz，Hexo 站点，活跃更新）。

策略：每次全量扫描 /archives/ 归档页（新→旧），按 URL 与标题指纹
双重去重后抓取未知文章。无断点状态，永不漏抓；
每日运行多花约 7 分钟扫描（417 页），换取对漏抓免疫。
"""
import re

from lxml import etree

from base import Article, SourceAdapter, polite_get

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

    def fetch_new(self):
        next_url, pages = f"{self.BASE}/archives/", 0
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
                url = self.join(href)
                title = (a.xpath("./div/text()") or [""])[0].strip()
                if not title or self.already_known(title, url):
                    continue
                art = self.fetch_article(title, url)
                if art is None:
                    # 抓取失败（重试后）：跳过该篇继续扫描，
                    # 下一轮运行会因 URL 仍未收录而重试
                    print(f"  [{self.name}] 抓取失败，跳过：{url}")
                    continue
                yield art
            nxt = tree.xpath('//a[@rel="next"]/@href')
            next_url = self.join(nxt[0]) if nxt else None
        if pages >= PAGE_CAP:
            print(f"  [{self.name}] 达到归档页安全上限 {PAGE_CAP}，停止")

    def join(self, href: str) -> str:
        return href if href.startswith("http") else self.BASE + href

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


def clean_article(body_lines):
    """复用清洗库：去水印/实体/分页行，重组段落。"""
    from cleanlib import clean_paragraphs
    return clean_paragraphs(body_lines, "我不是盐神")
