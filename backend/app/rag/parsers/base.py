from abc import ABC, abstractmethod




class BaseParser(ABC):

    @abstractmethod
    def parse(self, file_bytes) -> str:
        """文档解析"""

        pass