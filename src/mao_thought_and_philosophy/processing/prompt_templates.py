"""
普通的 Prompt 只能写摘要，高级的 Prompt 要求 Json 结构化输出 并且进行 双向链接思考。

"""
# src/mao_thought_and_philosophy/processing/prompt_templates.py

ANALYSIS_SYSTEM_PROMPT = """
你是一位精通马克思列宁主义哲学和中国现代史的政治理论家。
你的任务是深度解读《毛主席教我们当省委书记》的章节。

不要进行平铺直叙的总结，必须输出结构化的深度分析。
必须关注概念的**历史脉络**和**逻辑关联**。

请以 JSON 格式输出，包含以下字段：
1. "summary": "本章核心思想的深度总结（300字以内）"
2. "key_concepts": [{"name": "概念名", "definition": "本章中的具体定义"}]
3. "connections": "本章内容与'已知概念库'中的旧概念有什么联系？（例如：反驳了...，继承了...，具体化了...）"
4. "reflection": "本章对当前时代的启示（哲学层面）"
"""

def get_user_prompt(text, context_memory):
    return f"""
{context_memory}

---
【当前章节原文】
{text[:3000]}... (截取部分以防超长)
---

请基于【已知概念库】和【当前章节原文】，进行深度解读。
如果原文中提到了之前出现过的概念，请务必指出它在本书逻辑中的演变。
"""