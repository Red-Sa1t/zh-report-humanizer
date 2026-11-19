#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中文报告「AI味」自检脚本。

用法:
    python check_report.py <报告.md> [报告2.md ...]

输出以下信号:
    1. 禁用词命中（含行号与上下文）
    2. 否定再肯定句式（硬规则一，必须为 0）
    3. 箭头符号（硬规则二，必须为 0，代码块与行内代码除外）
    4. 破折号「——」（硬规则三，目标为 0）
    5. emoji 与装饰符号（硬规则四，目标为 0）
    6. 图表与画图代码（图题、正文引用、Mermaid / PlantUML / Graphviz / matplotlib 配置）
    7. 排版一致性：中英文混排空格、中文里的半角标点、人称混用、参考文献提醒
    8. 正向手法提示：可能性表述密度、逗号过多的流水句（不设 0 目标）
    9. 节奏与结构：句长变异系数 CV、段落长度、冒号+列表段、加粗密度

硬规则优先于其他所有项：四项硬规则的命中都必须清零。
提示项只用来挑句子，读得顺就不用动。
"""
import re
import sys
import statistics
from pathlib import Path

# Windows 控制台默认 GBK，不改会把中文输出成乱码。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# 级别一：铁证级（出现即改）
TIER1 = ["赋能", "助力", "深耕", "聚焦", "打造", "引领", "抓手", "闭环",
         "多维度", "全方位", "一站式", "沉浸式", "底层逻辑", "顶层设计",
         "生态位", "护城河", "里程碑", "新篇章"]
# 级别二：密集出现才可疑
TIER2 = ["此外", "与此同时", "值得注意的是", "综上所述", "总而言之",
         "不难看出", "显而易见", "毋庸置疑", "众所周知", "由此可见"]
# 套话短语。用正则，避免把「随着文件数增加，耗时线性增长」这类正常写法当成套话。
CLICHE = [r"在当今", r"随着[^，。；]{0,20}的?(?:不断|快速|飞速|日益|迅速)(?:发展|进步|普及)",
          r"的重要组成部分", r"的(?:大)?背景下", r"的角度来看",
          r"具有(?:十分|非常|极其)?重要(?:的)?意义", r"有着重要意义",
          r"通过本次实验，?我深刻(?:认识|体会)到"]
# 句法层特征（「而是」交给否定再肯定专项检查，避免重复计数）
SYNTAX = ["不仅是", "不仅仅是", "体现了", "彰显了", "反映出",
          "标志着", "折射出", "凸显了"]
# 去情态用的可能性表述。密集出现才可疑，单字「能」交给人工判断。
HEDGE = ["能够", "可以", "有助于", "有望", "能有效", "能显著"]

# ---- 硬规则一：否定再肯定 ----------------------------------------------
NEG_START = re.compile(r"不是|并非|不在于|不只是|不仅是|不仅仅|非但|与其说")
AFFIRM_LINK = re.compile(r"而是|则是|更是|而在于|则在于|恰恰是|恰恰说明|不如说")
# 「没有 / 不…，反而 / 恰恰…」单独配对。「没有」很常见，只和反推型连接词配，
# 否则「A 没有检出，B 则是 apache-2.0」这种并列对比会被误报。
NEG_MEIYOU = re.compile(r"没有|并没|不")
AFFIRM_REVERSE = re.compile(r"反而|反倒|恰恰")
# 「不是…，是…」这类省略连接词的形式，单独补一条。
BARE_PAIR = re.compile(
    r"(?:不是|并非|不只是|不仅是|不在于)[^，。；！？\n]{1,40}[，,]\s*(?:而|则|更)?是")
# 「A 而不是 B」是允许的写法（后面没有补肯定），检查前先去掉，避免误报。
ALLOWED_NEG = re.compile(r"而(?:不是|非)")
# 删掉一半之后只剩后半个连接词，属于残留，单独提醒。
# 只抓分句开头的「而是」；「B 模块则是 apache-2.0」这种并列对比是正常写法。
DANGLING = re.compile(r"(?:^|[，,：:])\s*而是")

# ---- 硬规则二 / 三 / 四 ------------------------------------------------
# 只抓表示流程的箭头。「<=」「>=」在正文里通常是比较符号，不算。
ARROW = re.compile(r"→|←|⇒|⇐|⟶|⟵|->|<-(?!-)|=>")
EM_DASH = re.compile(r"——")
EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF"   # 表情、符号、交通、补充符号
    "☀-⛿"            # 杂项符号 ☀ ⚠ ⚡
    "✀-➿"            # 装饰符号 ✅ ❌ ✨ ✔ ✘
    "⭐⭕⬆⬇⬅➡"  # ⭐ ⭕ 方向箭头图标
    "\U0001F1E6-\U0001F1FF"    # 区旗
    "️]")

CJK = r"[一-鿿]"


def strip_code(text: str) -> str:
    """去掉代码块与行内代码（命令、报错原文里出现禁用词是合理的）。"""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"`[^`]*`", "", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)   # 图片
    text = re.sub(r"^\s*\|.*\|\s*$", "", text, flags=re.M)  # 表格
    return text


def strip_code_lines(text: str) -> str:
    """去掉代码块内容与行内代码，保留原行号，供逐行检查使用。"""
    out, in_fence = [], False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else re.sub(r"`[^`]*`", "", line))
    return "\n".join(out)


def code_blocks(text: str):
    """返回 [(语言标记, 起始行号, 代码内容)]。"""
    blocks, lang, start, buf, in_fence = [], "", 0, [], False
    for i, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if s.startswith("```"):
            if not in_fence:
                in_fence, lang, start, buf = True, s[3:].strip().lower(), i, []
            else:
                in_fence = False
                blocks.append((lang, start, "\n".join(buf)))
            continue
        if in_fence:
            buf.append(line)
    return blocks


def find_hits(lines, words, regex=False):
    hits = []
    for i, line in enumerate(strip_code_lines("\n".join(lines)).splitlines(), 1):
        for w in words:
            m = re.search(w, line) if regex else (w if w in line else None)
            if m:
                hits.append((m.group(0) if regex else w, i, line.strip()[:78]))
    return hits


def sentences(body: str):
    parts = re.split(r"[。！？；\n]+", body)
    return [p.strip() for p in parts if len(p.strip()) >= 4]


def prose_only(body: str) -> str:
    """只保留散文段落，用于节奏分析。列表、标题、表格天生短且整齐，会污染统计。"""
    out = []
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith(("#", "-", "*", ">", "|", "!")) or re.match(r"^\d+[.)]\s", s):
            out.append("")
            continue
        out.append(s)
    return "\n".join(out)


def paragraphs(body: str, keep_lists: bool = False):
    out = []
    for blk in re.split(r"\n\s*\n", body):
        blk = blk.strip()
        if not blk or blk.startswith("|"):
            continue
        if blk.startswith("#") and not keep_lists:
            continue
        out.append(blk)
    return out


def scan_neg_affirm(raw: str):
    """扫描否定再肯定句式，返回 (成对命中, 疑似残留)。

    按 。！？； 切句，逗号不切句，这样「不是 A，而是 B」会落在同一句里。
    """
    paired, dangling = [], []
    for i, line in enumerate(strip_code_lines(raw).splitlines(), 1):
        for sent in re.split(r"[。！？；]", line):
            sent = sent.strip()
            if not sent:
                continue
            s = ALLOWED_NEG.sub("", sent)
            if ((NEG_START.search(s) and AFFIRM_LINK.search(s))
                    or (NEG_MEIYOU.search(s) and AFFIRM_REVERSE.search(s))
                    or BARE_PAIR.search(s)):
                paired.append((sent[:78], i))
            elif DANGLING.search(s):
                dangling.append((sent[:78], i))
    return paired, dangling


def scan_line_regex(raw: str, pattern):
    hits = []
    for i, line in enumerate(strip_code_lines(raw).splitlines(), 1):
        s = line.strip()
        if s and pattern.search(s):
            hits.append((s[:78], i))
    return hits


def scan_runon(raw: str, min_commas: int = 3, min_len: int = 36):
    """找出逗号过多的流水句，只提示候选，不判定对错。"""
    hits = []
    for i, line in enumerate(strip_code_lines(raw).splitlines(), 1):
        s = line.strip()
        if not s or s.startswith(("#", "|", ">", "-", "*")) or re.match(r"^\d+[.)]\s", s):
            continue
        for sent in re.split(r"[。！？；]", s):
            sent = sent.strip()
            if len(sent) >= min_len and sent.count("，") >= min_commas:
                hits.append((sent[:78], i))
    return hits


# ---- 图表检查 ----------------------------------------------------------
FIG_CAPTION = re.compile(r"^\s*(?:\*\*)?图\s*\d+(?:[-.．]\d+)*")
TAB_CAPTION = re.compile(r"^\s*(?:\*\*)?表\s*\d+(?:[-.．]\d+)*")
DIAGRAM_LANGS = ("mermaid", "plantuml", "puml", "dot", "graphviz")


def scan_figures(raw: str):
    """检查图题、表题与正文引用，返回问题列表 [(行号, 说明)]。"""
    issues = []
    lines = raw.splitlines()
    n = len(lines)

    def nearby(idx, step, pattern, span=3):
        j = idx + step
        while 0 <= j < n and abs(j - idx) <= span:
            if lines[j].strip():
                return bool(pattern.search(lines[j]))
            j += step
        return False

    # 图片与画图代码块：图题应在下方
    fig_idx = [i for i, l in enumerate(lines) if re.search(r"!\[[^\]]*\]\([^)]*\)", l)]
    in_fence, start = False, 0
    for i, l in enumerate(lines):
        s = l.strip()
        if s.startswith("```"):
            if not in_fence:
                in_fence, start = True, i
                lang = s[3:].strip().lower()
            else:
                in_fence = False
                if lang.startswith(DIAGRAM_LANGS):
                    fig_idx.append(i)       # 用代码块结束行判断下方图题
    for i in sorted(fig_idx):
        if not nearby(i, 1, FIG_CAPTION):
            if nearby(i, -1, FIG_CAPTION):
                issues.append((i + 1, "图题在图上方，应放在图下方"))
            else:
                issues.append((i + 1, "图下方没有「图 X-Y 标题」形式的图题"))

    # 表格：表题应在上方
    for i, l in enumerate(lines):
        if l.strip().startswith("|") and (i == 0 or not lines[i - 1].strip().startswith("|")):
            if not nearby(i, -1, TAB_CAPTION):
                issues.append((i + 1, "表格上方没有「表 X-Y 标题」形式的表题"))

    # 正文引用：编号了的图表应在正文里被提到
    body = strip_code_lines(raw)
    for kind, pat in (("图", FIG_CAPTION), ("表", TAB_CAPTION)):
        for i, l in enumerate(lines):
            m = pat.search(l)
            if not m:
                continue
            num = re.sub(r"[*\s]", "", m.group(0))[1:]
            refs = [ln for ln in body.splitlines()
                    if not pat.search(ln) and re.search(rf"{kind}\s*{re.escape(num)}(?!\d)", ln)]
            if not refs:
                issues.append((i + 1, f"{kind} {num} 在正文中没有被引用（应先写「如{kind} {num} 所示」）"))
    return issues


GRAY_NAMES = {"k", "black", "w", "white", "gray", "grey", "dimgray", "dimgrey",
              "darkgray", "darkgrey", "lightgray", "lightgrey", "silver", "none"}


def is_gray(value: str) -> bool:
    """判断颜色值是否为黑白灰：颜色名、R=G=B 的十六进制、'0.0'~'1.0' 灰度字符串。"""
    v = value.strip().strip("'\"").lower()
    if v in GRAY_NAMES or re.fullmatch(r"(?:0?\.\d+|[01](?:\.0+)?)", v):
        return True
    m = re.fullmatch(r"#([0-9a-f]{3}|[0-9a-f]{6})", v)
    if not m:
        return False
    h = m.group(1)
    if len(h) == 3:
        return h[0] == h[1] == h[2]
    return h[0:2] == h[2:4] == h[4:6]


def scan_diagram_code(raw: str):
    """检查画图代码的样式：黑白、直角、无阴影、图内无标题。"""
    issues = []
    for lang, ln, code in code_blocks(raw):
        if lang.startswith("mermaid"):
            if not re.search(r"%%\{\s*init", code):
                issues.append((ln, "Mermaid 没有 init 配置，默认主题是彩色的；用 references/figures-zh.md 里的黑白预设"))
            # 先去掉节点文字、引号、连线标签和注释，避免文字里的括号被误判
            shape = re.sub(r"%%.*", "", code)
            shape = re.sub(r"\[[^\]]*\]|\"[^\"]*\"|\|[^|]*\|", "", shape)
            m = re.search(r"\w\s*\(", shape)
            if m and re.search(r"^\s*(?:graph|flowchart)\b", code, re.M):
                issues.append((ln, "Mermaid 流程图里有 `id(…)` 圆角或 `id([…])` 胶囊形节点；"
                                   "普通步骤用 `id[文字]` 直角矩形"))
            for val in re.findall(r"(?:fill|stroke|color)\s*:\s*(#[0-9a-fA-F]{3,6}|[a-zA-Z]+)", code):
                if not is_gray(val):
                    issues.append((ln, f"Mermaid style/classDef 里有彩色 `{val}`"))
                    break
        elif lang.startswith(("plantuml", "puml")):
            if not re.search(r"skinparam\s+monochrome\s+true", code, re.I):
                issues.append((ln, "PlantUML 缺少 `skinparam monochrome true`"))
            if not re.search(r"skinparam\s+shadowing\s+false", code, re.I):
                issues.append((ln, "PlantUML 缺少 `skinparam shadowing false`"))
            if re.search(r"skinparam\s+roundcorner\s+[1-9]", code, re.I):
                issues.append((ln, "PlantUML 设置了圆角，改成 `skinparam roundcorner 0`"))
        elif lang.startswith(("dot", "graphviz")):
            colors = re.findall(r"\b(?:fill)?color\s*=\s*\"?([#\w]+)", code)
            if re.search(r"\brounded\b", code):
                issues.append((ln, "Graphviz 用了 rounded；改成 shape=box"))
            if any(not is_gray(c) for c in colors):
                issues.append((ln, "Graphviz 用了彩色；线条和文字用黑色，填充用白色或浅灰"))
        elif lang.startswith(("python", "py")) and re.search(r"matplotlib|plt\.", code):
            if re.search(r"plt\.title\(|\.set_title\(|suptitle\(", code):
                issues.append((ln, "matplotlib 在图内写了标题；标题放到图题里"))
            colors = re.findall(r"\b(?:color|c|facecolor|edgecolor)\s*=\s*(['\"][^'\"]+['\"])", code)
            cmaps = re.findall(r"\bcmap\s*=\s*['\"]([^'\"]+)['\"]", code)
            if any(not is_gray(c) for c in colors) or \
                    any(c.lower() not in ("gray", "grey", "greys", "binary", "gist_gray") for c in cmaps):
                issues.append((ln, "matplotlib 用了彩色；优先用灰度加线型或 hatch 纹理区分"))
    return issues


def scan_typography(raw: str):
    """排版一致性：中英文混排空格、半角标点、人称。返回 dict。"""
    body = strip_code_lines(raw)
    prose = "\n".join(l for l in body.splitlines()
                      if l.strip() and not l.strip().startswith(("|", "!", "#")))
    tight = len(re.findall(rf"{CJK}[A-Za-z0-9]|[A-Za-z0-9]{CJK}", prose))
    spaced = len(re.findall(rf"{CJK} [A-Za-z0-9]|[A-Za-z0-9] {CJK}", prose))
    halfwidth = []
    for i, l in enumerate(body.splitlines(), 1):
        s = l.strip()
        if not s or s.startswith(("|", "!", "#")):
            continue
        if re.search(rf"{CJK}[,;?!]|{CJK}:(?!//)|[,;?!]\s*{CJK}|\({CJK}|{CJK}\)", s):
            halfwidth.append((s[:78], i))
    persons = {
        "我": len(re.findall(r"我(?!们)", prose)),
        "我们": len(re.findall(r"我们", prose)),
        "笔者": len(re.findall(r"笔者", prose)),
        "本人": len(re.findall(r"本人", prose)),
    }
    has_refs = bool(re.search(r"^#+\s*参考文献|^参考文献\s*$", raw, re.M))
    return tight, spaced, halfwidth, persons, has_refs


def cv(values):
    if len(values) < 2:
        return 0.0
    m = statistics.mean(values)
    return statistics.stdev(values) / m if m else 0.0


def print_hits(title, hits, hint=None, limit=None):
    print(f"\n--- {title}: {len(hits)} 处 ---")
    if not hits:
        print("    (无)")
        return
    for ctx, ln in hits[:limit] if limit else hits:
        if hint:
            print(f"    L{ln:<4} {hint}")
            print(f"          {ctx}")
        else:
            print(f"    L{ln:<4} {ctx}")
    if limit and len(hits) > limit:
        print(f"    …… 另有 {len(hits) - limit} 处")


def check(path_str):
    p = Path(path_str)
    if not p.exists():
        print(f"!! 找不到文件: {p}")
        return 1
    raw = p.read_text(encoding="utf-8")
    lines = raw.splitlines()
    body = strip_code(raw)
    char_count = len(re.sub(r"\s", "", body))

    print("=" * 72)
    print(f"报告: {p}    字数(去代码): {char_count}")
    print("=" * 72)

    total_issues = 0
    hard_issues = 0
    for words, label, rx in ((TIER1, "级别一 铁证级词汇", False),
                             (TIER2, "级别二 可疑词汇", False),
                             (CLICHE, "套话短语", True),
                             (SYNTAX, "句法层特征", False)):
        hits = find_hits(lines, words, regex=rx)
        print(f"\n--- {label}: {len(hits)} 处 ---")
        if not hits:
            print("    (无)")
        for w, ln, ctx in hits:
            print(f"    L{ln:<4} [{w}]  {ctx}")
        total_issues += len(hits)

    # ---- 四条硬规则 ----
    paired, dangling = scan_neg_affirm(raw)
    print_hits("否定再肯定（硬规则一，目标 0）", paired, "删掉一半：只留否定，或只留肯定")
    hard_issues += len(paired)
    if dangling:
        print_hits("疑似残留（只剩「而是 / 则是」，前半句已删）", dangling)
        total_issues += len(dangling)

    arrows = scan_line_regex(raw, ARROW)
    print_hits("箭头符号（硬规则二，目标 0，代码块除外）", arrows,
               "改用关联词或顿号：先…，再…，最后…")
    hard_issues += len(arrows)

    dashes = scan_line_regex(raw, EM_DASH)
    print_hits("破折号「——」（硬规则三，目标 0）", dashes, "换成逗号、括号或冒号，或拆成两句")
    hard_issues += len(dashes)

    emojis = scan_line_regex(raw, EMOJI)
    print_hits("emoji 与装饰符号（硬规则四，目标 0）", emojis, "删掉；要表示对错用文字「正确 / 错误」")
    hard_issues += len(emojis)

    # ---- 图表 ----
    fig_issues = scan_figures(raw) + scan_diagram_code(raw)
    print(f"\n--- 图表与画图代码（见 references/figures-zh.md）: {len(fig_issues)} 处 ---")
    if not fig_issues:
        print("    (无)")
    for ln, msg in sorted(fig_issues):
        print(f"    L{ln:<4} {msg}")
    total_issues += len(fig_issues)

    # ---- 排版一致性 ----
    tight, spaced, halfwidth, persons, has_refs = scan_typography(raw)
    print(f"\n--- 排版一致性 ---")
    if tight and spaced:
        major = "加空格" if spaced >= tight else "不加空格"
        print(f"    中英文 / 数字混排：加空格 {spaced} 处，不加 {tight} 处  !! 不统一，"
              f"按多数统一为「{major}」")
    else:
        print(f"    中英文 / 数字混排：加空格 {spaced} 处，不加 {tight} 处  （统一）")
    used = {k: v for k, v in persons.items() if v}
    flag = "  !! 混用，全文固定一种" if len(used) > 1 else ""
    print(f"    人称：{used if used else '未使用第一人称'}{flag}")
    if len(used) > 1:
        total_issues += 1
    print_hits("中文语境里的半角标点（, ; : ? ! ( )）", halfwidth, limit=8)
    total_issues += len(halfwidth)
    if has_refs:
        print("\n    !! 有参考文献：逐条核实作者、题名、年份、出处真实存在，"
              "格式按 GB/T 7714-2015。没核实的删掉。")

    # ---- 正向手法提示 ----
    hedges = find_hits(lines, HEDGE)
    runons = scan_runon(raw)
    print(f"\n--- 正向手法提示（不设 0 目标，只用来挑句子）---")
    density = 1000.0 * len(hedges) / char_count if char_count else 0
    print(f"    可能性表述 {len(hedges)} 处，每千字 {density:.1f} 处  "
          f"（能够 / 可以 / 有助于 / 有望；单字「能」请人工看）")
    for w, ln, ctx in hedges[:8]:
        print(f"      L{ln:<4} [{w}]  {ctx}")
    if len(hedges) > 8:
        print(f"      …… 另有 {len(hedges) - 8} 处")
    print(f"    逗号过多的流水句 {len(runons)} 句  （可考虑降级为单句、补连接词；读得顺就不用动）")
    for ctx, ln in runons[:5]:
        print(f"      L{ln:<4} {ctx}")
    if len(runons) > 5:
        print(f"      …… 另有 {len(runons) - 5} 句")

    # ---- 节奏 ----
    prose = prose_only(body)
    sents = sentences(prose)
    lens = [len(s) for s in sents]
    print(f"\n--- 节奏（仅散文，已排除列表/标题/表格）---")
    if len(lens) >= 2:
        c = cv(lens)
        verdict = ("过于均匀，像模板套的" if c < 0.20
                   else "偏平实（报告的正常范围，无需处理）" if c < 0.45
                   else "有起伏（正常）" if c <= 1.00
                   else "起伏过大，可能刻意为之")
        print(f"    句子数 {len(sents)}  平均 {statistics.mean(lens):.1f} 字  "
              f"CV={c:.2f}  ({verdict})")
        print(f"    最短 {min(lens)} 字，最长 {max(lens)} 字")
        print("    （平实报告不必追求 CV 0.4-0.8，那本身是一种风格化）")
    else:
        print("    句子太少，无法评估")

    paras = paragraphs(prose)
    if len(paras) >= 2:
        plens = [len(re.sub(r"\s", "", q)) for q in paras]
        print(f"    段落数 {len(paras)}  平均 {statistics.mean(plens):.0f} 字  "
              f"CV={cv(plens):.2f}")

    # ---- 结构：在含列表的原文上统计，否则「冒号+列表」永远是 0 ----
    print(f"\n--- 结构 ---")
    blocks = paragraphs(body, keep_lists=True)
    colon_list = 0
    for k, blk in enumerate(blocks):
        first = blk.split("\n")[0].strip()
        rest = blk.split("\n")[1:]
        nxt = blocks[k + 1] if k + 1 < len(blocks) else ""
        if re.search(r"[：:]\s*(?:\*\*)?$", first) and (
                any(re.match(r"\s*(?:[-*]|\d+[.)])\s", r) for r in rest)
                or re.match(r"\s*(?:[-*]|\d+[.)])\s", nxt)):
            colon_list += 1
    if blocks:
        ratio = 100.0 * colon_list / len(blocks)
        flag = "  !! 偏高" if ratio > 30 else ""
        print(f"    「冒号+列表」段落: {colon_list}/{len(blocks)} ({ratio:.0f}%){flag}")
    bold = len(re.findall(r"\*\*[^*]+\*\*", body))
    print(f"    加粗片段: {bold} 处  (建议 <15)")
    bullets = len(re.findall(r"^\s*[-*]\s", body, re.M))
    print(f"    列表项: {bullets} 条")

    print(f"\n{'=' * 72}")
    print(f"硬规则命中: {hard_issues}（目标 0）    其他命中: {total_issues}"
          f"（目标：级别一 = 0，其余尽量 <5）")
    print("=" * 72)
    return 1 if hard_issues else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    rc = 0
    for arg in sys.argv[1:]:
        rc |= check(arg)
        print()
    sys.exit(rc)
