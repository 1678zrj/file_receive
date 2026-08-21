from abc import ABC, abstractmethod

class LifecycleComponent(ABC):

    async def startup(self) -> None:
        """初始化连接客户端"""
        pass

    async def shutdown(self) -> None:
        """释放网络连接与资源"""
        pass