# zh-report-humanizer

一个用于 [Claude Code](https://claude.com/claude-code) / Claude Agent Skills 的技能包，帮助撰写或修改**中文技术 / 学术报告**（课程作业、实验报告、分析报告、课程设计）时去掉"AI 味"，覆盖正文和图表。

核心主张：**报告里的人味来自具体性和真实过程，不来自文风。** 因此它同时反对两类错误改法：

- **AI 腔**：「综上所述」「赋能」「高效、稳定、可靠」三连排比、意义拔高。
- **刻意风格化**：加金句、制造节奏、硬塞口语词、同义词轮换骗检测器。

A Claude skill for de-AI-ifying Chinese technical/academic reports. It favors concrete details (numbers, filenames, commands, error output) and real troubleshooting process over stylistic tricks, and ships with a Python self-check script.

## 内容

```text
zh-report-humanizer/
├── SKILL.md                     # 技能主文件：硬规则、语体基线、负向词表、改写手法、图表与排版
├── references/
│   ├── ai-tells-zh.md           # AI 写作特征完整清单（内容层 / 语言层 / 结构层 / 图表层）
│   ├── figures-zh.md            # 图表规范与 Mermaid / PlantUML / Graphviz / matplotlib / draw.io 黑白预设
│   └── rewrite-examples.md      # 12 组改写范例
├── scripts/
│   └── check_report.py          # 自检脚本（纯标准库，Python 3.8+）
└── examples/
    └── bad-sample.md            # 用来试跑自检脚本的反例
```

## 四条硬规则

1. 禁止「不是…而是…」这类否定再肯定句式，一句话只留否定或只留肯定。
2. 正文陈述过程不用箭头 `A → B → C`，改用关联词或顿号（代码块豁免）。
3. 全文如非必要不用破折号「——」。
4. 正文和图里不用 emoji 与装饰符号。

## 安装

把整个目录放到 Claude Code 的 skills 目录下：

```bash
# 个人级（所有项目可用）
git clone https://github.com/<your-name>/zh-report-humanizer ~/.claude/skills/zh-report-humanizer

# 项目级（只对当前仓库生效）
git clone https://github.com/<your-name>/zh-report-humanizer .claude/skills/zh-report-humanizer
```

Windows 下个人级目录是 `%USERPROFILE%\.claude\skills\`。

安装后，在对话里说「帮我去掉这篇报告的 AI 味」「报告润色」「图太花了」等，Claude 会自动加载这个技能。

## 单独使用自检脚本

脚本不依赖第三方库，可以脱离 Claude 单独用：

```bash
python scripts/check_report.py report.md
python scripts/check_report.py examples/bad-sample.md
```

输出包括四条硬规则命中、禁用词、套话、图表与画图代码检查、中英文混排和半角标点、人称混用、流水句候选、句长变异系数等。**硬规则有命中时退出码为 1**，可以放进 pre-commit 或 CI。

## 适用范围与局限

- 面向正式书面报告，不适合公众号、博客、小说等需要文风的文体。
- 规则检查基于正则，会有误报和漏报；脚本输出是候选清单，最终以人工判断为准。
- 这个技能的目标是把报告写清楚、写具体，**不是**用来规避 AIGC 检测或学术诚信审查。没做过的实验、没踩过的坑不要编，参考文献必须逐条核实。

## 参考

- Wikipedia: [Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing)
- GB/T 7713、GB/T 7714-2015

## 许可证

[MIT](LICENSE)。欢迎提 Issue / PR 补充词表、误报样例和改写范例。
