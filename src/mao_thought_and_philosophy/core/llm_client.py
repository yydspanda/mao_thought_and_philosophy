import re
from typing import Any, Dict

from json_repair import repair_json  # 【新增】引入修复库
from openai import OpenAI

from ..config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


def _clean_json_string(json_str: str) -> str:
    """清洗 JSON 字符串，移除 Markdown 代码块标记"""
    pattern = r"^```(?:json)?\s*(.*?)\s*```$"
    match = re.search(pattern, json_str, re.DOTALL)
    if match:
        return match.group(1)
    return json_str.strip()


def call_llm_json(system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    """
    调用大模型并强制返回 Python 字典 (JSON)。
    集成 json_repair 以增强对大模型输出格式错误的容错能力。
    """
    # 在这里保留简单的防御性检查
    if not LLM_API_KEY:
        raise ValueError("LLM_API_KEY 未配置，请检查 .env 文件")

    # 直接使用 config 中导入的变量
    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

    content: str = ""  # 初始化变量，防止在 try 块之前报错导致 except 访问不到

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            # 强制模型尝试输出 JSON 结构
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        raw_content = response.choices[0].message.content
        content = raw_content if raw_content is not None else ""
        cleaned_content = _clean_json_string(content)

        # return_objects=True 表示直接返回 Python 字典/列表
        # 它可以自动修复：未转义的引号、缺少的闭合括号、多余的逗号等
        parsed_data = repair_json(cleaned_content, return_objects=True)

        if not isinstance(parsed_data, dict):
            raise TypeError(
                f"LLM did not return a JSON object as expected. Got type {type(parsed_data)}."
            )

        return parsed_data

    except Exception as e:
        print(f"\n❌ API 调用或 JSON 解析错误: {str(e)}")

        # 【新增】打印导致错误的原始内容片段，方便调试
        print("🔍 导致错误的原始内容 (前500字符):")
        print(content[:500] + "...")

        # 抛出异常让 workflow 处理
        raise e


if __name__ == "__main__":
    # 测试代码：修改为明确要求 JSON 的提示词，否则 response_format 可能报错
    sys_prompt = "你是一个助手，请务必只输出 JSON 格式。"
    user_prompt = "和大家打个美国式的招呼，返回字段 {'greeting': '内容'}"

    try:
        result = call_llm_json(sys_prompt, user_prompt)
        print("测试成功:", result)
    except Exception as e:
        print("测试失败:", e)
