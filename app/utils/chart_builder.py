from collections import defaultdict
from typing import Any, Dict, List, Optional

from app.schemas.agent import ChartAdvice, ChartType

_AXIS_CHART_TYPES = {ChartType.BAR, ChartType.LINE, ChartType.AREA, ChartType.HORIZONTAL_BAR}
_NAME_VALUE_CHART_TYPES = {ChartType.PIE, ChartType.FUNNEL}

_SERIES_TYPE_BAR = "bar"
_SERIES_TYPE_LINE = "line"
_SERIES_TYPE_SCATTER = "scatter"

_AXIS_TYPE_CATEGORY = "category"
_AXIS_TYPE_VALUE = "value"

_TRIGGER_AXIS = "axis"
_TRIGGER_ITEM = "item"

_LEGEND_BOTTOM: Dict[str, Any] = {"top": "bottom"}
_LEGEND_BOTTOM_SCROLL: Dict[str, Any] = {"top": "bottom", "type": "scroll"}

_ANIMATION_DURATION = 600

_PIE_RADIUS = ["40%", "70%"]
_PIE_LABEL_FORMAT = "{b}: {d}%"
_FUNNEL_LEFT = "10%"
_FUNNEL_WIDTH = "80%"

_LABEL_ROTATE_THRESHOLD = 6


def build(advice: ChartAdvice, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """根据 ChartAdvice 和查询结果生成 ECharts option JSON"""
    chart_type = advice.chart_type

    if chart_type in _AXIS_CHART_TYPES:
        return _build_axis_chart(advice, rows)
    if chart_type in _NAME_VALUE_CHART_TYPES:
        return _build_name_value_chart(advice, rows)
    if chart_type == ChartType.SCATTER:
        return _build_scatter_chart(advice, rows)

    raise ValueError(f"Unsupported chart type: {chart_type}")


def _base_option(title: str) -> Dict[str, Any]:
    return {
        "title": {"text": title, "left": "center"},
        "tooltip": {"trigger": _TRIGGER_AXIS},
        "animation": True,
        "animationDuration": _ANIMATION_DURATION,
    }


def _build_axis_chart(
    advice: ChartAdvice,
    rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """构建轴式图表：bar / line / area / horizontal_bar"""
    option = _base_option(advice.title)
    series_type = _resolve_series_type(advice.chart_type)
    is_horizontal = advice.chart_type == ChartType.HORIZONTAL_BAR

    if advice.series_field:
        categories, series_list = _group_by_series(
            rows, advice.x_field, advice.y_field, advice.series_field, series_type,
        )
        if advice.chart_type == ChartType.AREA:
            for s in series_list:
                s["areaStyle"] = {}
        option["legend"] = _LEGEND_BOTTOM.copy()
    else:
        categories = [_to_str(r.get(advice.x_field)) for r in rows]
        data = [_to_number(r.get(advice.y_field)) for r in rows]
        series_entry: Dict[str, Any] = {"type": series_type, "data": data}
        if advice.chart_type == ChartType.AREA:
            series_entry["areaStyle"] = {}
        if advice.chart_type == ChartType.LINE:
            series_entry["smooth"] = True
        series_list = [series_entry]

    category_axis: Dict[str, Any] = {
        "type": _AXIS_TYPE_CATEGORY,
        "data": categories,
        "axisLabel": {"interval": 0, "rotate": 30 if len(categories) > _LABEL_ROTATE_THRESHOLD else 0},
    }
    value_axis: Dict[str, Any] = {"type": _AXIS_TYPE_VALUE}

    if is_horizontal:
        option["xAxis"] = value_axis
        option["yAxis"] = category_axis
    else:
        option["xAxis"] = category_axis
        option["yAxis"] = value_axis

    option["series"] = series_list
    return option


def _build_name_value_chart(
    advice: ChartAdvice,
    rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """构建 name-value 图表：pie / funnel"""
    option = _base_option(advice.title)
    option["tooltip"] = {"trigger": _TRIGGER_ITEM}

    data = [
        {"name": _to_str(r.get(advice.x_field)), "value": _to_number(r.get(advice.y_field))}
        for r in rows
        if r.get(advice.y_field) is not None
    ]

    series_entry: Dict[str, Any] = {
        "type": advice.chart_type.value,
        "data": data,
    }

    if advice.chart_type == ChartType.PIE:
        series_entry["radius"] = _PIE_RADIUS
        series_entry["label"] = {"show": True, "formatter": _PIE_LABEL_FORMAT}
        option["legend"] = _LEGEND_BOTTOM_SCROLL.copy()

    if advice.chart_type == ChartType.FUNNEL:
        series_entry["left"] = _FUNNEL_LEFT
        series_entry["width"] = _FUNNEL_WIDTH
        series_entry["sort"] = "descending"
        series_entry["label"] = {"show": True, "position": "inside"}
        option["legend"] = _LEGEND_BOTTOM_SCROLL.copy()

    option["series"] = [series_entry]
    return option


def _build_scatter_chart(
    advice: ChartAdvice,
    rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """构建散点图"""
    option = _base_option(advice.title)
    option["tooltip"] = {"trigger": _TRIGGER_ITEM}
    option["xAxis"] = {"type": _AXIS_TYPE_VALUE, "name": advice.x_field}
    option["yAxis"] = {"type": _AXIS_TYPE_VALUE, "name": advice.y_field}

    if advice.series_field:
        groups: Dict[str, List[List[Any]]] = defaultdict(list)
        for r in rows:
            x = _to_number(r.get(advice.x_field))
            y = _to_number(r.get(advice.y_field))
            if x is not None and y is not None:
                groups[_to_str(r.get(advice.series_field))].append([x, y])
        option["legend"] = _LEGEND_BOTTOM.copy()
        option["series"] = [
            {"name": name, "type": _SERIES_TYPE_SCATTER, "data": data}
            for name, data in groups.items()
        ]
    else:
        data = [
            [_to_number(r.get(advice.x_field)), _to_number(r.get(advice.y_field))]
            for r in rows
            if r.get(advice.x_field) is not None and r.get(advice.y_field) is not None
        ]
        option["series"] = [{"type": _SERIES_TYPE_SCATTER, "data": data}]

    return option


def _group_by_series(
    rows: List[Dict[str, Any]],
    x_field: Optional[str],
    y_field: Optional[str],
    series_field: str,
    series_type: str,
) -> tuple[List[str], List[Dict[str, Any]]]:
    """按 series_field 分组，返回分类轴标签和多组 series"""
    categories_set: List[str] = []
    groups: Dict[str, Dict[str, Any]] = defaultdict(dict)

    for r in rows:
        cat = _to_str(r.get(x_field))
        if cat not in categories_set:
            categories_set.append(cat)
        series_name = _to_str(r.get(series_field))
        groups[series_name][cat] = _to_number(r.get(y_field))

    series_list = []
    for name, cat_values in groups.items():
        data = [cat_values.get(cat, 0) for cat in categories_set]
        entry: Dict[str, Any] = {"name": name, "type": series_type, "data": data}
        if series_type == _SERIES_TYPE_LINE:
            entry["smooth"] = True
        series_list.append(entry)

    return categories_set, series_list


def _resolve_series_type(chart_type: ChartType) -> str:
    if chart_type in {ChartType.BAR, ChartType.HORIZONTAL_BAR}:
        return _SERIES_TYPE_BAR
    return _SERIES_TYPE_LINE


def _to_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _to_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
