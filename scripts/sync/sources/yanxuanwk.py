#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「盐选文库」适配器（yanxuanwk.com，号称收录 34000+ 篇）。

实验性：站点结构未完全确认且部分地区网络不可达，
默认关闭；SYNC_ENABLE_YANXUANWK=1 时启用。
启用后先做健康检查，不可达自动跳过，不影响其他源。
"""
import os

from base import SourceAdapter, polite_get


class YanxuanwkAdapter(SourceAdapter):
    name = "盐选文库"
    BASE = "https://www.yanxuanwk.com"
    enabled = os.environ.get("SYNC_ENABLE_YANXUANWK", "0") == "1"

    def health(self) -> bool:
        if not self.enabled:
            print(f"  [{self.name}] 未启用（SYNC_ENABLE_YANXUANWK!=1）")
            return False
        try:
            r = polite_get(self.sess, self.BASE, timeout=15)
            if r.status_code == 200:
                return True
            print(f"  [{self.name}] 健康检查失败: HTTP {r.status_code}")
            return False
        except Exception as exc:
            print(f"  [{self.name}] 健康检查失败（站点不可达，已跳过）: {exc}")
            return False

    def fetch_new(self):
        # TODO: 确认站点列表/正文结构后实现，参考 yanshen.py 的模式：
        # 1. 列表分页扫描至断点  2. 逐篇抓取并 clean_paragraphs 清洗
        # 3. after_save 推进断点
        print(f"  [{self.name}] 适配器尚未实现站点结构解析，本轮跳过")
        return iter([])
