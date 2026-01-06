import argparse
import sys
from .config import setup_directories, validate_config, ASSETS_DIR
from .processing.workflow import run_analysis


def main():
    # 1. 解析命令行参数
    parser = argparse.ArgumentParser(description="Mao Thought Knowledge Base Generator")
    parser.add_argument(
        "--file", "-f",
        type=str,
        default="毛泽东选集一至七卷.epub",
        help="assets 目录下的 epub 文件名 (例如: my_book.epub)"
    )
    args = parser.parse_args()

    print("🚀 系统初始化...")
    setup_directories()

    try:
        validate_config()
    except ValueError as e:
        print(e)
        return

    # 检查文件是否存在
    target_file = ASSETS_DIR / args.file
    if not target_file.exists():
        print(f"❌ 错误：在 {ASSETS_DIR} 下未找到文件 '{args.file}'")
        print(f"📂 可用文件: {[f.name for f in ASSETS_DIR.glob('*.epub')]}")
        return

    # 2. 传入文件名运行
    run_analysis(epub_filename=args.file)


if __name__ == "__main__":
    main()
