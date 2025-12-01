import re
from pathlib import Path

# 保持原有的导入不变
from .prompt_templates import get_user_prompt, get_system_prompt
from ..config import ASSETS_DIR, OUTPUT_DIR
from ..core.graph_builder import ConceptMemory
from ..core.llm_client import call_llm_json
from ..core.loader import read_epub_chapters_custom

# 定义输出路径
KB_DIR = OUTPUT_DIR / "knowledge_base"
CHAPTERS_DIR = KB_DIR / "chapters"
CONCEPTS_DIR = KB_DIR / "concepts"  # 【新增】概念卡片目录


def sanitize_filename(name):
    """清洗文件名"""
    name = name.replace('.html', '').replace('.xhtml', '')
    name = re.sub(r'[\\/*?:"<>|“”‘’\'"]', "", name)
    return name.strip()[:60]


def get_safe_title_from_chap(chapter_data):
    """辅助函数：从章节数据中提取并清洗标题"""
    raw = chapter_data.get('title', chapter_data['id'])
    return sanitize_filename(raw)


def generate_concept_cards(memory):
    """
    将 JSON 数据转化为 Obsidian 可读的 Markdown 概念卡片
    """
    CONCEPTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n📇 正在生成 {len(memory.concepts)} 张概念卡片...")

    for name, definition in memory.concepts.items():
        # 清洗文件名
        safe_name = sanitize_filename(name)
        if not safe_name: continue

        file_path = CONCEPTS_DIR / f"{safe_name}.md"

        # 获取出处列表 (这里存储的是文件名，如 "01_省委...")
        chapter_links = memory.appearances.get(name, [])
        # 生成双向链接字符串
        backlinks = ", ".join([f"[[{link}]]" for link in chapter_links])

        content = f"""---
tags: [核心概念]
---

# {name}

### 📝 定义
> {definition}

### 📚 出现章节
{backlinks}
"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    print(f"✅ 概念卡片已生成至: {CONCEPTS_DIR}")


def run_analysis():
    # 1. 初始化目录
    KB_DIR.mkdir(parents=True, exist_ok=True)
    CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)

    # 2. 加载电子书
    epub_path = ASSETS_DIR / "毛主席教我们当省委书记.epub"
    if not epub_path.exists():
        print(f"❌ 错误：在 {ASSETS_DIR} 下找不到电子书文件！")
        return

    book_title = epub_path.stem
    print(f"📖 正在解析《{book_title}》...")

    current_system_prompt = get_system_prompt(book_title)
    chapters = read_epub_chapters_custom(epub_path)

    # 【修改点 1】初始化并加载旧记忆
    # 这样即使跳过前9章，前9章的概念依然在内存里，不会丢失
    memory = ConceptMemory()
    json_path = KB_DIR / "knowledge_graph.json"
    memory.load_from_file(json_path)

    print(f"📚 共识别出 {len(chapters)} 个章节，开始构建知识库...\n")

    index_content = "# 全书目录与索引\n\n| 序号 | 章节 | 核心标签 | 一句话总结 |\n|---|---|---|---|\n"

    # 3. 逐章处理
    for i, chap in enumerate(chapters):

        # --- A. 准备文件名 ---
        curr_safe_title = get_safe_title_from_chap(chap)
        file_name = f"{i + 1:02d}_{curr_safe_title}.md"
        file_path = CHAPTERS_DIR / file_name

        # 这是一个不带后缀的链接名，用于 Obsidian 链接和记忆库
        link_name = f"{i + 1:02d}_{curr_safe_title}"

        # =================================================================
        # 断点续传：检查文件是否已存在
        # =================================================================
        if file_path.exists():
            print(f"⏩ [已存在，跳过] {file_name}")

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    # 简单提取摘要和标签用于目录回填
                    summary_match = re.search(r'> \*\*摘要\*\*：(.*?)\n', content)
                    summary = summary_match.group(1).strip() if summary_match else "（摘要读取失败）"

                    tags_match = re.search(r'tags: \[(.*?)\]', content)
                    tags_str = tags_match.group(1) if tags_match else ""
                    tags_clean = tags_str.replace("'", "").replace('"', "")
                    tags_display = ", ".join([f"`{t.strip()}`" for t in tags_clean.split(',')][:3])

                    link = f"[{curr_safe_title}](./chapters/{file_name})"
                    index_content += f"| {i + 1} | {link} | {tags_display} | {summary} |\n"
            except Exception as e:
                print(f"   ⚠️ 读取旧文件元数据失败: {e}")

            continue
        # =================================================================

        print(f"⚡ [{i + 1}/{len(chapters)}] 正在深度研读：{curr_safe_title} ...")

        # --- B. AI 分析 ---
        context_str = memory.get_context_string()
        prompt = get_user_prompt(chap['content'], context_str)

        try:
            result = call_llm_json(current_system_prompt, prompt)
        except Exception as e:
            print(f"   ⚠️ 分析失败，跳过本章: {str(e)}")
            continue

        # --- C. 更新知识图谱记忆 ---
        # 【修改点 2】传入 link_name (带序号的)，这样概念卡片里的链接就能点通了
        concepts = result.get('key_concepts', [])
        memory.update(concepts, link_name)

        # --- D. 组装 Markdown 内容 ---
        tags = result.get('tags', [])
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
        # 修复原文分段显示问题
        html_formatted_content = chap['content'].replace('\n', '<br>')
        md_content += f"""
<details>
<summary><strong>📄 点击展开/收起：本章原文全文</strong></summary>

{html_formatted_content}

</details>

"""
        md_content += f"""
## 🧠 深度思考与解读

{result.get('analysis')}

"""

        if 'quotes' in result and result['quotes']:
            md_content += "### 💬 振聋发聩的金句\n"
            for q in result['quotes']:
                md_content += f"> {q}\n>\n"

        md_content += "\n---\n"

        # 上一章链接
        if i > 0:
            prev_chap = chapters[i - 1]
            prev_title = get_safe_title_from_chap(prev_chap)
            prev_link_name = f"{i:02d}_{prev_title}"
            md_content += f"⬅️ 上一章：[[{prev_link_name}]] | "

        # 下一章链接
        if i < len(chapters) - 1:
            next_chap = chapters[i + 1]
            next_title = get_safe_title_from_chap(next_chap)
            next_link_name = f"{i + 2:02d}_{next_title}"
            md_content += f"下一章：[[{next_link_name}]] ➡️"

        # --- E. 写入文件 ---
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        # --- F. 更新目录索引 ---
        tags_str = ", ".join([f"`{t}`" for t in tags[:3]])
        link = f"[{curr_safe_title}](./chapters/{file_name})"
        index_content += f"| {i + 1} | {link} | {tags_str} | {summary} |\n"

        # 【建议】每跑完一章就保存一次记忆，防止程序中途崩溃数据丢失
        memory.save_memory(KB_DIR)

    # 4. 循环结束后的收尾工作
    with open(KB_DIR / "00_全书概览_Index.md", "w", encoding="utf-8") as f:
        f.write(index_content)

    # 保存最终 JSON
    memory.save_memory(KB_DIR)

    # 【修改点 3】生成概念卡片
    generate_concept_cards(memory)

    print(f"\n✅ 全部完成！知识库已生成在：{KB_DIR}")
    print("你可以直接用 Obsidian 打开此目录，体验最佳。")
