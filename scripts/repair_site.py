#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""坏页修复：跨构建交叉修复优先，尾部重复坏页做字节层截断恢复。

Hugo 直写磁盘的竞态（0.154/0.168 均复现）有两种观测形态，均只发生在
页尾：「页尾附加重复尾块」（多出一个 </html>）与「尾块首字节损坏」。
因此：

1. cross_fix —— 捐赠构建中同一页完好则整体拷贝（内容 100% 一致）；
2. truncate_fix —— 无捐赠可用时，截断到第一个 </html>。
   正常页面的第一个 </html> 就是文件结尾（正文里的该字符串会被
   Goldmark 转义为 &lt;/html&gt;，不可能冲突），截掉的只是附加尾块；
   附带双重保护：截掉部分必须小于 2KB，且修复结果须通过完整性校验。

用法：python3 scripts/repair_site.py <主构建目录> [捐赠构建目录]
     全部修复 exit 0；仍有坏页 exit 1。
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_site import find_bad, is_bad_page  # noqa: E402

TAIL_LIMIT = 2048  # 截掉的附加尾块超过此值视为未知损坏模式，放弃截断


def truncate_fix(page: Path) -> bool:
    """截掉第一个 </html> 之后的附加尾块，成功返回 True。"""
    raw = page.read_bytes()
    marker = raw.find(b"</html>")
    if marker < 0:
        return False
    head = raw[: marker + len(b"</html>")] + b"\n"
    cut = len(raw) - len(head)
    if cut > TAIL_LIMIT or cut <= 0:
        return False
    page.write_bytes(head)
    return is_bad_page(page) is None


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(__doc__, file=sys.stderr)
        return 2
    base = Path(sys.argv[1])
    donor = Path(sys.argv[2]) if len(sys.argv) == 3 else None
    if not base.is_dir():
        print(f"目录不存在: {base}", file=sys.stderr)
        return 2
    if donor is not None and not donor.is_dir():
        donor = None

    bad = find_bad(base)
    if not bad:
        print("✓ 主构建已全部完整")
        return 0

    fixed_copy = fixed_trunc = 0
    for p, _why in bad:
        q = donor / p.relative_to(base) if donor else None
        if q is not None and q.is_file() and is_bad_page(q) is None:
            shutil.copy2(q, p)
            fixed_copy += 1
        elif truncate_fix(p):
            fixed_trunc += 1
        else:
            print(f"  无法修复：{p.relative_to(base)}", file=sys.stderr)
    print(f"修复 {len(bad)} 页（交叉拷贝 {fixed_copy}，截断恢复 {fixed_trunc}）")

    rest = find_bad(base)
    if rest:
        print(f"✗ 仍有 {len(rest)} 页损坏", file=sys.stderr)
        return 1
    print("✓ 主构建已全部完整")
    return 0


if __name__ == "__main__":
    sys.exit(main())
