import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langgraph")

from langgraph.graph import StateGraph, START, END
from APP.agents.state import AgentState
from APP.agents.profile_agent import extract_profile_node
from APP.agents.finder_agent import find_opportunities_node
from APP.agents.tailor_agent import tailor_application_node

def build_graph():
    """
    Agent 4: Orchestrator that wires the agents together.
    """
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("profile_agent", extract_profile_node)
    workflow.add_node("finder_agent", find_opportunities_node)
    workflow.add_node("tailor_agent", tailor_application_node)
    
    # Add edges
    workflow.add_edge(START, "profile_agent")
    
    # Simple routing logic: if error, stop. Else, continue.
    def check_error(state: AgentState):
        if state.get("error"):
            return END
        return "finder_agent"
        
    workflow.add_conditional_edges("profile_agent", check_error)
    
    def check_error_finder(state: AgentState):
        if state.get("error"):
            return END
        return "tailor_agent"
        
    workflow.add_conditional_edges("finder_agent", check_error_finder)
    
    workflow.add_edge("tailor_agent", END)
    
    # Compile graph
    app = workflow.compile()
    return app

# The compiled graph instance
copilot_graph = build_graph()
