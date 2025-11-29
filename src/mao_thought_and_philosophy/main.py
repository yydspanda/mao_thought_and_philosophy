"""

"""
# src/mao_thought_and_philosophy/main.py
from .config import setup_directories, validate_config
from .processing.workflow import run_analysis


def main():
    print("🚀 系统初始化...")

    # 1. 创建目录
    setup_directories()

    # 2. 校验配置 (如果有问题，这里就会报错停止，不会等到跑了一半才崩)
    try:
        validate_config()
        print("✅ 配置校验通过")
    except ValueError as e:
        print(e)
        return

    # 3. 运行主流程
    run_analysis()


if __name__ == "__main__":
    main()