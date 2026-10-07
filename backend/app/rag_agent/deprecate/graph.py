from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, START, END
from app.rag_agent.deprecate.call_tool_node import tool_node
# 导入上一节中定义的工具
from app.rag_agent.deprecate.state import OverAllState
from app.rag_agent.deprecate.call_model_node import call_model













async def should_continue(state: OverAllState):
    messages = state["messages"]
    last_message: AIMessage = messages[-1]
    if last_message.tool_calls:
        return "tool_node"
    return END


graph_builder = StateGraph(state_schema=OverAllState)
graph_builder.add_node("call_model", call_model)
graph_builder.add_node("tool_node", tool_node)
graph_builder.add_edge(START, "call_model")
graph_builder.add_edge("tool_node", "call_model")
graph_builder.add_conditional_edges("call_model", should_continue)

