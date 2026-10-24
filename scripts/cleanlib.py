#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文章清洗共享库：解析旧模板、清洗正文、文件名规范化、拼音首字母、front matter 生成。

被 scripts/migrate.py（一次性迁移）与 scripts/sync/（增量同步）共同复用，
保证新旧文章最终落盘格式完全一致。
"""
import json
import re
import unicodedata

# ---------------------------------------------------------------- 常量与正则

# 源站反爬水印，直接粘连在正文后：备案号:YX11ArJYRwx
WATERMARK_RE = re.compile(r"备案号[:：]\s*YX[0-9A-Za-z]+")
# HTML 缩进/空白实体
ENTITY_RE = re.compile(r"&emsp;|&ensp;|&nbsp;|&#8194;|&#8195;|&#160;")
# 裸 HTML 标签（仅当行内出现明显标签特征时才做剥离）
HTML_TAG_RE = re.compile(r"</?[A-Za-z][^>]{0,160}>")
# 行内疑似 HTML 结构特征
HTML_HINT_RE = re.compile(r"class=|<div|<span|<p[ >]|<a |<br", re.I)
# 零宽字符（源站排版残留）
ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")
SOURCES = ("我不是盐神", "知乎搬运工", "盐选文库", "语雀盐选库")


def normalize_filename(stem: str) -> str:
    """文件名（不含 .md）规范化：Windows 兼容 + 去尾随空格 + 压缩连续空格。

    半角括号转全角：括号在 markdown 链接目的地里会截断链接，
    中文语境下全角括号也更符合排版习惯。
    换行/制表符折叠为单个空格：NTFS 文件名禁止换行，且会破坏
    shell 工具的逐行输出（语雀文档标题常自带换行）。
    """
    stem = unicodedata.normalize("NFC", stem)
    for ch in '\\/:*?"<>|\n\r\t':
        stem = stem.replace(ch, " ")
    stem = stem.replace("(", "（").replace(")", "）")
    stem = re.sub(r"\s{2,}", " ", stem).strip().rstrip(".")
    return stem


def escape_link_text(title: str) -> str:
    """目录页链接文字转义：方括号会破坏 [text](dest) 结构。"""
    return title.replace("[", "［").replace("]", "］")


def norm_title(title: str) -> str:
    """标题归一化指纹（跨源去重用）：NFKC 折叠全半角后去除所有空白与标点。"""
    t = unicodedata.normalize("NFKC", title)
    return re.sub(r"[\W_]+", "", t, flags=re.UNICODE).lower()


# ---------------------------------------------------------------- 拼音首字母

# GB2312 一级汉字（区 16-55）按拼音排序，用码位边界映射首字母；生僻字回退 '#'
_GB_RANGES = (
    (0xB0A1, "A"), (0xB0C5, "B"), (0xB2C1, "C"), (0xB4EE, "D"), (0xB6EA, "E"),
    (0xB7A2, "F"), (0xB8C1, "G"), (0xB9FE, "H"), (0xBBF7, "J"), (0xBFA6, "K"),
    (0xC0AC, "L"), (0xC2E8, "M"), (0xC4C3, "N"), (0xC5B6, "O"), (0xC5BE, "P"),
    (0xC6DA, "Q"), (0xC8BB, "R"), (0xC8F6, "S"), (0xCBFA, "T"), (0xCDDA, "W"),
    (0xCEF4, "X"), (0xD1B9, "Y"), (0xD4D1, "Z"),
)


def pinyin_initial(text: str) -> str:
    """取标题首字符的拼音首字母（优先 pypinyin，缺失时回退 GB2312 码表）。"""
    if not text:
        return "#"
    ch = text[0]
    try:
        from pypinyin import lazy_pinyin  # type: ignore

        py = lazy_pinyin(ch)[0]
        if py and py[0].isascii() and py[0].isalpha():
            return py[0].upper()
    except Exception:
        pass
    if ch.isascii():
        if ch.isalpha():
            return ch.upper()
        if ch.isdigit():
            return "0"
        return "#"
    try:
        b = ch.encode("gb2312")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return "#"
    code = (b[0] << 8) | b[1]
    if not (0xB0A1 <= code <= 0xD7D9):
        return "#"
    letter = "#"
    for start, L in _GB_RANGES:
        if code >= start:
            letter = L
    return letter


# ---------------------------------------------------------------- 句子切分

# 长段落按句号/问号/叹号/省略号切分为短段落（盐选阅读风格：一句一段）
_SENT_RE = re.compile(r"[^。！？]*?[。！？]+[」』”’\"』]*|[^。！？]*?……[」』”’\"」]*|[^。！？……]+$")


def sentence_split(text: str) -> list:
    out = []
    for m in _SENT_RE.finditer(text):
        s = m.group(0).strip()
        if s:
            out.append(s)
    return out or [text]


# ---------------------------------------------------------------- 旧模板解析

_URL_MD_RE = re.compile(r"\[原文地址\]\((https?://[^)\s]+)\)")
_FOOTER_URL_RE = re.compile(r"本文搬运来自[：:]\s*(https?://\S+)")
_COLUMN_RE = re.compile(r"出自专栏[:：]\s*《(.+?)》")
_SUBTITLE_RE = re.compile(r"##\s*(.+?)\s*$")


def parse_article(text: str, source: str, fallback_title: str) -> dict:
    """解析文章，返回 title / source_url / column / 原始行列表。

    支持两种输入：
    - 已清洗格式（YAML front matter 开头）：直接取元数据，正文为其余行；
    - 旧爬虫模板（盐神 / 搬运工两种）：按模板特征解析。
    """
    lines = text.split("\n")
    title, url, column = None, None, None
    if lines and lines[0].strip() == "---":
        for i, raw in enumerate(lines[1:], start=1):
            s = raw.strip()
            if s == "---":
                body_start = i + 1
                break
            m = re.match(r"([A-Za-z_]+):\s*(.+)$", s)
            if m:
                key, val = m.group(1), m.group(2).strip()
                if val.startswith('"') and val.endswith('"'):
                    try:
                        val = json.loads(val)
                    except ValueError:
                        pass
                if key == "title":
                    title = val
                elif key == "source_url":
                    url = val
                elif key == "column":
                    column = val
        else:
            body_start = len(lines)
        return {"title": title or fallback_title, "source_url": url,
                "column": column, "body_lines": lines[body_start:]}

    body_start = 1
    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip().rstrip()
    else:
        title, body_start = fallback_title, 0
    # 头部 5 行内找 原文链接 与 专栏/副标题 行
    for i, raw in enumerate(lines[:5]):
        s = raw.strip()
        m = _URL_MD_RE.match(s)
        if m:
            url = m.group(1)
            body_start = max(body_start, i + 1)
            continue
        m = _SUBTITLE_RE.match(s)
        if m and i >= 1 and column is None:
            cm = _COLUMN_RE.match(m.group(1))
            if cm:
                column = cm.group(1)
                body_start = max(body_start, i + 1)
            # 不含「出自专栏」的 ## 行是爬虫残留碎片，直接跳过不收录
            else:
                body_start = max(body_start, i + 1)
    if url is None:
        m = _FOOTER_URL_RE.search(text)
        if m:
            url = m.group(1).strip()
    if title is None:
        title = fallback_title
    return {"title": title, "source_url": url, "column": column,
            "body_lines": lines[body_start:] if body_start < len(lines) else []}


# ---------------------------------------------------------------- 正文清洗

_DROP_PREFIXES = ("[原文地址]", "本文搬运来自", "收藏于", "备案号")
_JUNK_LINE_RE = re.compile(r"^[\s.。、·,，×✕]*$")


def clean_paragraphs(body_lines, source: str) -> list:
    """逐行清洗并重组为段落列表。"""
    paras = []
    for raw in body_lines:
        ln = ZERO_WIDTH_RE.sub("", raw)
        ln = ln.replace("\u00a0", " ")
        ln = ENTITY_RE.sub("", ln)
        ln = WATERMARK_RE.sub("", ln)
        s = ln.strip()
        if not s:
            continue
        if s.lower().startswith("<br"):
            continue
        if any(s.startswith(p) for p in _DROP_PREFIXES):
            continue
        # 盐神模板中的分页符独立成行（"1"），整行丢弃
        if source == "我不是盐神" and re.fullmatch(r"\d{1,3}", s):
            continue
        if _JUNK_LINE_RE.match(s):
            continue
        if HTML_HINT_RE.search(s):
            s = HTML_TAG_RE.sub("", s).strip()
            if not s:
                continue
        if s.startswith("#"):
            continue
        if len(s) > 140:
            paras.extend(sentence_split(s))
        else:
            paras.append(s)
    # 相邻重复段落去重（源站重复推送段落）
    deduped = []
    for p in paras:
        if not deduped or deduped[-1] != p:
            deduped.append(p)
    return deduped


def build_markdown(meta: dict, paras: list) -> str:
    """统一落盘格式：YAML front matter + 空行分隔段落。"""
    fm = ["---"]
    for key in ("title", "source", "source_url", "column", "date"):
        val = meta.get(key)
        if val:
            fm.append(f"{key}: {json.dumps(str(val), ensure_ascii=False)}")
    fm.append("---")
    body = "\n\n".join(paras)
    return "\n".join(fm) + "\n\n" + body + "\n"


def preview_of(paras: list, limit: int = 80) -> str:
    text = paras[0] if paras else ""
    return text[:limit] + ("…" if len(text) > limit else "")


# ---------------------------------------------------------------- 语雀 markdown 清洗

# markdown 图片（本库无图惯例，整行丢弃）
_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)|<img[^>]*>", re.I)
# markdown 链接保留文字丢弃目标
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
# 行内 HTML 标签（font/span 等）
_INLINE_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")
# HTML 实体
_ENTITY_DEC_RE = re.compile(r"&#(\d+);")
_MD_HEADING_RE = re.compile(r"^#{1,6}\s+")


def clean_markdown_source(md: str) -> list:
    """清洗语雀导出的 markdown 正文为段落列表。"""
    out = []
    for raw in md.split("\n"):
        ln = _MD_IMAGE_RE.sub("", raw)
        ln = _MD_LINK_RE.sub(r"\1", ln)
        ln = _INLINE_TAG_RE.sub("", ln)
        ln = _ENTITY_DEC_RE.sub(lambda m: chr(int(m.group(1))), ln)
        ln = ZERO_WIDTH_RE.sub("", ln)
        s = ln.strip()
        if not s:
            continue
        s = _MD_HEADING_RE.sub("", s).strip()
        s = WATERMARK_RE.sub("", s)
        if not s or _JUNK_LINE_RE.match(s):
            continue
        out.append(s)
    return out
