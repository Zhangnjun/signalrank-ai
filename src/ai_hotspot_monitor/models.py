from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class Source:
    name: str
    url: str
    kind: str = "rss"
    authority_weight: float = 0.7
    enabled: bool = True
    article_limit: int | None = None
    headers: dict[str, str] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Article:
    source_name: str
    title: str
    url: str
    summary: str
    published: str
    content: str
    source_kind: str = "rss"
    author: str = ""
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        return "\n".join(part for part in [self.title, self.summary, self.content] if part)


@dataclass(slots=True)
class ResumeProfile:
    raw_text: str
    normalized_text: str
    salient_terms: list[str]
    focus_summary: str


@dataclass(slots=True)
class LocalScore:
    relevance_score: float
    impact_score: float
    quality_score: float
    discovery_score: float
    final_score: float
    semantic_score: float
    term_overlap_score: float
    title_alignment_score: float
    authority_score: float
    recency_score: float
    resonance_score: float
    depth_score: float
    noise_penalty: float
    keep: bool
    keep_reason: str
    industry_heavyweight: bool


@dataclass(slots=True)
class AiAssessment:
    keep: bool
    keep_reason: str
    relevance_score: float
    impact_score: float
    quality_score: float
    discovery_score: float
    embedding_score: float
    industry_heavyweight: bool
    summary: str
    tags: list[str]


@dataclass(slots=True)
class RankedArticle:
    article: Article
    local_score: LocalScore
    final_relevance_score: float
    final_impact_score: float
    final_quality_score: float
    final_discovery_score: float
    final_score: float
    ai_assessment: AiAssessment | None = None
    duplicate_count: int = 1
    topic_cluster_size: int = 1
    generated_summary: str = ""
    matched_resume_terms: list[str] = field(default_factory=list)
    embedding_score: float = 0.0

    @property
    def keep(self) -> bool:
        if self.ai_assessment is not None:
            return self.ai_assessment.keep
        return self.local_score.keep

    @property
    def keep_reason(self) -> str:
        if self.ai_assessment is not None:
            return self.ai_assessment.keep_reason
        return self.local_score.keep_reason


@dataclass(slots=True)
class PipelineStats:
    fetched_count: int
    deduped_count: int
    kept_count: int
    discarded_count: int


@dataclass(slots=True)
class MonitorResult:
    profile: ResumeProfile
    ranked_articles: list[RankedArticle]
    stats: PipelineStats
    generated_at: datetime
