from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages


class OverAllState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
