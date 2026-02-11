from typing import Optional, List, Any, Literal, Union

from pydantic import BaseModel, Field

from app.vars.vars import FilterOp


class FilterElement(BaseModel):
    """
    过滤条件
    """
    op: FilterOp = Field(..., description="操作符")
    operands: Optional[List[Union["FilterElement", Any]]] = Field(default=None, description="操作对象")


class OrderElement(BaseModel):
    """
    排序字段
    """
    fields: str = Field(..., description="排序字段")
    direction: Literal["ASC", "DESC"] = Field(default="ASC", description="排序方向")


class WindowElement(BaseModel):
    """
    sql 窗口函数信息
    """
    partition_by: Optional[List[str]] = Field(default=None, description="分区字段列表")
    order_by: Optional[List[OrderElement]] = Field(default=None, description="排序字段列表")
    frame: Optional[str] = Field(default=None,
                                 description="窗口帧定义，例如ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW")


class ColumnElement(BaseModel):
    """
    查询字段、表达式
    """
    name: str = Field(..., description="字段名或表达式")
    table_alias: Optional[str] = Field(default=None, description="所属表别名")
    alias: Optional[str] = Field(default=None, description="字段别名")
    agg: Optional[str] = Field(default=None, description="聚合函数")
    func_args: Optional[List[Any]] = Field(default=None, description="函数参数，用于函数调用")
    window: Optional[WindowElement] = Field(default=None, description="窗口函数信息")


class LimitElement(BaseModel):
    """
    分页限制
    """
    offset: int = Field(default=0, description="偏移行数")
    count: int = Field(..., description="返回行数限制")


class JoinElement(BaseModel):
    """
    表关联节点
    """
    join_type: Literal["INNER", "LEFT", "RIGHT", "FULL"] = Field(..., description="关联类型")
    table: "TableElement" = Field(..., description="关联表节点")
    on: FilterElement = Field(..., description="关联条件")


class TableElement(BaseModel):
    """
    表信息
    """
    name: str = Field(..., description="表名")
    alias: Optional[str] = Field(default=None, description="表别名")
    joins: Optional[List[JoinElement]] = Field(default=None, description="表关联信息")


class SubQueryElement(BaseModel):
    """
    子查询节点
    """
    query: "QueryElement" = Field(..., description="子查询对应的查询语句")
    alias: str = Field(..., description="子查询别名")


class UnionElement(BaseModel):
    """
    集合操作节点
    """
    all: bool = Field(default=True, description="是否UNION ALL")
    queries: List["QueryElement"] = Field(..., description="参与集合操作的查询列表")


class QueryElement(BaseModel):
    select: List[ColumnElement] = Field(default_factory=list, description="选择字段列表")
    from_table: Optional[TableElement] = Field(default=None, description="主表")
    where: Optional[FilterElement] = Field(default=None, description="查询条件")
    group_by: Optional[List[str]] = Field(default=None, description="分组字段")
    having: Optional[FilterElement] = Field(default=None, description="聚合后过滤条件")
    order_by: Optional[List[OrderElement]] = Field(default=None, description="排序字段")
    limit: Optional[LimitElement] = Field(default=None, description="分页限制")
    unions: Optional[List[UnionElement]] = Field(default=None, description="集合操作列表")
    subqueries: Optional[List[SubQueryElement]] = Field(default=None, description="子查询列表")
