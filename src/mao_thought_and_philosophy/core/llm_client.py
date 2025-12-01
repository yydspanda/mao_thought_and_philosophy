# src/mao_thought_and_philosophy/core/llm_client.py
import json
import re
from openai import OpenAI

from ..config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


def _clean_json_string(json_str: str) -> str:
    """清洗 JSON 字符串"""
    pattern = r"^```(?:json)?\s*(.*?)\s*```$"
    match = re.search(pattern, json_str, re.DOTALL)
    if match:
        return match.group(1)
    return json_str.strip()


def call_llm_json(system_prompt: str, user_prompt: str) -> dict:
    """
    调用大模型并强制返回 Python 字典 (JSON)。
    """
    # 在这里保留简单的防御性检查
    if not LLM_API_KEY:
        raise ValueError("LLM_API_KEY 未配置，请检查 .env 文件")

    # 直接使用 config 中导入的变量
    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,  # 使用 config 中的变量
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        content = response.choices[0].message.content
        cleaned_content = _clean_json_string(content)
        parsed_data = json.loads(cleaned_content)
        return parsed_data

    except Exception as e:
        print(f"❌ API 调用错误: {str(e)}")
        # 抛出异常让上层 workflow 处理，或者返回默认空值
        raise e


if __name__ == '__main__':
    result = call_llm_json("和大家打个美国式的招呼", "你好")
    #{'greeting': "Hey, what's up?"}
    print(result)
