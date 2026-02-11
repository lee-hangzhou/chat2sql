from typing import Dict, Any

from langchain_core.messages import AIMessage

from app.agent.prompts import ChatPrompt
from app.agent.states import NL2SQLState
from app.schemas.agent import IntentParseResult
from app.core import Singleton
from app.core.llm import llm
from app.vars.prompts import IR_AST_TAG


class IntentParse(Singleton):
    def __init__(self):
        self.structured_llm = llm.with_structured_output(IntentParseResult)

    @staticmethod
    def _get_existing_ir_ast(state: NL2SQLState) -> str | None:
        if state.intent_parse_result and state.intent_parse_result.ir_ast:
            return state.intent_parse_result.ir_ast.model_dump_json(indent=2)
        return None

    def __call__(self, state: NL2SQLState) -> Dict[str, Any]:
        existing_ir_ast = self._get_existing_ir_ast(state)
        schemas = "\n\n".join(state.schemas)

        params = {
            "messages": state.messages,
            "schemas": schemas,
        }
        if existing_ir_ast:
            params["ir_ast_tag"] = IR_AST_TAG
            params["existing_ir_ast"] = existing_ir_ast
        prompt_messages = ChatPrompt.intent_recognition_prompt(**params)

        result: IntentParseResult = self.structured_llm.invoke(prompt_messages)
        return_dict = dict()
        if result.need_flow_up and result.flow_up_question:
            return_dict["messages"] = [AIMessage(content=result.flow_up_question)]

        return_dict["intent_parse_result"] = result
        return return_dict
