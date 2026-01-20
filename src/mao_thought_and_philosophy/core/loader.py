import logging
import re
import warnings
from importlib.resources import as_file
from typing import Any, Dict, List, Optional, Set

import ebooklib  # type: ignore
from bs4 import BeautifulSoup
from ebooklib import epub

# 忽略 ebooklib 的未来警告
from mao_thought_and_philosophy.config import ASSETS_DIR

# ebooklib 有时候会报一些不影响运行的 FutureWarnings，我们忽略它以保持控制台干净
warnings.filterwarnings("ignore", category=UserWarning, module="ebooklib")


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

    chapters: List[Dict[str, str]] = []

    # 2. 遍历书中的每一个 "Item" (元素)
    # EPUB 里不仅有文字，还有图片(ITEM_IMAGE)、样式(ITEM_STYLE)等

    # items = book.get_items()
    # items = [item for item in items]
    # for item in items[:10]:
    #     raw_content = item.get_content()
    #     print(raw_content.decode('utf-8'))

    for item in book.get_items():
        # 3. 过滤：我们只关心 "文档" 类型 (即 HTML/XHTML 文本)
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            # 获取该文件的原始二进制内容 (bytes)
            raw_content = item.get_content()
            # 4. 解析 HTML
            # 使用 BeautifulSoup 将乱糟糟的 HTML 标签结构化
            soup = BeautifulSoup(raw_content, "html.parser")

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
            text_content = soup.get_text(separator="\n\n", strip=True)

            # 5. 降噪过滤
            # 很多 EPUB 会把目录、版权页、封面也当成独立的文档。
            # 这些内容通常很短（比如少于 300 字）。
            # 为了不浪费 Token 和分析时间，我们把这些非正文内容过滤掉。
            if len(text_content) > 300:
                # 获取文件名作为 ID，通常是 'chap01.xhtml' 这种格式
                # 后面 workflow 里会用它来做文件名
                chapter_id = item.get_name()

                chapters.append({"id": chapter_id, "content": text_content})

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

    chapters: List[Dict[str, Any]] = []

    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            # 1. 创建 Soup 对象
            soup = BeautifulSoup(item.get_content(), "html.parser")

            # --- 2. 优先提取并移除标题 (核心修改) ---
            extracted_title = None

            # 我们按照优先级查找标题标签
            # 这里的逻辑是：一旦找到了标题，记录下来，然后立马把它从 soup 里删掉！
            for tag in ["h1", "h2", "h3", "title"]:
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
                extracted_title = (
                    file_id.split("/")[-1].replace(".xhtml", "").replace(".html", "")
                )

            # --- 3. 提取剩余的正文 ---
            # 此时 soup 里已经没有那个 h1/h2 标签了，所以 content 不会包含标题
            text_content = soup.get_text(separator="\n\n", strip=True)

            # 再次清洗：有时候 decompose 后开头会有很多空行
            text_content = text_content.strip()

            # --- 4. (兜底策略) 字符串去重 ---
            # 万一标题不是用 h标签 写的，而是加粗的 p 标签，上面的 decompose 没抓到。
            # 我们做一次字符串层面的检查：如果正文开头就是标题，把它切掉。
            if text_content.startswith(extracted_title):
                # 切片，去掉标题长度，再去掉可能紧跟的换行符
                text_content = text_content[len(extracted_title) :].strip()

            # 过滤过短章节
            if len(text_content) > 300:
                chapters.append(
                    {
                        "id": item.get_name(),
                        "title": extracted_title,
                        "content": text_content,
                    }
                )

    return [
        {
            "id": item.get("id"),
            "title": item.get("title"),
            "content": item.get("content"),
        }
        for index, item in enumerate(chapters[3:-1])
    ]


def _extract_date_from_soup(soup):
    """
    特化功能：从 HTML 中提取（一九xx年x月x日）格式的日期。
    观察你的 XML，日期通常在 <p class="a0"><span class="f2">...</span></p> 中
    """
    # 尝试找包含年份的段落
    # 正则匹配：以括号开头，包含“年”，以括号结尾
    date_pattern = re.compile(r"^[（(].*?年.*?[）)]$")

    # 优先找 class="a0" 的 p 标签 (根据你提供的 CSS，a0 是居中且常用于日期)
    for p in soup.find_all("p", class_="a0"):
        text = p.get_text(strip=True)
        if date_pattern.match(text):
            return (
                text.replace("（", "")
                .replace("）", "")
                .replace("(", "")
                .replace(")", "")
            )

    # 如果没找到，扫一遍前 5 个段落
    for p in soup.find_all("p", limit=5):
        text = p.get_text(strip=True)
        if date_pattern.match(text):
            return (
                text.replace("（", "")
                .replace("）", "")
                .replace("(", "")
                .replace(")", "")
            )

    return "日期未知"


# 预编译正则，提升效率
# 匹配：(一九二五年十二月一日) 或 （一九二六年三月）
DATE_PATTERN = re.compile(r"^[（(].*?年.*?[）)]$")

# 默认排除的标题集合
DEFAULT_EXCLUDED_TITLES = {
    "第二版出版说明",
    "本书出版的说明",
    "出版说明",
    "静火有言",
    "目　录",
    "版本信息",
    "版权页",
    "封面",
}


class MaoEpubLoader:
    """
    专门针对《毛泽东选集》类结构 EPUB 的提取器。
    特点：支持卷/时期层级提取，智能日期识别。
    """

    def __init__(self, epub_path: str, excluded_titles: Optional[Set[str]] = None):
        self.epub_path = epub_path
        self.excluded_titles = (
            excluded_titles if excluded_titles else DEFAULT_EXCLUDED_TITLES
        )
        self.book: Optional[epub.EpubBook] = None
        self.chapters: List[Dict[str, Any]] = []

    def load(self) -> List[Dict[str, Any]]:
        """主入口：读取并解析 EPUB"""
        try:
            self.book = epub.read_epub(self.epub_path)
        except Exception as e:
            logging.error(f"❌ 无法打开电子书 {self.epub_path}: {e}")
            return []

        if self.book is None:
            return []

        # 从目录树根节点开始递归
        self._walk_toc(self.book.toc, hierarchy=[])
        return self.chapters

    def _walk_toc(self, items: List[Any], hierarchy: List[str]):
        """
        递归遍历目录树 (Navigation Logic)
        """
        for item in items:
            # 1. 节点是目录容器 (Section) -> Tuple(Section, Children)
            if isinstance(item, (tuple, list)):
                section_obj, children = item
                title = (
                    section_obj.title
                    if hasattr(section_obj, "title")
                    else str(section_obj)
                )
                # 递归进入下一层，层级列表 +1
                self._walk_toc(children, hierarchy + [title])

            # 2. 节点是文章链接 (Link)
            elif isinstance(item, epub.Link):
                self._process_link_item(item, hierarchy)

    def _process_link_item(self, link: epub.Link, hierarchy: List[str]):
        """
        处理单个文章节点 (Extraction Logic)
        """
        title = link.title
        if title in self.excluded_titles:
            return

        # 获取文件内容
        href = link.href.split("#")[0]
        try:
            if self.book is None:  # Guard for mypy
                return
            item = self.book.get_item_with_href(href)
            if not item:
                return
        except KeyError:
            return  # 甚至可以 log warning

        # 解析 HTML
        soup = BeautifulSoup(item.get_content(), "html.parser")

        # --- 提取元数据 ---
        publish_date = self._extract_date(soup)

        # --- 清洗 ---
        self._clean_soup(soup, title)

        # --- 提取纯文本 ---
        content = soup.get_text(separator="\n\n", strip=True)

        # --- 后处理文本 (去除残留日期等) ---
        content = self._post_process_content(content, publish_date, title)

        # 只有当内容长度足够时才保留（过滤掉只有标题的空页）
        if len(content) < 50:
            return

        # 解析层级 (卷/时期)
        volume = hierarchy[0] if len(hierarchy) >= 1 else "未分类"
        period = hierarchy[1] if len(hierarchy) >= 2 else "未分类"

        self.chapters.append(
            {
                "id": href,
                "title": title,
                "volume": volume,
                "period": period,
                "date": publish_date,
                "content": content,
            }
        )

    def _extract_date(self, soup: BeautifulSoup) -> str:
        """
        特化功能：从 HTML 中提取（一九xx年x月x日）格式的日期。
        观察你的 XML，日期通常在 <p class="a0"><span class="f2">...</span></p> 中
        """
        # 尝试找包含年份的段落
        # 正则匹配：以括号开头，包含“年”，以括号结尾
        # date_pattern = re.compile(r"^[（(].*?年.*?[）)]$")

        # 优先找 class="a0" 的 p 标签 (根据你提供的 CSS，a0 是居中且常用于日期)
        for p in soup.find_all("p", class_="a0"):
            text = p.get_text(strip=True)
            if DATE_PATTERN.match(text):
                return (
                    text.replace("（", "")
                    .replace("）", "")
                    .replace("(", "")
                    .replace(")", "")
                )

        # 如果没找到，扫一遍前 5 个段落
        for p in soup.find_all("p", limit=5):
            text = p.get_text(strip=True)
            if DATE_PATTERN.match(text):
                return (
                    text.replace("（", "")
                    .replace("）", "")
                    .replace("(", "")
                    .replace(")", "")
                )

        return "日期未知"

    def _clean_soup(self, soup: BeautifulSoup, title: str):
        """
        在转文本前，从 DOM 树中移除干扰元素。
        """
        # 1. 移除标题标签
        for header in soup.find_all(["h1", "h2", "h3", "title"]):
            header.decompose()

        # 2. 移除可能的 CSS 隐藏元素或页码
        for tag in soup.find_all(class_=["page-number", "hidden"]):
            tag.decompose()

    def _post_process_content(self, content: str, date: str, title: str) -> str:
        """
        对提取后的纯文本进行修剪
        """
        # 如果正文开头包含了标题，去除之
        if content.startswith(title):
            content = content[len(title) :].lstrip()

        # 如果正文开头包含了日期，去除之
        # 注意：这里要小心，别把正文里的日期误删，通常日期在最前面
        if date != "日期未知":
            # 构造可能的开头格式
            candidates = [date, f"（{date}）", f"({date})"]
            for cand in candidates:
                if content.startswith(cand):
                    content = content[len(cand) :].lstrip()
                    break

        return content


# ---------------- 调用示例 ----------------


def read_epub_chapters_mao_selected(epub_path, excluded_titles=DEFAULT_EXCLUDED_TITLES):
    """
    保持原有的函数签名，作为兼容层
    """
    loader = MaoEpubLoader(epub_path, excluded_titles)
    return loader.load()


if __name__ == "__main__":
    epub_path_traversable = ASSETS_DIR / "毛泽东选集一至七卷.epub"
    with as_file(epub_path_traversable) as epub_path:
        if epub_path.exists():
            chapters = read_epub_chapters_mao_selected(epub_path)
            print(f"✅ 共提取 {len(chapters)} 章")

            if chapters:
                sample = chapters[10] if len(chapters) > 10 else chapters[0]
                print(f"标题: {sample['title']}")
                print(f"日期: {sample['date']}")
                print(f"层级: {sample['volume']} / {sample['period']}")
                print(f"内容预览: {sample['content'][:80]}...")
