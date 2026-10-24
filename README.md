# 知乎盐选文章收藏 · 在线阅读

[![部署站点](https://github.com/ygxiuming/Zhihu-Salt-Selected-Articles-Collection/actions/workflows/deploy.yml/badge.svg)](https://github.com/ygxiuming/Zhihu-Salt-Selected-Articles-Collection/actions/workflows/deploy.yml)
[![定时同步](https://github.com/ygxiuming/Zhihu-Salt-Selected-Articles-Collection/actions/workflows/sync.yml/badge.svg)](https://github.com/ygxiuming/Zhihu-Salt-Selected-Articles-Collection/actions/workflows/sync.yml)

> 📖 **[点击这里在线阅读（支持全文搜索 / 夜间模式 / 字号调节）](https://ygxiuming.github.io/Zhihu-Salt-Selected-Articles-Collection/)**

知乎盐选文章收集，文章来源于知乎搬运工和我不是盐神。

由于该死的抖音老是推送，让我有时候想看盐选文章，但是又不甘心花这个钱。
所以一般都是从知乎盐选搬运工和我不是盐神的网站上进行观看的，在这感谢大佬的付出。

可能是由于网站的不稳定，有时候访问不了，所以创建该仓库收藏大佬网站上的文章。仅供个人收藏，解解书瘾。如有其他意见，可联系本人，将会把该仓库转为私有。

## 数据源

| 来源 | 状态 | 收录 | 说明 |
|---|---|---|---|
| [我不是盐神](https://onehu.xyz/) | ✅ 活跃更新 | 8300+ 篇（源站全量） | 每日定时增量同步 |
| [知乎搬运工](https://www.zhbyg.top/) | ⚠️ 常失联 | 7000+ 篇（存量） | 源站可达时自动恢复同步 |
| 盐选文库（yanxuanwk.com） | 🧪 实验性 | 待接入 | 适配器已内置，默认关闭 |
| 语雀「知乎盐选库」 | 🧪 实验性 | 待导入 | 适配器已内置，默认关闭 |

## 如何阅读

**方式一：在线站点（推荐）** —— 打开[在线阅读站](https://ygxiuming.github.io/Zhihu-Salt-Selected-Articles-Collection/)，
首页搜索框支持中文全文搜索（标题 + 正文开头），文章页可调字号、切换夜间模式。

**方式二：GitHub 内浏览** —— 从 [目录.md](./目录.md) 进入各源目录，
按拼音首字母分组浏览（如 [我不是盐神/目录-README.md](./我不是盐神/目录-README.md)），
所有内链由脚本生成并经校验（0 死链），点击标题直达 Markdown 原文。

**方式三：全量下载** —— [Releases](https://github.com/ygxiuming/Zhihu-Salt-Selected-Articles-Collection/releases)
每月 1 号自动发布全量 ZIP 快照，无需克隆仓库。

## 仓库结构

```
├── 我不是盐神/          # 文章（front matter 元数据 + 规范正文）
│   └── 目录-*.md        # 按拼音首字母分组的浏览目录（脚本生成）
├── 知乎搬运工/          # 同上
├── 目录.md              # 总目录入口（脚本生成）
├── data/
│   ├── articles_index.json   # 全库元数据索引（同步去重 / 目录生成）
│   └── progress/             # 各源断点进度（增量同步）
├── scripts/             # 迁移 / 校验 / 同步工具（Python）
│   ├── cleanlib.py      #   清洗与规范化共享库
│   ├── catalog.py       #   目录与索引生成（迁移、同步共用）
│   ├── validate.py      #   仓库校验（内链 / 文件名 / 元数据）
│   ├── migrate.py       #   一次性深度清洗迁移（已执行）
│   └── sync/            #   定时同步框架 + 各源适配器
├── hugo.toml            # 静态站配置（模块挂载文章目录）
├── layouts/ static/     # 站点模板与样式（夜间模式 / 字号 / Pagefind UI）
└── .github/workflows/   # 同步 / 部署 / 快照 三个工作流
```

## 自动化

- **每日 02:00 UTC（北京 10:00）定时同步**：各源独立执行、互不阻塞；
  断点续抓 + 跨源标题去重 + 限速 1 req/s 对源站友好；
  有新增才提交（`sync: 增量同步`）并自动重新构建部署站点。
  公共仓库定时任务 60 天无活动会被 GitHub 禁用，已用 keepalive 空提交保活。
- **每月 1 号全量快照**：打包 ZIP 发布到 Releases（单文件限额 2GB）；自上次快照以来无文章更新时自动跳过。
- 手动触发：Actions 页面可指定 `sources` 与单次抓取上限 `limit`。

## 本地开发

```bash
# 文章校验
uv venv && uv pip install -r scripts/requirements.txt
uv run python scripts/validate.py

# 手动同步（默认限 800 篇/源，0 为不限）
uv run python scripts/sync/run_sync.py --sources yanshen --limit 50

# 本地建站（需 hugo extended ≥0.154 与 node）
hugo --minify --gc && npx -y pagefind@1.5.2 --site public
hugo server -D   # 开发预览
```

搜索索引为控制体积只收录标题与正文开头 1500 字（与源站搜索行为一致）；
全部限制与扩容路径见 [docs/存储与扩容预案.md](./docs/存储与扩容预案.md)。

## 免责声明

本仓库及站点内容均收集自公开网络（知乎盐选专栏的第三方搬运站），
仅供个人收藏学习，不提供任何下载牟利渠道，版权归原作者与知乎所有。
如有侵权请联系，将立即转私有或删除。
