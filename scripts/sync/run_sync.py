#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""同步入口：按顺序跑各源适配器（互不阻塞），最后重建索引与目录页。

用法：
  uv run python scripts/sync/run_sync.py [--sources yanshen,zhbyg] [--limit 800]

环境变量：
  SYNC_RATE              每次请求最小间隔秒数（默认 1.0，对源站友好）
  SYNC_ENABLE_YUQUE      1 启用语雀盐选库（实验性，默认关）
  GITHUB_STEP_SUMMARY    存在时写入 Actions Summary
"""
import argparse
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from base import finalize  # noqa: E402
from sources.yanshen import YanshenAdapter  # noqa: E402
from sources.zhbyg import ZhbygAdapter  # noqa: E402
from sources.yanxuanwk import YanxuanwkAdapter  # noqa: E402
from sources.yuque import YuqueAdapter  # noqa: E402

ADAPTERS = {
    "yanshen": YanshenAdapter,
    "zhbyg": ZhbygAdapter,
    "yanxuanwk": YanxuanwkAdapter,
    "yuque": YuqueAdapter,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", default="all",
                    help="逗号分隔的源 key，或 all")
    ap.add_argument("--limit", type=int,
                    default=int(os.environ.get("SYNC_LIMIT", "0")),
                    help="每个源本次最多抓取篇数（0=不限）")
    ap.add_argument("--no-finalize", action="store_true",
                    help="跳过结尾的索引/目录重建（供分批追平时避免与 CI 冲突）")
    args = ap.parse_args()

    selected = (list(ADAPTERS) if args.sources == "all"
                else [s.strip() for s in args.sources.split(",") if s.strip()])
    summary = []
    for key in selected:
        cls = ADAPTERS.get(key)
        if cls is None:
            summary.append({"source": key, "status": "未知来源", "written": 0,
                            "skipped": 0, "failed": 0})
            continue
        print(f"▶ 同步 {cls.name} …")
        try:
            summary.append(cls(limit=args.limit).process())
        except Exception:
            traceback.print_exc()
            summary.append({"source": cls.name, "status": "异常中断",
                            "written": 0, "skipped": 0, "failed": 0})

    if args.no_finalize:
        # 分批追平模式：CI 可能同时在重建索引/目录，本地不写避免冲突
        text = "\n".join(f"| {r['source']} | {r['status']} | {r['written']} "
                         f"| {r['skipped']} | {r['failed']} |" for r in summary)
        text = "## 同步结果（索引/目录未重建，--no-finalize）\n\n" + text
    else:
        text = finalize(summary)
    print("\n" + text)
    gp = os.environ.get("GITHUB_STEP_SUMMARY")
    if gp:
        # GITHUB_STEP_SUMMARY 为 Actions 挂载的空文件，单次覆盖写入即可
        Path(gp).write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
