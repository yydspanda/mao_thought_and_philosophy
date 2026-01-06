# restore_old_format.py
import json
import os
import re
from pathlib import Path
from collections import defaultdict

# ======================= 用户配置 =======================
# ❗️ 请确保这个路径指向你想要清理的书籍的输出目录
BOOK_DIR = Path("output/毛泽东选集一至七卷") 
# ==========================================================

CHAPTERS_DIR = BOOK_DIR / "chapters"
JSON_PATH = BOOK_DIR / "knowledge_graph.json"

# 定义哪些字符是“好”的（旧格式包含，新格式没有）
# 我们的目标是删除不包含这些字符的重复项
GOOD_CHARS = {'《', '》', '“', '”', '"'}

def create_base_name(filename):
    """创建一个用于比较的“裸名”，即去掉所有特殊符号和后缀"""
    name_no_ext = filename.rsplit('.', 1)[0]
    return re.sub(r'[《》“”"]', '', name_no_ext)

def clean_duplicate_files():
    """扫描 chapters 目录，删除新的、不带符号的重复文件"""
    print(f"🧹 [1/3] 正在扫描目录: {CHAPTERS_DIR}")
    if not CHAPTERS_DIR.exists():
        print("❌ 错误: 找不到 chapters 目录，请检查 BOOK_DIR 配置。")
        return []

    # 1. 按“裸名”对所有文件进行分组
    grouped_files = defaultdict(list)
    for file_path in CHAPTERS_DIR.glob("*.md"):
        base_name = create_base_name(file_path.name)
        grouped_files[base_name].append(file_path)

    # 2. 找出重复组，并删除“坏”文件
    files_to_delete = []
    for base_name, file_list in grouped_files.items():
        if len(file_list) > 1:  # 这是一个重复组
            print(f"\n   发现重复组: {base_name}")
            for file_path in file_list:
                # 如果文件名中不包含任何“好”字符，那它就是新生成的“坏”文件
                if not any(char in file_path.name for char in GOOD_CHARS):
                    files_to_delete.append(file_path)
                    print(f"      - 标记删除: {file_path.name} (新格式)")
                else:
                    print(f"      - 保留: {file_path.name} (旧格式)")

    # 3. 执行删除
    deleted_filenames = []
    if not files_to_delete:
        print("✅ 没有发现需要清理的重复文件。")
        return []

    print("\n🗑️  开始执行删除...")
    for file_path in files_to_delete:
        try:
            deleted_filenames.append(file_path.name)
            os.remove(file_path)
            print(f"   - 已删除: {file_path.name}")
        except OSError as e:
            print(f"   - ❌ 删除失败: {file_path.name}, 错误: {e}")
    
    print(f"✅ 文件清理完毕，共删除 {len(deleted_filenames)} 个文件。")
    return deleted_filenames

def clean_json_memory(deleted_filenames):
    """读取 JSON 文件，清除所有与被删除文件相关的引用和概念"""
    print(f"\n🧠 [2/3] 正在清理知识图谱: {JSON_PATH}")
    if not deleted_filenames:
        print("✅ 无需清理知识图谱。")
        return
        
    if not JSON_PATH.exists():
        print("❌ 错误: 找不到 knowledge_graph.json 文件。")
        return

    # 将文件名转换为 JSON 中使用的 "link_name" (无后缀)
    purge_link_names = {name.rsplit('.', 1)[0] for name in deleted_filenames}
    
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    concepts = data.get("concepts", {})
    appearances = data.get("appearances", {})
    
    # 1. 清理出处 (appearances)
    concepts_to_fully_remove = set()
    for concept_name, links in appearances.items():
        # 过滤列表，只保留不该被删除的链接
        original_count = len(links)
        appearances[concept_name] = [link for link in links if link not in purge_link_names]
        
        if len(appearances[concept_name]) < original_count:
            print(f"   - 清理引用: 概念 [{concept_name}] 中移除了与新文件的关联。")

        # 2. 检查是否有概念变成了“孤儿”
        if not appearances[concept_name]:
            concepts_to_fully_remove.add(concept_name)
            print(f"      - 发现孤儿概念: [{concept_name}] 已没有任何引用，将被彻底删除。")

    # 3. 彻底删除孤儿概念
    for concept_name in concepts_to_fully_remove:
        if concept_name in appearances:
            del appearances[concept_name]
        if concept_name in concepts:
            del concepts[concept_name]
    
    # 4. 写回 JSON 文件
    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print("✅ 知识图谱清理完毕。")

def main():
    """主执行函数"""
    print("🚀 开始执行知识库回滚与清理程序...")
    
    # 第一步：清理文件
    deleted_files = clean_duplicate_files()
    
    # 第二步：清理JSON
    clean_json_memory(deleted_files)
    
    print("\n🎉 [3/3] 全部清理工作完成！")
    print("\n下一步建议:")
    print("1. 检查 `workflow.py` 中的 `sanitize_filename` 函数是否已恢复到旧版。")
    print("2. 重新运行你的主程序 `main.py`，它会自动跳过已存在的旧文件，并为你重新生成被删除的文件（这次会是带书名号的好版本）。")
    print("3. 最后，重新生成一次概念卡片以确保链接正确无误。")

if __name__ == "__main__":
    main()