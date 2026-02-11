from typing import Dict, Any

from langchain_core.messages import HumanMessage
from langgraph.types import interrupt

from app.agent.states import NL2SQLState
from app.core import Singleton


class FlowUp(Singleton):
    def __call__(self, state: NL2SQLState) -> Dict[str, Any]:
        user_reply = interrupt(state.intent_parse_result.flow_up_question)
        return {
            "messages": [HumanMessage(content=user_reply)]
        }
