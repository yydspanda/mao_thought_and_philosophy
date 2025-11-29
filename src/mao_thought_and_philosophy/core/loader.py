"""
这个模块负责把书变成 AI 能读懂的结构化对象，而不是一堆乱码。

"""
# src/mao_thought_and_philosophy/core/loader.py
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup


def read_epub_chapters(epub_path):
    book = epub.read_epub(epub_path)
    chapters = []

    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            text = soup.get_text(strip=True)
            # 简单的过滤，太短的章节可能是目录或版权页
            if len(text) > 500:
                chapters.append({
                    "id": item.get_name(),
                    "content": text
                })
    return chapters
