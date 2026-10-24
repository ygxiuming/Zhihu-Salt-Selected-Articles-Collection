#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨构建交叉修复：用「捐赠构建」里的完好页面覆盖「主构建」的坏页。

Hugo 落盘竞态导致每次构建随机 ~0.05% 页面损坏，同一页在两次独立构建
中同时损坏的概率趋近于零，因此两份构建交叉后必然（概率意义上）完整。

用法：python3 scripts/repair_site.py <主构建目录> <捐赠构建目录>
     打印修复统计；主构建剩余坏页数非零时 exit 1（调用方再取下一份捐赠）。
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_site import find_bad, is_bad_page  # noqa: E402


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    base, donor = Path(sys.argv[1]), Path(sys.argv[2])
    for d in (base, donor):
        if not d.is_dir():
            print(f"目录不存在: {d}", file=sys.stderr)
            return 2

    bad = find_bad(base)
    fixed = skipped = 0
    for p, why in bad:
        q = donor / p.relative_to(base)
        if q.is_file() and is_bad_page(q) is None:
            shutil.copy2(q, p)
            fixed += 1
        else:
            skipped += 1
            print(f"  捐赠构建中同样损坏，留待下一轮：{p.relative_to(base)}",
                  file=sys.stderr)
    print(f"修复 {fixed} 页（捐赠侧同样损坏 {skipped} 页）")

    rest = find_bad(base)
    if rest:
        print(f"✗ 仍有 {len(rest)} 页损坏", file=sys.stderr)
        return 1
    print("✓ 主构建已全部完整")
    return 0


if __name__ == "__main__":
    sys.exit(main())
