"""
config: 项目目录配置与环境变量管理
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 使用 importlib.resources (Python 3.9+)
if sys.version_info < (3, 9):
    from importlib_resources import files
else:
    from importlib.resources import files

# --- 1. 目录定位 ---

# 定位工作区 (Current Working Directory)
# 假设用户的终端是在项目根目录下运行的 (即包含 .env 的那个目录)
BASE_WORK_DIR = Path.cwd()

# 定位包内资源 (Assets)
ASSETS_DIR = files("mao_thought_and_philosophy") / "assets"

# 定义输出与日志目录
OUTPUT_DIR = BASE_WORK_DIR / "output"
LOG_DIR = BASE_WORK_DIR / "log"

# --- 2. 加载环境变量 (.env) ---

# 显式指定 .env 文件的路径在工作区根目录下
ENV_PATH = BASE_WORK_DIR / ".env"

# 加载 .env 文件
# override=True 表示如果有同名变量，优先使用 .env 中的值覆盖系统环境变量
# if_exists=False (默认) 如果文件不存在，不会报错，但我们在下面会做检查
load_result = load_dotenv(dotenv_path=ENV_PATH, override=True)

if not load_result:
    # 这是一个非阻塞警告，你也可以选择在这里 raise Exception 强制退出
    print(f"⚠️  警告: 在 {BASE_WORK_DIR} 下未找到 .env 文件，将尝试使用系统环境变量。")

# --- 3. 导出配置变量 ---

# 将环境变量读取到 Python 变量中，供其他模块直接 import 使用
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")

# --- 4. 辅助函数 ---

def setup_directories():
    """确保输出目录存在"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

def validate_config():
    """
    检查关键配置是否存在，建议在 main.py 启动时调用
    """
    if not LLM_API_KEY:
        raise ValueError(
            f"❌ 未找到 LLM_API_KEY！\n"
            f"请确保在 {ENV_PATH} 文件中配置了该变量。"
        )