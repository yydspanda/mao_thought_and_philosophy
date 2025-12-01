# src/mao_thought_and_philosophy/core/graph_builder.py
import json
from pathlib import Path

class ConceptMemory:
    def __init__(self):
        # 存储概念及其定义：{"修正主义": "赫鲁晓夫提出的..."}
        self.concepts = {}
        # 存储概念间的关系（预留功能）：[("赫鲁晓夫", "修正主义", "推动者")]
        self.relations = []
        # 记录每个概念出现的章节：{"修正主义": ["01_省委...", "03_防止..."]}
        self.appearances = {}

    def update(self, new_concepts, chapter_title):
        """
        接收大模型提取的新概念，合并到全局记忆中

        Args:
            new_concepts (list): [{"name": "xxx", "definition": "xxx"}, ...]
            chapter_title (str): 当前章节的标题
        """
        # 1. 防御性检查：如果 LLM 没提取出概念，直接返回
        if not new_concepts or not isinstance(new_concepts, list):
            return

        for concept in new_concepts:
            # 使用 .get 安全获取，防止 KeyError
            name = concept.get('name')
            definition = concept.get('definition')

            # 如果关键字段缺失，跳过
            if not name or not definition:
                continue

            # 2. 更新概念定义
            # 策略：如果是一个全新的概念，记录它的定义。
            # 如果是旧概念，我们暂时保留最早的定义，防止定义被不断追加导致 Prompt 过长。
            # (当然，这里也可以改为覆盖更新，取决于你希望它记最新的还是最早的)
            if name not in self.concepts:
                self.concepts[name] = definition

            # 3. 记录出处 (关键逻辑)
            if name not in self.appearances:
                self.appearances[name] = []

            # 避免同一章重复记录
            if chapter_title not in self.appearances[name]:
                self.appearances[name].append(chapter_title)

    def get_context_string(self, limit=20):
        """
        提取高价值概念，打包成字符串发给 LLM。
        策略：优先选择出现频率最高（最重要）的概念。
        """
        if not self.concepts:
            return "暂无已知概念。"

        summary = f"【已知核心概念库 (Top {limit})】:\n"

        # 1. 排序：按“出现章节数”从多到少排序，找出最重要的概念
        # x[0] 是概念名, x[1] 是章节列表
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
            # 截断定义长度，节省 Token
            clean_def = definition[:100] + "..." if len(definition) > 100 else definition

            summary += f"- {name}: {clean_def}\n"
            count += 1

        return summary

    def save_memory(self, output_dir: Path):
        """
        将知识图谱保存为 JSON 文件，供后续可视化或检索使用
        """
        data = {
            "concepts": self.concepts,
            "relations": self.relations, # 预留
            "appearances": self.appearances
        }

        file_path = output_dir / "knowledge_graph.json"

        try:
            with open(file_path, "w", encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"💾 知识图谱数据已保存至: {file_path}")
        except Exception as e:
            print(f"❌ 保存知识图谱失败: {e}")