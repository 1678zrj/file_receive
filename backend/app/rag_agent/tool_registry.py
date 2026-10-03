from langchain_core.tools import BaseTool
from app.rag_agent.schema import UserRole
from app.rag_agent.tools import search, ask_user_question


class ToolRegistry:
    def __init__(self, tools: list[BaseTool]):
        self._tools: list[BaseTool] = tools
        self._tools_handler: dict[str, BaseTool] = {}
        self._role_tools_handler_dict: dict[int, dict[str, BaseTool]] = {
            role.value: {}
            for role in UserRole
        }
        self._init_tools()

    def _init_tools(self):
        for tool in self._tools:
            self._tools_handler[tool.name] = tool
            if tool.metadata:
                allowed_roles = tool.metadata.get("allowed_roles", [])
                for allowed_role in allowed_roles:
                    self._role_tools_handler_dict[allowed_role][tool.name] = tool

    def get_tool_by_name(self, tool_name: str) -> BaseTool | None:
        """
        根据工具名获取对应的工具
        面向的是系统的所有工具集
        """
        return self._tools_handler.get(tool_name)

    def get_tool_by_name_and_role(self, tool_name: str, role: int) -> BaseTool | None:
        """
        根据工具名和角色权限获取对应的工具
        需要工具名和角色权限都符合对应的工具
        """
        return self._role_tools_handler_dict.get(role, {}).get(tool_name)

    def get_role_tools_handler(self, role: int) -> dict[str, BaseTool]:
        """
        根据角色获取可使用的工具字典
        工具字典中是工具名及其对应工具
        """
        return self._role_tools_handler_dict.get(role, {})

    def get_role_tools(self, role: int) -> list[BaseTool]:
        """
        根据角色获取可使用的工具列表
        """
        return list(self._role_tools_handler_dict.get(role, {}).values())


tools = [search, ask_user_question]
tool_registry = ToolRegistry(tools)

if __name__ == "__main__":
    print(search.metadata)
    print(ask_user_question.metadata)
    print(tool_registry.get_tool_by_name(search.name))
    print(tool_registry.get_role_tools_handler(UserRole.STUDENT.value))
    print(tool_registry.get_tool_by_name_and_role(search.name, UserRole.STUDENT.value))
    print(tool_registry.get_role_tools(UserRole.STUDENT.value))