import time

from app.rag.parsers.base import BaseParser
import anydoc
from pathlib import Path
from app.core.config import BASE_DIR

class MarkdownParser(BaseParser):

    def parse(self, file_bytes: bytes) -> str:
        """文档解析"""
        return file_bytes.decode(encoding='utf-8-sig')


if __name__ == "__main__":
    markdown_parser = MarkdownParser()
    file_path = Path(r"D:\mycode\python\file_receive\backend\record\AI\请求大模型响应报错处理策略.md")
    with open(file_path, "rb") as f:
        file_bytes = f.read()
    start = time.time()
    content = markdown_parser.parse(file_bytes)
    end = time.time()
    print(content)
    print(f"耗时：{end - start}秒")
    new_file_path = BASE_DIR / "test.md"
    new_file_path.write_text(content, encoding='utf-8')