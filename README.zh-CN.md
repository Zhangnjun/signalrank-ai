# SignalRank AI

SignalRank AI 是一个面向 AI 行业的信息监控与排序工具。

它会读取一份简历或 CV，然后抓取 AI 新闻、实验室公告、工程博客和论文动态，并从以下几个维度对内容进行排序：

- 与简历方向的相关性
- 行业影响力
- 内容质量
- 发现价值

它的目标不是做一个泛化新闻爬虫，而是从大量 AI 信息里筛出两类真正值得关注的内容：

- 和个人背景高度匹配的内容
- 即使不完全匹配，但对整个 AI 行业非常重要的内容

这套机制适合工程师、研究者、求职者和技术团队做定向情报跟踪，而不是被普通资讯流淹没。

## 项目价值

很多 AI 热点监控方案的问题很明显：

- 依赖手写关键词，迁移性差
- 抓很多内容，但噪音、标题党和弱技术内容太多

SignalRank AI 的思路不同：

- 先从 CV 中抽取画像，而不是依赖固定关键词表
- 对每条内容做多维评分，而不是只看一个分数
- 支持“两段式 AI 重排”：先本地召回，再用 AI 精筛

## 功能特性

- 支持 `txt`、`md`、`pdf`、`docx` 简历输入
- 支持 `rss`、`atom`、`json_feed` 配置化信源
- 自动抓取正文并清洗 HTML
- 支持 URL 级去重与主题级聚合
- 本地评分包括：
  - `relevance_score`
  - `impact_score`
  - `quality_score`
  - `discovery_score`
  - `final_score`
- 可选 OpenAI 增强：
  - embedding 语义重排
  - LLM 结构化最终判定
- 输出 Markdown 和 JSON，方便人工查看和后续自动化处理

## 目录结构

```text
signalrank-ai/
├── .gitignore
├── README.md
├── README.zh-CN.md
├── pyproject.toml
├── sources.example.json
├── sources.curated.json
├── sources.premium.example.json
└── src/ai_hotspot_monitor
    ├── cli.py
    ├── config.py
    ├── fetcher.py
    ├── models.py
    ├── pipeline.py
    ├── resume.py
    └── scoring.py
```

## 快速开始

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp sources.curated.json sources.json
```

本地模式运行：

```bash
ai-hotspot-monitor \
  --resume ./path/to/resume.md \
  --sources ./sources.json
```

开启 AI 重排：

```bash
export OPENAI_API_KEY="your_key"

ai-hotspot-monitor \
  --resume ./path/to/resume.md \
  --sources ./sources.json \
  --ai-evaluate \
  --embedding-model text-embedding-3-small \
  --ai-candidate-pool 20 \
  --ai-top-k 8 \
  --ai-model gpt-5-mini
```

## 信源配置

仓库中提供三套配置文件：

- `sources.example.json`
  最小可用示例。
- `sources.curated.json`
  可直接运行的公开信源组合，优先选择已验证可访问的官方 feed。
- `sources.premium.example.json`
  premium 或受限信源的占位模板，比如 The Information、Semafor 等，默认禁用。

后续扩展更多站点时，一般只需要改配置文件，不需要改主流程代码。

## 输出结果

默认输出到 `./reports`：

- `ai_hotspots_<timestamp>.json`
- `ai_hotspots_<timestamp>.md`

每条记录通常包含：

- 标题、来源、发布时间、URL
- 自动摘要
- 命中的简历术语
- 本地评分
- 最终评分
- 可选 embedding 分
- 保留决策与保留原因
- 是否属于行业级重磅事件

## 工作原理

### 1. 简历画像

系统会先把简历归一化，并抽取：

- 标准化后的文本
- 高权重术语
- 一个简短的方向摘要

这样就能针对不同 CV 自适应，而不是依赖固定关键词列表。

### 2. 抓取与清洗

系统会读取配置中的 feed，抓取条目并尝试抽取正文。
如果页面出现 `403`、`404` 或 HTML 质量较差，会自动降级，不会让整批任务失败。

### 3. 去重与主题聚合

系统会对重复 URL 去重，并对相似标题做主题聚类，避免同一个热点被重复放大。

### 4. 本地评分

每条内容会被打多个分：

- `relevance_score`
  判断与 CV 的相关性，来源于 TF-IDF 字符特征、术语重叠和标题对齐。
- `impact_score`
  结合信源权重、发布时间、主题共振和内容深度。
- `quality_score`
  压制标题党、浅层内容和低信息密度文本。
- `discovery_score`
  用来保留“虽然不完全匹配 CV，但值得关注”的发现型内容。

### 5. 保留策略

一条内容可以因为以下原因被保留：

- 与 CV 高相关
- 是行业级重磅事件
- 虽然不是完全命中，但影响力和质量都比较高，属于 discovery 候选

这比“只按相关性硬过滤”更适合做热点跟踪。

### 6. 可选 AI 重排

开启 `--ai-evaluate` 后，流程会变成：

1. 本地评分做宽召回
2. 用 embedding 对候选做语义重排
3. 再把前一部分候选交给 LLM 做结构化最终判断

这比下面两种方式都更实用：

- 只靠本地规则
- 所有内容都直接丢给 LLM

## 常用参数

- `--resume`
  简历文件路径
- `--sources`
  信源配置文件
- `--per-source-limit`
  每个信源抓取多少条
- `--top-n`
  最终保留多少条结果
- `--min-relevance`
  高相关保留阈值
- `--min-quality`
  内容质量阈值
- `--heavyweight-impact`
  行业重磅事件阈值
- `--ai-evaluate`
  是否开启 AI 重排
- `--ai-candidate-pool`
  embedding 阶段处理多少个候选
- `--ai-top-k`
  LLM 最终处理多少条

## 适用场景

- 跟踪与某个工程背景相关的 AI 行业变化
- 生成 AI 热点日报或周报
- 监控前沿实验室和平台厂商动态
- 从大范围研究与媒体流中筛出工程上真正有价值的内容
- 用于求职、研究、技术情报和竞品观察

## 公开仓库注意事项

建议不要提交以下本地文件：

- 私有的 `sources.json`
- 本地运行生成的报告
- 个人简历
- 带 Cookie 或认证信息的配置

仓库中的 `.gitignore` 已经排除了常见本地运行产物。
