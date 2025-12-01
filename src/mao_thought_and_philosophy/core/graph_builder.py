# src/mao_thought_and_philosophy/core/graph_builder.py
import json
import os
from pathlib import Path


class ConceptMemory:
    def __init__(self):
        # 存储概念及其定义：{"修正主义": "赫鲁晓夫提出的..."}
        self.concepts = {}
        # 存储概念间的关系：[("赫鲁晓夫", "修正主义", "推动者")]
        self.relations = []
        # 记录每个概念出现的章节：{"修正主义": ["01_省委...", "03_防止..."]}
        self.appearances = {}

    def load_from_file(self, file_path: Path):
        """
        从已有的 JSON 文件加载记忆
        这是防止断点续传时数据丢失的关键。
        """
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 使用 .get 防止旧数据字段缺失导致报错
                    self.concepts = data.get("concepts", {})
                    self.relations = data.get("relations", [])
                    self.appearances = data.get("appearances", {})
                print(f"🧠 已加载现有知识图谱：包含 {len(self.concepts)} 个概念")
            except Exception as e:
                print(f"⚠️ 尝试加载旧图谱失败 (将从头开始构建): {e}")
        else:
            print("🆕 未找到现有图谱，将初始化空白记忆。")

    def update(self, new_concepts, chapter_title):
        """
        接收大模型提取的新概念，合并到全局记忆中
        """
        # 1. 防御性检查
        if not new_concepts or not isinstance(new_concepts, list):
            return

        for concept in new_concepts:
            # 使用 .get 安全获取
            name = concept.get('name')
            definition = concept.get('definition')

            # 如果关键字段缺失，跳过
            if not name or not definition:
                continue

            # 2. 更新概念定义
            # 策略：保留最早的定义（通常是首次提出时的定义），避免定义不断变长。
            if name not in self.concepts:
                self.concepts[name] = definition

            # 3. 记录出处
            if name not in self.appearances:
                self.appearances[name] = []

            # 避免同一章重复记录
            if chapter_title not in self.appearances[name]:
                self.appearances[name].append(chapter_title)

    def get_context_string(self, limit=20):
        """
        提取高价值概念，打包成字符串发给 LLM。
        """
        if not self.concepts:
            return "暂无已知概念。"

        summary = f"【已知核心概念库 (Top {limit})】:\n"

        # 排序：按“出现章节数”从多到少排序，优先把高频概念发给 AI
        sorted_concepts = sorted(
            self.appearances.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )

        count = 0
        for name, _ in sorted_concepts:
            if count >= limit:
                break

            definition = self.concepts.get(name, "暂无定义")
            # 简单截断，防止 Token 溢出
            clean_def = definition[:100] + "..." if len(definition) > 100 else definition

            summary += f"- {name}: {clean_def}\n"
            count += 1

        return summary

    def save_memory(self, output_dir: Path):
        """
        将知识图谱保存为 JSON 文件
        """
        data = {
            "concepts": self.concepts,
            "relations": self.relations,
            "appearances": self.appearances
        }

        file_path = output_dir / "knowledge_graph.json"

        try:
            with open(file_path, "w", encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"💾 知识图谱数据已保存至: {file_path}")
        except Exception as e:
            print(f"❌ 保存知识图谱失败: {e}")