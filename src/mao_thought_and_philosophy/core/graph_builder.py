"""
这是解决“章节无关联”的关键。我们需要一个全局状态来记录这本书里出现的所有核心概念。

"""
# src/mao_thought_and_philosophy/core/graph_builder.py
import json
from pathlib import Path


class ConceptMemory:
    def __init__(self):
        # 存储概念及其定义：{"修正主义": "赫鲁晓夫提出的..."}
        self.concepts = {}
        # 存储概念间的关系：[("赫鲁晓夫", "修正主义", "推动者")]
        self.relations = []
        # 记录每个概念出现的章节
        self.appearances = {}

    def update(self, new_concepts, chapter_id):
        """
        接收大模型提取的新概念，合并到全局记忆中
        """
        for concept in new_concepts:
            name = concept['name']
            definition = concept['definition']

            # 如果是旧概念，记录演变；如果是新概念，添加
            if name not in self.concepts:
                self.concepts[name] = definition
            else:
                # 这是一个高级功能：概念进化
                self.concepts[name] += f" | 补充定义({chapter_id}): {definition}"

            if name not in self.appearances:
                self.appearances[name] = []
            self.appearances[name].append(chapter_id)

    def get_context_string(self):
        """
        将当前已知的核心概念打包成字符串，
        发给 LLM，让它在读下一章时拥有“前文记忆”。
        """
        summary = "【已知核心概念库】:\n"
        # 为了节省 Token，只取最近更新或最重要的 Top 10 概念
        for k, v in list(self.concepts.items())[:15]:
            summary += f"- {k}: {v[:50]}...\n"
        return summary

    def save_memory(self, path: Path):
        data = {
            "concepts": self.concepts,
            "relations": self.relations,
            "appearances": self.appearances
        }
        with open(path / "knowledge_graph.json", "w", encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)