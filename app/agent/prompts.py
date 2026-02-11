from typing import List, Optional

from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.core import Singleton
from app.vars.prompts import INTENT_RECOGNITION_SYSTEM_PROMPT, INTENT_RECOGNITION_HUMAN_PROMPT, \
    GENERATE_SQL_SYSTEM_PROMPT, GENERATE_SQL_HUMAN_PROMPT
from app.vars.vars import HUMAN_TYPE, SYSTEM_TYPE


class ChatPrompt(Singleton):

    @classmethod
    def intent_recognition_prompt(
            cls, **kwargs
    ) -> List[BaseMessage]:
        template = ChatPromptTemplate.from_messages([
            (SYSTEM_TYPE, INTENT_RECOGNITION_SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="messages"),
            (HUMAN_TYPE, INTENT_RECOGNITION_HUMAN_PROMPT)
        ])

        return template.format_messages(**kwargs)

    @classmethod
    def generate_prompt(cls, schemas: str, ir_ast: str) -> List[BaseMessage]:
        template = ChatPromptTemplate.from_messages([
            (SYSTEM_TYPE, GENERATE_SQL_SYSTEM_PROMPT),
            (HUMAN_TYPE, GENERATE_SQL_HUMAN_PROMPT)
        ])
        return template.format_messages(schemas=schemas, ir_ast=ir_ast)
