from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import OperationalError


class ExplainAnalysis(BaseModel):
    """方言无关的 EXPLAIN 分析结果"""

    cost: int = Field(..., description="预估开销，根据方言自行定义")
    issues: list[str] = Field(default_factory=list, description="检测到的性能问题")
    raw: str = Field(default="", description="原始 EXPLAIN 输出，用于日志和 LLM 反馈")


class DialectStrategy(ABC):
    """SQL 方言策略抽象基类，所有方言相关行为由子类实现"""

    @property
    @abstractmethod
    def name(self) -> str:
        """人类可读方言名，注入到 prompt 中"""

    @property
    @abstractmethod
    def sqlglot_dialect(self) -> str:
        """sqlglot 方言标识符"""

    @abstractmethod
    def is_system_error(self, exc: OperationalError) -> bool:
        """判断是否为系统级错误，需上抛而非包装为校验失败"""

    @abstractmethod
    def build_explain_sql(self, sql: str) -> str:
        """根据方言构建 EXPLAIN 语句"""

    @abstractmethod
    def parse_explain(self, rows: list[dict], max_rows: int) -> ExplainAnalysis:
        """解析 EXPLAIN 结果行，返回方言无关的分析结果"""

    @staticmethod
    def _extract_raw_text(rows: list[dict]) -> str:
        lines: list[str] = []
        for row in rows:
            lines.extend(str(v) for v in row.values())
        return "\n".join(lines)

    @staticmethod
    def _extract_dbapi_error_code(exc: OperationalError) -> Optional[int]:
        """从 SQLAlchemy OperationalError 的底层 DBAPI 异常中提取数字错误码"""
        orig = getattr(exc, "orig", None)
        if orig is not None and hasattr(orig, "args") and orig.args:
            first = orig.args[0]
            if isinstance(first, int):
                return first
        return None


class _MySQLExplainRow(BaseModel):
    """MySQL EXPLAIN 单行解析模型"""

    model_config = ConfigDict(populate_by_name=True)

    table: Optional[str] = None
    join_type: Optional[str] = Field(default=None, alias="type")
    rows: int = 0
    extra: str = ""


class MySQLDialect(DialectStrategy):

    _SYSTEM_ERROR_CODES = frozenset({
        1040, 1041, 1042, 1043, 1044, 1045,
        1080, 1152, 1153, 1154, 1155, 1156,
        1157, 1158, 1159, 1160, 1161,
    })

    _JOIN_ALL = "ALL"
    _JOIN_INDEX = "index"

    _EXTRA_USING_TEMPORARY = "Using temporary"
    _EXTRA_USING_FILESORT = "Using filesort"
    _EXTRA_USING_JOIN_BUFFER = "Using join buffer"

    _ISSUE_FULL_TABLE_SCAN = "表 {table} 全表扫描，预估扫描行数 {rows}"
    _ISSUE_FULL_INDEX_SCAN = "表 {table} 全索引扫描，预估扫描行数 {rows}"
    _ISSUE_TEMP_AND_FILESORT = "表 {table} 同时使用了临时表和文件排序"
    _ISSUE_JOIN_NO_INDEX = "表 {table} JOIN 未使用索引"
    _ISSUE_CARTESIAN = "多表全表扫描（{count} 张表），存在笛卡尔积风险"

    @property
    def name(self) -> str:
        return "MySQL"

    @property
    def sqlglot_dialect(self) -> str:
        return "mysql"

    def is_system_error(self, exc: OperationalError) -> bool:
        code = self._extract_dbapi_error_code(exc)
        return code is not None and code in self._SYSTEM_ERROR_CODES

    def build_explain_sql(self, sql: str) -> str:
        return f"EXPLAIN {sql}"

    def parse_explain(self, rows: list[dict], max_rows: int) -> ExplainAnalysis:
        parsed = [
            _MySQLExplainRow.model_validate(
                {k.lower(): v for k, v in row.items() if v is not None}
            )
            for row in rows
        ]

        issues: list[str] = []
        full_scan_count = 0

        for r in parsed:
            if not r.table:
                continue
            if r.join_type == self._JOIN_ALL and r.rows > max_rows:
                issues.append(self._ISSUE_FULL_TABLE_SCAN.format(table=r.table, rows=r.rows))
            if r.join_type == self._JOIN_INDEX and r.rows > max_rows:
                issues.append(self._ISSUE_FULL_INDEX_SCAN.format(table=r.table, rows=r.rows))
            if self._EXTRA_USING_TEMPORARY in r.extra and self._EXTRA_USING_FILESORT in r.extra:
                issues.append(self._ISSUE_TEMP_AND_FILESORT.format(table=r.table))
            if self._EXTRA_USING_JOIN_BUFFER in r.extra:
                issues.append(self._ISSUE_JOIN_NO_INDEX.format(table=r.table))
            if r.join_type == self._JOIN_ALL:
                full_scan_count += 1

        if full_scan_count > 1:
            issues.append(self._ISSUE_CARTESIAN.format(count=full_scan_count))

        cost = sum(r.rows for r in parsed)
        raw = self._extract_raw_text(rows)
        return ExplainAnalysis(cost=cost, issues=issues, raw=raw)


class PostgreSQLDialect(DialectStrategy):
    """PostgreSQL 方言，使用 EXPLAIN (FORMAT JSON) 获取结构化执行计划"""

    _SYSTEM_SQLSTATES = frozenset({
        "08000", "08001", "08003", "08004", "08006",
        "57000", "57014", "57P01", "57P02", "57P03", "57P04",
        "53000", "53100", "53200", "53300", "53400",
    })

    _NODE_SEQ_SCAN = "Seq Scan"

    _KEY_NODE_TYPE = "Node Type"
    _KEY_PLAN_ROWS = "Plan Rows"
    _KEY_TOTAL_COST = "Total Cost"
    _KEY_RELATION = "Relation Name"
    _KEY_PLANS = "Plans"
    _KEY_PLAN = "Plan"

    _ISSUE_SEQ_SCAN = "表 {table} 顺序扫描，预估行数 {rows}"

    @property
    def name(self) -> str:
        return "PostgreSQL"

    @property
    def sqlglot_dialect(self) -> str:
        return "postgres"

    def is_system_error(self, exc: OperationalError) -> bool:
        orig = getattr(exc, "orig", None)
        pgcode = getattr(orig, "pgcode", None) if orig else None
        return pgcode is not None and pgcode in self._SYSTEM_SQLSTATES

    def build_explain_sql(self, sql: str) -> str:
        return f"EXPLAIN (FORMAT JSON) {sql}"

    def parse_explain(self, rows: list[dict], max_rows: int) -> ExplainAnalysis:
        plan = self._extract_plan(rows)
        if plan is None:
            raw = self._extract_raw_text(rows)
            return ExplainAnalysis(cost=0, issues=[], raw=raw)

        issues: list[str] = []
        self._walk_plan(plan, issues, max_rows)

        cost = int(plan.get(self._KEY_TOTAL_COST, 0))
        raw = json.dumps(plan, indent=2, ensure_ascii=False)
        return ExplainAnalysis(cost=cost, issues=issues, raw=raw)

    def _extract_plan(self, rows: list[dict]) -> Optional[dict]:
        """从 EXPLAIN FORMAT JSON 结果中提取顶层 Plan 节点"""
        if not rows:
            return None
        value = next(iter(rows[0].values()), None)
        if value is None:
            return None
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return None
        if isinstance(value, list) and value:
            return value[0].get(self._KEY_PLAN)
        if isinstance(value, dict):
            return value.get(self._KEY_PLAN)
        return None

    def _walk_plan(self, node: dict, issues: list[str], max_rows: int) -> None:
        """递归遍历计划树，检测 Seq Scan 等性能问题"""
        node_type = node.get(self._KEY_NODE_TYPE, "")
        plan_rows = int(node.get(self._KEY_PLAN_ROWS, 0))
        relation = node.get(self._KEY_RELATION, "")

        if node_type == self._NODE_SEQ_SCAN and relation and plan_rows > max_rows:
            issues.append(self._ISSUE_SEQ_SCAN.format(table=relation, rows=plan_rows))

        for child in node.get(self._KEY_PLANS, []):
            self._walk_plan(child, issues, max_rows)


_CH_GRANULES_PATTERN = re.compile(r"Granules:\s*(\d+)/(\d+)")


class ClickHouseDialect(DialectStrategy):
    """ClickHouse 方言，使用 EXPLAIN indexes=1 获取索引命中和 granule 统计"""

    _SYSTEM_ERROR_CODES = frozenset({
        159,   # TIMEOUT_EXCEEDED
        202,   # TOO_MANY_SIMULTANEOUS_QUERIES
        209,   # SOCKET_TIMEOUT
        210,   # NETWORK_ERROR
        241,   # MEMORY_LIMIT_EXCEEDED
        516,   # AUTHENTICATION_FAILED
        999,   # KEEPER_EXCEPTION
    })

    _NODE_READ_FROM_MERGE_TREE = "ReadFromMergeTree"
    _KEYWORD_INDEXES = "Indexes:"

    _ISSUE_FULL_GRANULE_SCAN = "全 granule 扫描（{selected}/{total}），未命中主键索引"
    _ISSUE_NO_INDEX_FILTER = "ReadFromMergeTree 未使用索引过滤"

    @property
    def name(self) -> str:
        return "ClickHouse"

    @property
    def sqlglot_dialect(self) -> str:
        return "clickhouse"

    def is_system_error(self, exc: OperationalError) -> bool:
        code = self._extract_dbapi_error_code(exc)
        return code is not None and code in self._SYSTEM_ERROR_CODES

    def build_explain_sql(self, sql: str) -> str:
        return f"EXPLAIN indexes=1 {sql}"

    def parse_explain(self, rows: list[dict], max_rows: int) -> ExplainAnalysis:
        raw = self._extract_raw_text(rows)
        issues: list[str] = []

        matches = _CH_GRANULES_PATTERN.findall(raw)
        if matches:
            cost = sum(int(selected) for selected, _ in matches)
            for selected, total in matches:
                if selected == total and int(total) > 0:
                    issues.append(
                        self._ISSUE_FULL_GRANULE_SCAN.format(selected=selected, total=total)
                    )
        else:
            cost = 0
            if self._NODE_READ_FROM_MERGE_TREE in raw and self._KEYWORD_INDEXES not in raw:
                issues.append(self._ISSUE_NO_INDEX_FILTER)

        return ExplainAnalysis(cost=cost, issues=issues, raw=raw)


_SCHEME_DIALECT_MAP: dict[str, type[DialectStrategy]] = {
    "mysql+aiomysql": MySQLDialect,
    "postgresql+psycopg": PostgreSQLDialect,
    "clickhouse+asynch": ClickHouseDialect,
}


def detect_dialect(url: str) -> DialectStrategy:
    """从数据库 URL scheme 推断方言并返回对应策略实例

    Raises:
        ValueError: URL scheme 不在支持列表中
    """
    scheme = urlparse(url).scheme
    dialect_cls = _SCHEME_DIALECT_MAP.get(scheme)
    if dialect_cls is None:
        supported = ", ".join(sorted(_SCHEME_DIALECT_MAP))
        raise ValueError(
            f"Unsupported database URL scheme: {scheme!r}, supported: {supported}"
        )
    return dialect_cls()
