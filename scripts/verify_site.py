#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""站点产物校验：构建后全量扫描 HTML 完整性，防 Hugo 渲染竞态漏网。

Hugo（0.154/0.168 均复现）在并发渲染时偶发把个别页面的页尾块
重复输出（多出一个 </html>）或写入坏字节，每次构建受影响页面随机。
CI/本地构建须循环「hugo → 本脚本校验」直到通过（见 deploy.yml）。

用法：python3 scripts/verify_site.py <站点输出目录>
     全部通过 exit 0 并打印统计；发现损坏打印清单 exit 1。
"""
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    root = Path(sys.argv[1])
    if not root.is_dir():
        print(f"目录不存在: {root}", file=sys.stderr)
        return 2

    total = 0
    bad: list[str] = []
    for p in root.rglob("*.html"):
        if "pagefind" in p.parts:
            continue
        total += 1
        raw = p.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            bad.append(f"UTF-8 坏字节 @{exc.start}: {p.relative_to(root)}")
            continue
        if text.count("</html>") != 1:
            bad.append(f"</html> 异常（{text.count('</html>')} 处）: {p.relative_to(root)}")

    if bad:
        print(f"✗ 损坏页面 {len(bad)} / {total}：", file=sys.stderr)
        for line in bad[:20]:
            print(f"  {line}", file=sys.stderr)
        if len(bad) > 20:
            print(f"  …共 {len(bad)} 处", file=sys.stderr)
        return 1
    print(f"✓ 校验通过：{total} 个 HTML 页面完整")
    return 0


if __name__ == "__main__":
    sys.exit(main())
