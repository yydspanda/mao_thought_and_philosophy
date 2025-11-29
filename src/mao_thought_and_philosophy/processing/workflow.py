"""
这是主控逻辑，串联起一切。

"""
# src/mao_thought_and_philosophy/processing/workflow.py
import os
import json
from ..config import ASSETS_DIR, OUTPUT_DIR
from ..core.loader import read_epub_chapters
from ..core.graph_builder import ConceptMemory
from ..core.llm_client import call_llm_json  # 假设你封装了一个返回 dict 的 LLM 调用
from .prompt_templates import ANALYSIS_SYSTEM_PROMPT, get_user_prompt


def run_analysis():
    # 1. 准备
    epub_path = ASSETS_DIR / "毛主席教我们当省委书记.epub"
    memory = ConceptMemory()
    chapters = read_epub_chapters(epub_path)

    print(f"检测到 {len(chapters)} 个章节，开始深度解读...")

    final_markdown = "# 《毛主席教我们当省委书记》深度解读与知识图谱\n\n"

    # 2. 循环处理每一章
    for i, chap in enumerate(chapters):
        print(f"正在处理第 {i + 1} 章: {chap['id']}...")

        # 获取以前章节积累的知识上下文
        context_str = memory.get_context_string()

        # 构造 Prompt
        prompt = get_user_prompt(chap['content'], context_str)

        # 调用大模型 (这里需要你配置好 API Key)
        # 假设返回的是解析好的 Python 字典
        result = call_llm_json(system_prompt=ANALYSIS_SYSTEM_PROMPT, user_prompt=prompt)

        # 3. 更新全局记忆 (这是关联产生的关键步骤！)
        memory.update(result['key_concepts'], chap['id'])

        # 4. 实时生成 Markdown (Obsidian 风格)
        md_content = f"## 第 {i + 1} 章：{chap['id']}\n\n"
        md_content += f"> **核心摘要**：{result['summary']}\n\n"

        md_content += "### 🧠 概念图谱演化\n"
        for concept in result['key_concepts']:
            # 使用双括号语法，方便 Obsidian/Logseq 自动连接
            md_content += f"- **[[{concept['name']}]]**: {concept['definition']}\n"

        md_content += "\n### 🔗 逻辑关联与脉络\n"
        md_content += f"{result['connections']}\n\n"

        md_content += "### 💡 哲学启示\n"
        md_content += f"{result['reflection']}\n\n"

        md_content += "---\n\n"

        final_markdown += md_content

    # 5. 保存结果
    with open(OUTPUT_DIR / "Full_Analysis.md", "w", encoding="utf-8") as f:
        f.write(final_markdown)

    # 保存知识图谱数据，供以后可视化使用
    memory.save_memory(OUTPUT_DIR)

    print("解读完成！已生成 Full_Analysis.md 和 knowledge_graph.json")