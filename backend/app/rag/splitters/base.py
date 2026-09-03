from abc import ABC, abstractmethod


class BaseSplitter(ABC):

    def __init__(self, chunk_size: int = 1024):
        self.chunk_size = chunk_size


    @abstractmethod
    def split_text(
            self,
            text: str,
            chunk_size: int | None = None,
            **kwargs
    ) -> list[str]:
        """将完整的文档切分成多个文本块"""
        pass