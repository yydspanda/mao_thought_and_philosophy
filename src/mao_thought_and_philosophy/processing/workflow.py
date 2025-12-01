import os
import re
from pathlib import Path

# 导入配置和核心模块
from ..config import ASSETS_DIR, OUTPUT_DIR
from ..core.loader import read_epub_chapters_custom  # 确保 loader.py 里函数名一致
from ..core.graph_builder import ConceptMemory
from ..core.llm_client import call_llm_json
from .prompt_templates import ANALYSIS_SYSTEM_PROMPT, get_user_prompt

# 定义输出路径
KB_DIR = OUTPUT_DIR / "knowledge_base"
CHAPTERS_DIR = KB_DIR / "chapters"


def sanitize_filename(name):
    """
    【增强版】清洗文件名
    1. 移除 html 后缀
    2. 移除系统非法字符 (/:*?"<>|)
    3. 移除中文/英文引号，防止文件名丑陋和链接破坏
    """
    # 移除后缀
    name = name.replace('.html', '').replace('.xhtml', '')

    # 正则替换：移除 \ / * ? : " < > | 以及 “” ‘’ ' "
    name = re.sub(r'[\\/*?:"<>|“”‘’\'"]', "", name)

    # 去除首尾空格并截断长度，防止文件名过长
    return name.strip()[:60]


def get_safe_title_from_chap(chapter_data):
    """
    辅助函数：从章节数据中提取并清洗标题
    用于生成当前文件、上一章链接、下一章链接，确保逻辑统一
    """
    # 优先取 extracted_title，如果没有则取 id
    raw = chapter_data.get('title', chapter_data['id'])
    return sanitize_filename(raw)


def run_analysis():
    # 1. 初始化目录
    KB_DIR.mkdir(parents=True, exist_ok=True)
    CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)

    # 2. 加载电子书
    epub_path = ASSETS_DIR / "毛主席教我们当省委书记.epub"
    if not epub_path.exists():
        print(f"❌ 错误：在 {ASSETS_DIR} 下找不到电子书文件！")
        return

    print("📖 正在解析电子书章节...")
    # 这里调用的是我们之前修改过的、能提取 title 的 loader
    chapters = read_epub_chapters_custom(epub_path)
    memory = ConceptMemory()

    print(f"📚 共识别出 {len(chapters)} 个章节，开始构建知识库...\n")

    # 初始化总索引内容
    index_content = "# 全书目录与索引\n\n| 序号 | 章节 | 核心标签 | 一句话总结 |\n|---|---|---|---|\n"

    # 3. 逐章处理
    for i, chap in enumerate(chapters):

        # --- A. 准备文件名 ---
        # 获取清洗后的标题
        curr_safe_title = get_safe_title_from_chap(chap)

        # 生成带序号的文件名，如 "01_省委第一书记要抓理论工作.md"
        file_name = f"{i + 1:02d}_{curr_safe_title}.md"
        file_path = CHAPTERS_DIR / file_name

        print(f"⚡ [{i + 1}/{len(chapters)}] 正在深度研读：{curr_safe_title} ...")

        # --- B. AI 分析 (RAG + 记忆) ---
        context_str = memory.get_context_string()
        prompt = get_user_prompt(chap['content'], context_str)

        try:
            # 调用大模型获取 JSON
            result = call_llm_json(ANALYSIS_SYSTEM_PROMPT, prompt)
        except Exception as e:
            print(f"   ⚠️ 分析失败，跳过本章: {str(e)}")
            continue

        # --- C. 更新知识图谱记忆 (可选) ---
        concepts = result.get('key_concepts', [])
        memory.update(concepts, curr_safe_title)
        # --- D. 组装 Markdown 内容 ---

        # 1. Frontmatter (元数据)
        tags = result.get('tags', [])
        # 处理摘要中的双引号，防止 YAML 格式错误
        summary = result.get('summary', '暂无总结').replace('"', "'")

        md_content = f"""---
title: "{curr_safe_title}"
order: {i + 1}
tags: {tags}
date: 2025-11-30
---

# 第{i + 1}章 {curr_safe_title}

> **摘要**：{summary}

"""
        # 2. 原文全文 (折叠显示)
        # 注意：<details> 内部保留空行，以确保 Markdown 渲染正常
        md_content += f"""
<details>
<summary><strong>📄 点击展开/收起：本章原文全文</strong></summary>

{chap['content']}

</details>

"""

        # 3. 深度思考 (Analysis)
        md_content += f"""
## 🧠 深度思考与解读

{result.get('analysis')}

"""

        # 4. 金句摘录 (Quotes)
        if 'quotes' in result and result['quotes']:
            md_content += "### 💬 振聋发聩的金句\n"
            for q in result['quotes']:
                md_content += f"> {q}\n>\n"

        # 5. 底部导航 (关键修复：确保链接文件名与生成的一致)
        md_content += "\n---\n"

        # 上一章
        if i > 0:
            prev_chap = chapters[i - 1]
            prev_title = get_safe_title_from_chap(prev_chap)
            # 序号规则：上一章的索引是 i-1，所以它的序号是 (i-1)+1 = i
            prev_link_name = f"{i:02d}_{prev_title}"
            md_content += f"⬅️ 上一章：[[{prev_link_name}]] | "

        # 下一章
        if i < len(chapters) - 1:
            next_chap = chapters[i + 1]
            next_title = get_safe_title_from_chap(next_chap)
            # 序号规则：下一章的索引是 i+1，所以它的序号是 (i+1)+1 = i+2
            next_link_name = f"{i + 2:02d}_{next_title}"
            md_content += f"下一章：[[{next_link_name}]] ➡️"

        # --- E. 写入文件 ---
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        # --- F. 更新目录索引 ---
        tags_str = ", ".join([f"`{t}`" for t in tags[:3]])  # 只展示前3个标签
        # 使用相对路径链接，方便在 GitHub 或 Obsidian 中直接点击
        link = f"[{curr_safe_title}](./chapters/{file_name})"
        index_content += f"| {i + 1} | {link} | {tags_str} | {summary} |\n"

    # 4. 循环结束后的收尾工作

    # A. 写入总索引
    with open(KB_DIR / "00_全书概览_Index.md", "w", encoding="utf-8") as f:
        f.write(index_content)

    # B. 【新增】保存知识图谱数据
    memory.save_memory(KB_DIR)
    print(f"\n✅ 全部完成！知识库已生成在：{KB_DIR}")
    print("你可以直接用 Obsidian 打开此目录，体验最佳。")
