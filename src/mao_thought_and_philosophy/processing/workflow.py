import datetime
import re
import sys
import time
from pathlib import Path

# 保持原有的导入不变
from .prompt_templates import get_user_prompt, get_system_prompt
from ..config import ASSETS_DIR, OUTPUT_DIR
from ..core.graph_builder import ConceptMemory
from ..core.llm_client import call_llm_json
from ..core.loader import read_epub_chapters_mao_selected


def sanitize_filename(name):
    # ... 安全文件名
    name = name.replace('.html', '').replace('.xhtml', '')
    name = re.sub(r'[\\/*?:"<>|“”‘’\'"]', "", name)
    return name.strip()[:60]

def get_safe_title_from_chap(chapter_data):
    """辅助函数：从章节数据中提取并清洗标题"""
    raw = chapter_data.get('title', chapter_data['id'])
    return sanitize_filename(raw)


def wait_with_countdown(seconds, message="等待中"):
    """
    倒计时辅助函数
    显示格式：⏳ 等待中: 00:29:59 ...
    """
    print(f"\n🛑 {message} (共 {seconds / 60:.1f} 分钟)...")
    for remaining in range(seconds, 0, -1):
        mins, secs = divmod(remaining, 60)
        hours, mins = divmod(mins, 60)
        time_format = f"{hours:02d}:{mins:02d}:{secs:02d}"

        # 使用 \r 回车符实现单行刷新，不换行
        sys.stdout.write(f"\r⏳ 倒计时: {time_format}")
        sys.stdout.flush()
        time.sleep(1)
    print("\n✅ 等待结束，继续执行！\n")


def generate_concept_cards(memory, output_dir: Path):
    """将 JSON 数据转化为 Obsidian 可读的 Markdown 概念卡片"""
    concepts_dir = output_dir / "concepts"
    concepts_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n📇 正在生成概念卡片至: {concepts_dir}")

    for name, definition in memory.concepts.items():
        safe_name = sanitize_filename(name)
        if not safe_name:
            continue

        file_path = concepts_dir / f"{safe_name}.md"
        chapter_links = memory.appearances.get(name, [])
        # 生成双向链接列表
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

    print("✅ 概念卡片更新完毕")


def run_analysis(epub_filename: str):
    # 1. 动态构建路径
    epub_path = ASSETS_DIR / epub_filename
    if not epub_path.exists():
        print(f"❌ 错误：在 {ASSETS_DIR} 下找不到文件：{epub_filename}")
        return
    book_title = epub_path.stem  # "毛泽东选集一至七卷"
    safe_book_title = sanitize_filename(book_title)
    # 【关键】为这本书创建独立的知识库目录
    current_kb_dir = OUTPUT_DIR / safe_book_title
    chapters_dir = current_kb_dir / "chapters"

    current_kb_dir.mkdir(parents=True, exist_ok=True)
    chapters_dir.mkdir(parents=True, exist_ok=True)

    print(f"📖 正在解析《{book_title}》...")
    print(f"📂 输出目录: {current_kb_dir}")

    # 2. 加载数据
    current_system_prompt = get_system_prompt(book_title)
    # 【核心调用】使用新的加载器，获取带层级（卷、时期）和日期的数据
    chapters = read_epub_chapters_mao_selected(epub_path)
    # 加载针对这本书的记忆文件
    memory = ConceptMemory()
    json_path = current_kb_dir / "knowledge_graph.json"
    memory.load_from_file(json_path)

    print(f"📚 共识别出 {len(chapters)} 个章节。")

    # =================================================================
    # 启动延时策略 (按需开启)
    # print("🚦 依据策略，程序将在 5 秒后开始处理...")
    # wait_with_countdown(5, "启动延迟")
    # =================================================================

    # 初始化全书索引内容 (Markdown 表格)
    # 【新增】增加了 卷、时期、日期 列
    index_content = "# 全书目录与索引\n\n| 序号 | 卷别 | 时期 | 章节 | 发表日期 | 核心标签 | 一句话总结 |\n|---|---|---|---|---|---|---|\n"

    # 3. 逐章处理
    for i, chap in enumerate(chapters):

        curr_safe_title = get_safe_title_from_chap(chap)
        # 生成带序号的文件名，保证排序
        file_name = f"{i + 1:03d}_{curr_safe_title}.md"
        file_path = chapters_dir / file_name
        # 链接名（用于 Obsidian 双链）
        link_name = f"{i + 1:03d}_{curr_safe_title}"
        # 提取元数据 (使用 .get 提供默认值，防止旧数据报错)
        volume = chap.get('volume', '未分类')
        period = chap.get('period', '未分类')
        publish_date = chap.get('date', '未知')
        # =================================================================
        # 断点续传：检查文件是否已存在
        # =================================================================
        if file_path.exists():
            print(f"⏩ [已存在，跳过] {file_name}")
            try:
                # 尝试读取已存在文件的 Frontmatter 或内容，填入索引表
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    # 正则提取摘要
                    summary_match = re.search(r'> \*\*摘要\*\*：(.*?)\n', content)
                    summary = summary_match.group(1).strip() if summary_match else "（摘要读取失败）"
                    # 正则提取标签
                    tags_match = re.search(r'tags: \[(.*?)\]', content)
                    tags_str = tags_match.group(1) if tags_match else ""
                    tags_clean = tags_str.replace("'", "").replace('"', "")
                    tags_display = ", ".join([f"`{t.strip()}`" for t in tags_clean.split(',')][:3])
                    # 构建索引行
                    link = f"[{curr_safe_title}](./chapters/{file_name})"
                    index_content += f"| {i + 1} | {volume} | {period} | {link} | {publish_date} | {tags_display} | {summary} |\n"
            except Exception:
                pass
            continue  # 跳过，且不进行等待
        # =================================================================
        # 开始处理新章节（或被删除后重跑的章节）
        # =================================================================
        # 【核心步骤】防止污染：先从内存中把这一章的旧痕迹擦掉
        memory.purge_chapter_memory(link_name)
        print(f"⚡ [{i + 1}/{len(chapters)}] 正在深度研读：{curr_safe_title} ...")

        # --- B. AI 分析 ---
        # 获取上下文记忆（Top 20 概念）
        context_str = memory.get_context_string()
        # 渲染 User Prompt
        prompt = get_user_prompt(chap['content'], context_str)

        try:
            # 调用 LLM
            result = call_llm_json(current_system_prompt, prompt)
        except Exception as e:
            print(f"   ⚠️ 分析失败，跳过本章: {str(e)}")
            continue

        # --- C. 更新知识图谱记忆 ---
        concepts = result.get('key_concepts', [])
        memory.update(concepts, link_name)
        # --- D. 组装 Markdown 内容 ---
        tags = result.get('tags', [])
        summary = result.get('summary', '暂无总结').replace('"', "'")
        # 【优化】将“时期”和“卷”作为标签加入，方便筛选
        if period != '未分类' and period not in tags:
            tags.append(period)
        if volume != '未分类' and volume not in tags:
            tags.append(volume)
        # 获取当前日期
        today_date = datetime.date.today().isoformat()
        # 构建 Frontmatter (YAML 头)
        md_content = f"""---
title: "{curr_safe_title}"
order: {i + 1}
volume: "{volume}"
period: "{period}"
publish_date: "{publish_date}"
tags: {tags}
date: {today_date}
---

# 第{i + 1}章 {curr_safe_title}

> **归属**：{volume} / {period}
> **发表时间**：{publish_date}

> **摘要**：{summary}

"""
        # 添加原文折叠块
        html_formatted_content = chap['content'].replace('\n', '<br>')
        md_content += f"""
<details>
<summary><strong>📄 点击展开/收起：本章原文全文</strong></summary>

{html_formatted_content}

</details>

"""
        # 添加 AI 分析正文
        md_content += f"""
## 🧠 深度思考与解读

{result.get('analysis')}

"""

        # 添加金句
        if 'quotes' in result and result['quotes']:
            md_content += "### 💬 振聋发聩的金句\n"
            for q in result['quotes']:
                md_content += f"> {q}\n>\n"

        md_content += "\n---\n"

        # 添加上一章/下一章导航
        if i > 0:
            prev_chap = chapters[i - 1]
            prev_title = get_safe_title_from_chap(prev_chap)
            prev_link_name = f"{i:03d}_{prev_title}"  # 注意这里序号格式保持一致
            md_content += f"⬅️ 上一章：[[{prev_link_name}]] | "

        if i < len(chapters) - 1:
            next_chap = chapters[i + 1]
            next_title = get_safe_title_from_chap(next_chap)
            next_link_name = f"{i + 2:03d}_{next_title}"
            md_content += f"下一章：[[{next_link_name}]] ➡️"

        # 写入文件
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        # 更新索引表字符串
        tags_str_display = ", ".join([f"`{t}`" for t in tags[:3]])
        link = f"[{curr_safe_title}](./chapters/{file_name})"
        index_content += f"| {i + 1} | {volume} | {period} | {link} | {publish_date} | {tags_str_display} | {summary} |\n"

        # 实时保存记忆到这本书的专用目录
        memory.save_memory(current_kb_dir)

        # =================================================================
        # API 冷却策略
        # =================================================================
        if i < len(chapters) - 1:
            sec = 1
            print(f"💤 休息 {sec} 秒以保护 API...")
            wait_with_countdown(sec, "API 冷却")
        # =================================================================

    # 4. 结束
    with open(current_kb_dir / "00_全书概览_Index.md", "w", encoding="utf-8") as f:
        f.write(index_content)

    memory.save_memory(current_kb_dir)
    # 生成卡片到专用目录
    generate_concept_cards(memory, current_kb_dir)

    print(f"\n✅ 全部完成！")
    print("你可以直接用 Obsidian 打开此目录，体验最佳。")
