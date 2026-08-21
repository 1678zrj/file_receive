import time

from app.rag.parsers.base import BaseParser
import anydoc
from pathlib import Path
from app.core.config import BASE_DIR

class DocxParser(BaseParser):

    def parse(self, file_bytes: bytes) -> str:
        """文档解析"""
        markdown = anydoc.to_markdown_bytes(file_bytes, format='docx')
        return markdown








if __name__ == "__main__":
    docx_parser = DocxParser()
    file_path = Path("D:/压裂/接口文档.docx")
    with open(file_path, "rb") as f:
        file_bytes = f.read()
    start = time.time()
    for i in range(1000):
        content = docx_parser.parse(file_bytes)
    end = time.time()
    print(content)
    print(f"耗时：{end - start}秒")
    new_file_path = BASE_DIR / "test.md"
    new_file_path.write_text(content, encoding='utf-8')