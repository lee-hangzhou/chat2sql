from typing import Any, Dict

from langchain_core.messages import AIMessage

from app.agent.prompts import ChatPrompt
from app.agent.states import NL2SQLState
from app.schemas.agent import AgentErrorCode, IntentParseResult
from app.core.llm import llm
from app.vars.prompts import IR_AST_TAG, PERFORMANCE_FEEDBACK_TAG


class IntentParse:
    def __init__(self):
        self.structured_llm = llm.with_structured_output(IntentParseResult)

    @staticmethod
    def _get_existing_ir_ast(state: NL2SQLState) -> str | None:
        if state.intent_parse_result and state.intent_parse_result.ir_ast:
            return state.intent_parse_result.ir_ast.model_dump_json(indent=2)
        return None

    @staticmethod
    def _get_performance_feedback(state: NL2SQLState) -> str | None:
        if state.performance_result and not state.performance_result.is_ok:
            return "; ".join(state.performance_result.issues)
        return None

    async def __call__(self, state: NL2SQLState) -> Dict[str, Any]:
        if state.is_success is False:
            return {}

        existing_ir_ast = self._get_existing_ir_ast(state)
        performance_feedback = self._get_performance_feedback(state)
        schemas = "\n\n".join(state.schemas)

        params: Dict[str, Any] = {
            "messages": state.messages,
            "schemas": schemas,
            "ir_ast_tag": "",
            "existing_ir_ast": "",
            "performance_feedback_tag": "",
            "performance_feedback": "",
        }
        if existing_ir_ast:
            params["ir_ast_tag"] = IR_AST_TAG
            params["existing_ir_ast"] = existing_ir_ast
        if performance_feedback:
            params["performance_feedback_tag"] = PERFORMANCE_FEEDBACK_TAG
            params["performance_feedback"] = performance_feedback
        prompt_messages = ChatPrompt.intent_recognition_prompt(**params)

        try:
            result: IntentParseResult = await self.structured_llm.ainvoke(prompt_messages)
        except Exception as e:
            return {
                "is_success": False,
                "error_code": AgentErrorCode.LLM_ERROR,
                "error_message": str(e),
            }

        return_dict: Dict[str, Any] = {"intent_parse_result": result}
        if result.need_follow_up and result.follow_up_question:
            return_dict["messages"] = [AIMessage(content=result.follow_up_question)]

        return return_dict
