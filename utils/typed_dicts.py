"""This includes all typed dictionaries used by the product within multiple applications such as the states for Langgraph"""

class BaseAgentState(TypedDict):
    """Shared state fields that every ReAct agent inherits.

    Agent-specific states extend this with their own fields.
    """

    messages: Annotated[list[BaseMessage], operator.add]
    reflection_list: NotRequired[Annotated[list[ReflectionEntry], operator.add]]


