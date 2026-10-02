from langgraph.graph import StateGraph
from app.rag_agent.state2 import OverAllState
from app.rag_agent.call_model_node2 import router_after_agent
from app.rag_agent.call_tool_node2 import gate_dispatcher_node





graph_builder = StateGraph(state_schema=OverAllState)
graph_builder.add_node("router_after_agent", router_after_agent)
graph_builder.add_node("gate_dispatcher_node", gate_dispatcher_node)

