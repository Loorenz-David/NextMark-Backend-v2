from __future__ import annotations

from typing import Literal, Any

from pydantic import BaseModel, Field


class StatisticalMetric(BaseModel):
    name: str
    value: float
    delta: float | None = None


class StatisticalInsight(BaseModel):
    type: Literal["trend", "anomaly", "correlation"]
    description: str
    confidence: float


class StatisticalOutput(BaseModel):
    summary: str
    key_metrics: list[StatisticalMetric] = Field(default_factory=list)
    insights: list[StatisticalInsight] = Field(default_factory=list)
    warnings: list[str] | None = None
    confidence_score: float


# ---------------------------------------------------------------------------
# Narrative Statistics Blocks
# ---------------------------------------------------------------------------

class NarrativeBlockText(BaseModel):
    """Text narrative block for descriptive analysis."""
    type: Literal["text"]
    title: str | None = None
    text: str


class NarrativeBlockAnalyticsKPI(BaseModel):
    """KPI metric block with name, value, and optional delta."""
    type: Literal["analytics_kpi"]
    metric_name: str
    value: float
    delta: float | None = None
    unit: str | None = None
    confidence_score: float | None = None


class NarrativeBlockAnalyticsTrend(BaseModel):
    """Trend analysis block showing direction and change over time."""
    type: Literal["analytics_trend"]
    title: str
    description: str
    direction: Literal["up", "down", "stable"] | None = None
    confidence_score: float | None = None
    data_points: list[dict[str, Any]] | None = None


class NarrativeBlockAnalyticsBreakdown(BaseModel):
    """Breakdown/composition analysis block showing component distribution."""
    type: Literal["analytics_breakdown"]
    title: str
    description: str | None = None
    components: list[dict[str, Any]]
    confidence_score: float | None = None


class NarrativeBlockAnalytics(BaseModel):
    """Generic analytics block for frontend-driven chart layouts."""
    type: Literal["analytics"]
    layout: Literal["metric_grid", "bar_list", "table"]
    title: str
    subtitle: str | None = None
    data: dict[str, Any]


class NarrativeBlock(BaseModel):
    """Union wrapper for all narrative block types."""
    # This is handled via discriminated union via Pydantic's model-validation
    # Frontend will receive blocks with explicit type field for runtime dispatch
    pass


# Discriminated union type for parsing
NarrativeBlockType = (
    NarrativeBlockText
    | NarrativeBlockAnalyticsKPI
    | NarrativeBlockAnalyticsTrend
    | NarrativeBlockAnalyticsBreakdown
    | NarrativeBlockAnalytics
)


class NarrativeStatisticalOutput(BaseModel):
    """
    New narrative-driven statistics output contract.
    
    Replaces flat StatisticalOutput with ordered narrative blocks
    that preserve LLM-specified sequence and structure.
    
    Includes:
    - summary: high-level text summary in message.content
    - blocks: ordered array of narrative blocks (text, KPI, trend, breakdown)
    - confidence_score: overall confidence in the analysis (0.0-1.0)
    """
    summary: str
    blocks: list[NarrativeBlockType] = Field(default_factory=list)
    confidence_score: float = 0.5
    warnings: list[str] | None = None
