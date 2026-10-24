#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""语雀「知乎盐选库」适配器（yuque.com/dayuyu-ualcu/azo1ge，访问密码 rydw）。

实验性：语雀带密码的分享文档需解锁会话且正文为 lake 格式，
默认关闭；SYNC_ENABLE_YUQUE=1 时启用，一次性导入高质量精选（已停更）。
"""
import os

from base import SourceAdapter, polite_get

DOC_URL = "https://www.yuque.com/dayuyu-ualcu/azo1ge"
DOC_PASSWORD = "rydw"


class YuqueAdapter(SourceAdapter):
    name = "语雀盐选库"
    enabled = os.environ.get("SYNC_ENABLE_YUQUE", "0") == "1"

    def health(self) -> bool:
        if not self.enabled:
            print(f"  [{self.name}] 未启用（SYNC_ENABLE_YUQUE!=1）")
            return False
        try:
            r = polite_get(self.sess, DOC_URL, timeout=20)
            if r.status_code == 200:
                return True
            print(f"  [{self.name}] 健康检查失败: HTTP {r.status_code}")
            return False
        except Exception as exc:
            print(f"  [{self.name}] 健康检查失败（已跳过）: {exc}")
            return False

    def fetch_new(self):
        # TODO: 解析分享页 appData JSON → 解锁密码 → 遍历文档内文章链接，
        # 指向 onehu/zhbyg 的复用对应适配器抓正文；指向知乎站内的跳过并记录。
        print(f"  [{self.name}] 适配器尚未实现语雀解锁流程，本轮跳过")
        return iter([])
