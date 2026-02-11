from typing import Dict, Any

from app.agent.prompts import ChatPrompt
from app.agent.states import NL2SQLState
from app.schemas.agent import SQLResult
from app.core import Singleton
from app.core.llm import llm


class SQLGenerator(Singleton):
    def __init__(self):
        self.structured_llm = llm.with_structured_output(SQLResult)

    def __call__(self, state: NL2SQLState) -> Dict[str, Any]:
        ir_ast = state.intent_parse_result.ir_ast.model_dump_json(indent=2)
        schemas = "\n\n".join(state.schemas)
        prompt_message = ChatPrompt.generate_prompt(schemas, ir_ast)
        result: SQLResult = self.structured_llm.invoke(prompt_message)
        return {"sql_result": result}
