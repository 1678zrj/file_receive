from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.rag.splitters.base import BaseSplitter


class RecursiveSplitter(BaseSplitter):

    def __init__(
            self,
            chunk_size: int = 1024,
            chunk_overlap: int = 0
    ):
        super().__init__(chunk_size=chunk_size)
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
        if actual_overlap >= actual_size:
            raise ValueError(
                f"chunk_overlap ({actual_overlap}) must lower than chunk_size ({actual_size})"
            )
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=actual_size,
            chunk_overlap=actual_overlap
        )
        texts = text_splitter.split_text(text)
        return texts
