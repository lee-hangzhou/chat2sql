import re
from typing import Optional, Type

from tortoise.models import Model

_ORDER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


def parse_order_string(order: str, model: Type[Model]) -> Optional[str]:
    """Parse order string for Tortoise ORM. Format: +field or -field."""
    if not order:
        return None

    s = order.strip()
    if len(s) < 2 or s[0] not in "+-":
        return None

    field = s[1:]
    if not _ORDER_RE.fullmatch(field):
        return None

    if field in ("id", "pk"):
        field = model._meta.pk_attr

    if field not in model._meta.db_fields:
        return None

    return field if s[0] == "+" else f"-{field}"
