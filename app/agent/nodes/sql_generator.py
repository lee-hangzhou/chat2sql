from typing import Any, Dict

from app.agent.prompts import ChatPrompt
from app.agent.states import NL2SQLState
from app.schemas.agent import AgentErrorCode, SQLResult
from app.core.llm import llm
from app.vars.prompts import VALIDATION_FEEDBACK_TAG


class SQLGenerator:
    def __init__(self):
        self.structured_llm = llm.with_structured_output(SQLResult)

    @staticmethod
    def _get_validation_feedback(state: NL2SQLState) -> str | None:
        """从校验结果中提取失败原因，用于指导 SQL 重新生成"""
        if state.syntax_result and not state.syntax_result.is_ok:
            return state.syntax_result.error
        if state.explain_error:
            return state.explain_error
        return None

    async def __call__(self, state: NL2SQLState) -> Dict[str, Any]:
        if not state.intent_parse_result or not state.intent_parse_result.ir_ast:
            return {
                "is_success": False,
                "error_code": AgentErrorCode.NO_IR_AST,
                "error_message": AgentErrorCode.NO_IR_AST.message,
            }

        ir_ast = state.intent_parse_result.ir_ast.model_dump_json(indent=2)
        schemas = "\n\n".join(state.schemas)
        validation_feedback = self._get_validation_feedback(state)

        params: Dict[str, Any] = {
            "schemas": schemas,
            "ir_ast": ir_ast,
            "validation_feedback_tag": "",
            "validation_feedback": "",
        }
        if validation_feedback:
            params["validation_feedback_tag"] = VALIDATION_FEEDBACK_TAG
            params["validation_feedback"] = validation_feedback

        prompt_message = ChatPrompt.generate_prompt(**params)

        try:
            result: SQLResult = await self.structured_llm.ainvoke(prompt_message)
        except Exception as e:
            return {
                "is_success": False,
                "error_code": AgentErrorCode.LLM_ERROR,
                "error_message": str(e),
            }

        return {"sql_result": result}
