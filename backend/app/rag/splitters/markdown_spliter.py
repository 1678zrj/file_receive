from langchain_text_splitters import MarkdownTextSplitter
from app.rag.splitters.base import BaseSplitter

class MarkdownSplitter(BaseSplitter):

    def __init__(
            self,
            chunk_size: int = 1024,
            chunk_overlap: int = 0
    ):
        super().__init__(chunk_size)
        self.chunk_overlap = chunk_overlap

    def split_text(
            self,
            text: str,
            chunk_size: int | None = None,
            chunk_overlap: int | None = None,
            **kwargs
    ) -> list[str]:
        actual_size = chunk_size if chunk_size is not None else self.chunk_size
        actual_overlap = chunk_overlap if chunk_overlap is not None else self.chunk_overlap
        markdown_splitter = MarkdownTextSplitter(
            chunk_size=actual_size,
            chunk_overlap=actual_overlap
        )
        texts = markdown_splitter.split_text(text)
        return texts

if __name__ == "__main__":
    from pathlib import Path
    markdown_splitter = MarkdownSplitter()
    file_path = Path(r"D:\mycode\python\file_receive\backend\record\AI\请求大模型响应报错处理策略.md")
    with open(file_path, mode='r', encoding='utf-8') as f:
        content = f.read()
    texts = markdown_splitter.split_text(content)
    for text in texts:
        print("====================================================")
        print(text)
        print("====================================================")
