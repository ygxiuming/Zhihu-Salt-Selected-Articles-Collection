#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""站点产物校验：构建后全量扫描 HTML 完整性，防 Hugo 落盘竞态漏网。

Hugo（0.154/0.168 均复现）直写磁盘时偶发把个别页面的页尾块重复输出
（多出一个 </html>）或写入坏字节，每次构建受影响页面随机（~0.05%）。
CI/本地构建须配合 repair_site.py 做「跨构建交叉修复」（见 deploy.yml）。

用法：python3 scripts/verify_site.py <站点输出目录>
     全部通过 exit 0 并打印统计；发现损坏打印清单 exit 1。
"""
import sys
from pathlib import Path


def is_bad_page(path: Path) -> str | None:
    """返回损坏描述；页面完好则返回 None。"""
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return f"UTF-8 坏字节 @{exc.start}"
    n = text.count("</html>")
    if n != 1:
        return f"</html> 异常（{n} 处）"
    return None


def find_bad(root: Path) -> list[tuple[Path, str]]:
    """扫描目录下全部 HTML（跳过 pagefind），返回 [(路径, 损坏描述)]。"""
    out: list[tuple[Path, str]] = []
    for p in sorted(root.rglob("*.html")):
        if "pagefind" in p.parts:
            continue
        why = is_bad_page(p)
        if why:
            out.append((p, why))
    return out


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    root = Path(sys.argv[1])
    if not root.is_dir():
        print(f"目录不存在: {root}", file=sys.stderr)
        return 2

    pages = [p for p in root.rglob("*.html") if "pagefind" not in p.parts]
    bad = find_bad(root)
    if bad:
        print(f"✗ 损坏页面 {len(bad)} / {len(pages)}：", file=sys.stderr)
        for p, why in bad[:20]:
            print(f"  {why}: {p.relative_to(root)}", file=sys.stderr)
        if len(bad) > 20:
            print(f"  …共 {len(bad)} 处", file=sys.stderr)
        return 1
    print(f"✓ 校验通过：{len(pages)} 个 HTML 页面完整")
    return 0


if __name__ == "__main__":
    sys.exit(main())
