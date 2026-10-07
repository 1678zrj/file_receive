from langgraph.graph import StateGraph, START
from app.rag_agent.state import OverAllState
from app.rag_agent.call_model_node import router_after_agent, call_model
from app.rag_agent.call_tool_node import gate_dispatcher_node, interactive_node, read_batch_node, router_next_task

graph_builder = StateGraph(state_schema=OverAllState)


graph_builder.add_node("call_model", call_model)
graph_builder.add_node("gate_dispatcher_node", gate_dispatcher_node)
graph_builder.add_node("read_batch_node", read_batch_node)
graph_builder.add_node("interactive_node", interactive_node)
graph_builder.add_edge(START, "call_model")
graph_builder.add_conditional_edges("call_model", router_after_agent)
graph_builder.add_conditional_edges("gate_dispatcher_node", router_next_task)
graph_builder.add_conditional_edges("read_batch_node", router_next_task)
graph_builder.add_conditional_edges("interactive_node", router_next_task)