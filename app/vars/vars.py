from typing import Literal

FilterOp = Literal["AND", "OR", "NOT",
"=", "!=", "<", ">", "<=", ">=",
"IN", "NOT IN",
"BETWEEN", "IS NULL", "IS NOT NULL",
"LIKE", "ILIKE", "REGEXP",
"EXISTS", "NOT EXISTS",
"JSON_CONTAINS", "JSON_EXTRACT", "JSON_OVERLAPS"]

HUMAN_TYPE = "human"
SYSTEM_TYPE = "system"

ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"