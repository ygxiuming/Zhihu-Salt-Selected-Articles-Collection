#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""语雀「知乎盐选库」导入适配器（yuque.com/dayuyu-ualcu/azo1ge，约 1000+ 篇精选，已停更）。

访问门槛（2026-10 实测）：该文档需要语雀账号登录 + 文档密码双重验证，
匿名请求只返回登录门禁页。因此本适配器默认关闭：
  1. 在浏览器登录语雀并输入文档密码，直到能看到正文；
  2. 把该会话的 Cookie 复制为仓库 Secret YUQUE_COOKIE（整行即可）；
  3. 之后运行 --sources yuque 即导入。

文档正文（lake 格式）里是各文章的原始链接；本适配器按域名分发：
  - onehu.xyz   → 复用 YanshenAdapter 抓取
  - zhbyg.top   → 源站已失联，记录条数后跳过
其他域名（知乎站内等）无法抓取，同样只记录。
"""
import json
import os
import re
import urllib.parse

from base import (Article, SourceAdapter, load_progress, polite_get,
                  save_progress)

DOC_URL = "https://www.yuque.com/dayuyu-ualcu/azo1ge"
_APPDATA_RE = re.compile(
    r"window\.appData = JSON\.parse\(decodeURIComponent\(\"(.*?)\"\)\)", re.S)
_LINK_RE = re.compile(r"https?://(?:www\.)?(onehu\.xyz|zhbyg\.top)/[^\s\"'<>（）()）]+")
_UNESCAPE = (("&#x2F;", "/"), ("&amp;", "&"), ("&quot;", '"'))


class YuqueAdapter(SourceAdapter):
    name = "语雀盐选库"
    enabled = bool(os.environ.get("YUQUE_COOKIE"))

    def __init__(self, limit: int = 0):
        super().__init__(limit)
        self.sess.headers["Cookie"] = os.environ.get("YUQUE_COOKIE", "")

    def health(self) -> bool:
        if not self.enabled:
            print(f"  [{self.name}] 跳过：未设置 YUQUE_COOKIE"
                  "（浏览器登录语雀并解锁文档后，把 Cookie 复制为 Secret 即可启用）")
            return False
        try:
            r = polite_get(self.sess, DOC_URL, timeout=25)
        except Exception as exc:
            print(f"  [{self.name}] 健康检查失败（已跳过）: {exc}")
            return False
        if r.status_code != 200 or "window.appData" not in r.text:
            print(f"  [{self.name}] 未能取得文档数据（Cookie 可能过期，HTTP {r.status_code}）")
            return False
        return True

    def doc_body(self) -> str:
        r = polite_get(self.sess, DOC_URL, timeout=25)
        m = _APPDATA_RE.search(r.text)
        if not m:
            return ""
        data = json.loads(urllib.parse.unquote(m.group(1)))
        return (data.get("doc") or {}).get("body") or ""

    def extract_links(self, body: str):
        """按文档顺序提取 (url, 域名类别)，去重。"""
        seen, links = set(), []
        for m in _LINK_RE.finditer(body):
            url = m.group(0)
            for a, b in _UNESCAPE:
                url = url.replace(a, b)
            url = url.rstrip("。，、；！？)）】》.")
            key = url.lower()
            if key not in seen:
                seen.add(key)
                links.append((url, m.group(1)))
        return links

    def fetch_new(self):
        body = self.doc_body()
        if not body:
            print(f"  [{self.name}] 文档正文为空，结束")
            return iter([])
        links = self.extract_links(body)
        dead = [u for u, host in links if "zhbyg" in host]
        other = [u for u, host in links
                 if "zhbyg" not in host and "onehu" not in host]
        print(f"  [{self.name}] 文档共 {len(links)} 条链接"
              f"（onehu {len(links) - len(dead) - len(other)}、"
              f"zhbyg(失联) {len(dead)}、其他 {len(other)}）")

        from sources.yanshen import YanshenAdapter
        yanshen = YanshenAdapter(limit=0)
        done = set(load_progress("yuque").get("done", []))
        for url, host in links:
            if url in done or "zhbyg" in host or "onehu" not in host:
                continue
            if self.limit and self.written + self.skipped >= self.limit:
                break
            art = yanshen.fetch_article("", url)
            if art is None:
                # 非线性失败（重试后仍失败）不记完成，下次重试；
                # 这里区分不了 404 与瞬时错误，静态站按缺失记录
                done.add(url)
                save_progress("yuque", {"done": sorted(done)})
                continue
            art.source = self.name  # 归入语雀精选来源
            if not art.date:
                art.date = ""
            yield art
        save_progress("yuque", {"done": sorted(done)})

    def after_save(self, art: Article, saved: bool):
        done = set(load_progress("yuque").get("done", []))
        done.add(art.source_url)
        save_progress("yuque", {"done": sorted(done)})
