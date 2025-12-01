import warnings

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub

from mao_thought_and_philosophy.config import ASSETS_DIR

# ebooklib 有时候会报一些不影响运行的 FutureWarnings，我们忽略它以保持控制台干净
warnings.filterwarnings("ignore", category=UserWarning, module='ebooklib')


def read_epub_chapters_common(epub_path):
    """
    读取 EPUB 文件并解析为章节列表。

    Args:
        epub_path (Path or str): epub 文件的路径

    Returns:
        list[dict]: 返回一个列表，每个元素是字典：
                    [
                        {"id": "chapter1.html", "content": "第一章的内容..."},
                        {"id": "chapter2.html", "content": "第二章的内容..."}
                    ]
    """

    # 1. 使用 ebooklib 打开电子书
    # 它会自动处理解压和文件索引
    try:
        book = epub.read_epub(epub_path)
    except Exception as e:
        print(f"❌ 无法打开电子书: {e}")
        return []

    chapters = []

    # 2. 遍历书中的每一个 "Item" (元素)
    # EPUB 里不仅有文字，还有图片(ITEM_IMAGE)、样式(ITEM_STYLE)等
    for item in book.get_items():

        # 3. 过滤：我们只关心 "文档" 类型 (即 HTML/XHTML 文本)
        if item.get_type() == ebooklib.ITEM_DOCUMENT:

            # 获取该文件的原始二进制内容 (bytes)
            raw_content = item.get_content()
            print(raw_content.decode('utf-8')[:500])

            # 4. 解析 HTML
            # 使用 BeautifulSoup 将乱糟糟的 HTML 标签结构化
            soup = BeautifulSoup(raw_content, 'html.parser')

            # --- 核心技术点 ---
            # get_text() 负责把 <p>Hello</p> 变成 "Hello"
            #
            # 参数 separator='\n\n':
            # 默认情况下，get_text会将所有文本粘在一起。
            # 这里我们要告诉它：每当遇到一个 HTML 标签结束（比如段落结束），
            # 插入两个换行符。这样能保留段落结构，而不是变成一坨文字墙。
            #
            # 参数 strip=True:
            # 去除每段文字首尾多余的空格。
            text_content = soup.get_text(separator='\n\n', strip=True)

            # 5. 降噪过滤
            # 很多 EPUB 会把目录、版权页、封面也当成独立的文档。
            # 这些内容通常很短（比如少于 300 字）。
            # 为了不浪费 Token 和分析时间，我们把这些非正文内容过滤掉。
            if len(text_content) > 300:
                # 获取文件名作为 ID，通常是 'chap01.xhtml' 这种格式
                # 后面 workflow 里会用它来做文件名
                chapter_id = item.get_name()

                chapters.append({
                    "id": chapter_id,
                    "content": text_content
                })

    return chapters


def read_epub_chapters_custom(epub_path):
    """
    读取 EPUB，智能提取标题，并防止标题在正文中重复出现。
    """
    try:
        book = epub.read_epub(epub_path)
    except Exception as e:
        print(f"❌ 无法打开电子书: {e}")
        return []

    chapters = []

    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            # 1. 创建 Soup 对象
            soup = BeautifulSoup(item.get_content(), 'html.parser')

            # --- 2. 优先提取并移除标题 (核心修改) ---
            extracted_title = None

            # 我们按照优先级查找标题标签
            # 这里的逻辑是：一旦找到了标题，记录下来，然后立马把它从 soup 里删掉！
            for tag in ['h1', 'h2', 'h3', 'title']:
                header_tag = soup.find(tag)
                if header_tag and header_tag.get_text(strip=True):
                    # A. 提取标题文本
                    extracted_title = header_tag.get_text(strip=True)

                    # B. 【关键步骤】从 HTML 树中彻底移除这个标签
                    # 这样后续 get_text() 就不会再包含这一行了
                    header_tag.decompose()

                    break  # 找到最高优先级的标题后就停止

            # 如果没找到 HTML 标题，用文件名做保底
            if not extracted_title:
                file_id = item.get_name()
                extracted_title = file_id.split('/')[-1].replace('.xhtml', '').replace('.html', '')

            # --- 3. 提取剩余的正文 ---
            # 此时 soup 里已经没有那个 h1/h2 标签了，所以 content 不会包含标题
            text_content = soup.get_text(separator='\n\n', strip=True)

            # 再次清洗：有时候 decompose 后开头会有很多空行
            text_content = text_content.strip()

            # --- 4. (兜底策略) 字符串去重 ---
            # 万一标题不是用 h标签 写的，而是加粗的 p 标签，上面的 decompose 没抓到。
            # 我们做一次字符串层面的检查：如果正文开头就是标题，把它切掉。
            if text_content.startswith(extracted_title):
                # 切片，去掉标题长度，再去掉可能紧跟的换行符
                text_content = text_content[len(extracted_title):].strip()

            # 过滤过短章节
            if len(text_content) > 300:
                chapters.append({
                    "id": item.get_name(),
                    "title": extracted_title,
                    "content": text_content
                })

    return [{'id': item.get('id'), 'title': item.get('title'), 'content': item.get('content')} for index, item in enumerate(chapters[3:-1])]


# --- 单元测试代码 ---
# 如果你直接运行 python loader.py，会执行下面这段，方便测试逻辑是否正确
if __name__ == "__main__":
    epub_path = ASSETS_DIR / "毛主席教我们当省委书记.epub"
    if not epub_path.exists():
        print(f"❌ 错误：在 {ASSETS_DIR} 下找不到电子书文件！")

    print(f"正在读取: {epub_path}")
    result = read_epub_chapters_custom(epub_path)

    print(f"共提取到 {len(result)} 个章节")
    if len(result) > 0:
        print("--- 第一章预览 (前200字) ---")
        print(result[3]['content'][:200])
        print("---------------------------")
