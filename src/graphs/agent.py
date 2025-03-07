from langgraph.prebuilt import create_react_agent
from langmem import create_manage_memory_tool, create_search_memory_tool


my_agent = create_react_agent(
    "openai:o3-mini",
    tools=[
        create_manage_memory_tool("memories"),
        create_search_memory_tool("memories"),
    ],
)
