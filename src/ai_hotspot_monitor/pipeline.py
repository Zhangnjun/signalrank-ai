from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime, timezone

from ai_hotspot_monitor.fetcher import ArticleFetcher
from ai_hotspot_monitor.models import (
    AiAssessment,
    Article,
    MonitorResult,
    PipelineStats,
    RankedArticle,
    ResumeProfile,
    Source,
)
from ai_hotspot_monitor.scoring import (
    build_resume_profile,
    fingerprint_title,
    generate_summary,
    score_article,
)


class MonitorPipeline:
    def __init__(
        self,
        fetcher: ArticleFetcher | None = None,
        ai_evaluator: "AiHotspotEvaluator | None" = None,
    ) -> None:
        self.fetcher = fetcher or ArticleFetcher()
        self.ai_evaluator = ai_evaluator

    def run(
        self,
        *,
        resume_text: str,
        sources: list[Source],
        per_source_limit: int,
        min_relevance: float,
        min_quality: float,
        heavyweight_impact: float,
        top_n: int,
        ai_top_k: int,
        ai_candidate_pool: int,
    ) -> MonitorResult:
        profile = build_resume_profile(resume_text)
        fetched_articles = self._fetch_all(sources, per_source_limit)
        deduped_articles, duplicate_counts, topic_cluster_sizes = self._dedupe_articles(fetched_articles)

        ranked: list[RankedArticle] = []
        for article in deduped_articles:
            canonical_key = article.url.strip() or article.title.strip()
            topic_key = fingerprint_title(article.title) or article.title.strip().lower()
            local_score, matched_terms = score_article(
                profile=profile,
                article=article,
                duplicate_count=duplicate_counts.get(canonical_key, 1),
                topic_cluster_size=topic_cluster_sizes.get(topic_key, 1),
                min_relevance=min_relevance,
                min_quality=min_quality,
                heavyweight_impact=heavyweight_impact,
            )
            ranked.append(
                RankedArticle(
                    article=article,
                    local_score=local_score,
                    final_relevance_score=local_score.relevance_score,
                    final_impact_score=local_score.impact_score,
                    final_quality_score=local_score.quality_score,
                    final_discovery_score=local_score.discovery_score,
                    final_score=local_score.final_score,
                    duplicate_count=duplicate_counts.get(canonical_key, 1),
                    topic_cluster_size=topic_cluster_sizes.get(topic_key, 1),
                    generated_summary=generate_summary(article),
                    matched_resume_terms=matched_terms,
                )
            )

        ranked.sort(
            key=lambda item: (
                item.keep,
                item.final_discovery_score,
                item.final_score,
                item.final_impact_score,
                item.final_relevance_score,
            ),
            reverse=True,
        )

        if self.ai_evaluator:
            self.ai_evaluator.apply_embedding_rerank(profile, ranked[: max(ai_candidate_pool, ai_top_k)])
            rerank_candidates = sorted(
                ranked[: max(ai_candidate_pool, ai_top_k)],
                key=lambda item: (
                    item.local_score.keep,
                    item.embedding_score,
                    item.final_discovery_score,
                    item.final_score,
                ),
                reverse=True,
            )
            for item in rerank_candidates[:ai_top_k]:
                assessment = self.ai_evaluator.evaluate(profile, item)
                item.ai_assessment = assessment
                item.final_relevance_score = assessment.relevance_score
                item.final_impact_score = assessment.impact_score
                item.final_quality_score = assessment.quality_score
                item.final_discovery_score = assessment.discovery_score
                item.embedding_score = assessment.embedding_score
                item.final_score = round(
                    0.30 * assessment.relevance_score
                    + 0.25 * assessment.impact_score
                    + 0.20 * assessment.quality_score
                    + 0.15 * assessment.discovery_score
                    + 0.10 * assessment.embedding_score,
                    2,
                )
                if assessment.summary:
                    item.generated_summary = assessment.summary

        ranked.sort(
            key=lambda item: (
                item.keep,
                item.final_discovery_score,
                item.final_score,
                item.final_impact_score,
                item.final_relevance_score,
            ),
            reverse=True,
        )
        for item in ranked:
            item.action_bucket = _action_bucket(item)
        ranked = ranked[:top_n]
        kept = sum(1 for item in ranked if item.keep)

        return MonitorResult(
            profile=profile,
            ranked_articles=ranked,
            stats=PipelineStats(
                fetched_count=len(fetched_articles),
                deduped_count=len(deduped_articles),
                kept_count=kept,
                discarded_count=max(0, len(ranked) - kept),
            ),
            generated_at=datetime.now(timezone.utc),
        )

    def _fetch_all(self, sources: list[Source], per_source_limit: int) -> list[Article]:
        articles: list[Article] = []
        for source in sources:
            try:
                articles.extend(self.fetcher.fetch(source, per_source_limit))
            except Exception:
                continue
        return articles

    def _dedupe_articles(
        self, articles: list[Article]
    ) -> tuple[list[Article], dict[str, int], dict[str, int]]:
        by_url: dict[str, Article] = {}
        by_title: dict[str, Article] = {}
        duplicate_counts: dict[str, int] = defaultdict(int)
        topic_cluster_sizes: dict[str, int] = defaultdict(int)

        for article in articles:
            canonical_key = article.url.strip() or article.title.strip()
            topic_key = fingerprint_title(article.title) or article.title.strip().lower()
            duplicate_counts[canonical_key] += 1
            topic_cluster_sizes[topic_key] += 1

            if article.url:
                if article.url in by_url:
                    by_url[article.url] = _prefer_article(by_url[article.url], article)
                else:
                    by_url[article.url] = article
            else:
                if topic_key in by_title:
                    by_title[topic_key] = _prefer_article(by_title[topic_key], article)
                else:
                    by_title[topic_key] = article

        deduped = list(by_url.values())
        seen_topic_keys = {fingerprint_title(item.title) or item.title.strip().lower() for item in deduped}
        for key, article in by_title.items():
            if key not in seen_topic_keys:
                deduped.append(article)
                seen_topic_keys.add(key)
        return deduped, duplicate_counts, topic_cluster_sizes


class AiHotspotEvaluator:
    def __init__(
        self,
        api_key: str | None,
        api_key_env: str,
        model: str,
        embedding_model: str,
        generation_api: str = "responses",
        base_url: str | None = None,
    ) -> None:
        try:
            from openai import OpenAI
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                "OpenAI package is not installed. Install dependencies or disable --ai-evaluate."
            ) from exc
        api_key = api_key or os.getenv(api_key_env)
        if not api_key:
            raise ValueError(
                f"Either --openai-api-key or environment variable {api_key_env} is required for AI hotspot evaluation."
            )
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self.client = OpenAI(**client_kwargs)
        self.model = model
        self.embedding_model = embedding_model
        self.generation_api = generation_api

    def apply_embedding_rerank(self, profile: ResumeProfile, ranked_articles: list[RankedArticle]) -> None:
        if not ranked_articles:
            return
        texts = [profile.raw_text[:7000]]
        texts.extend(_embedding_text(item.article) for item in ranked_articles)
        response = self.client.embeddings.create(model=self.embedding_model, input=texts)
        vectors = [item.embedding for item in response.data]
        resume_vector = vectors[0]
        article_vectors = vectors[1:]

        for item, vector in zip(ranked_articles, article_vectors):
            embedding_score = round(_cosine_similarity(resume_vector, vector) * 100.0, 2)
            item.embedding_score = embedding_score
            item.final_relevance_score = round(
                0.65 * item.final_relevance_score + 0.35 * embedding_score,
                2,
            )
            item.final_discovery_score = round(
                0.50 * item.local_score.discovery_score
                + 0.30 * item.final_impact_score
                + 0.20 * embedding_score,
                2,
            )
            item.final_score = round(
                0.35 * item.final_relevance_score
                + 0.25 * item.final_impact_score
                + 0.20 * item.final_quality_score
                + 0.20 * item.final_discovery_score,
                2,
            )

    def evaluate(self, profile: ResumeProfile, ranked_article: RankedArticle) -> AiAssessment:
        article = ranked_article.article
        instructions = (
            "You are ranking AI industry hotspots for an engineer. "
            "Judge a single article on three axes: resume relevance, industry impact, and content quality. "
            "Avoid hand-written keyword heuristics. Infer from the resume direction, article substance, source authority, and likely engineering value. "
            "Classify the article content kind before deciding keep. Use one of: infra-platform, agent-tooling, research-paper, enterprise-product, consumer-newsroom, market-commentary, other. "
            "Use one retention class from: resume-fit, industry-heavyweight, demo-potential, interview-material, watchlist. "
            "Consumer-newsroom content, creator features, messaging product updates, and general audience product news should be demoted unless they clearly change the AI engineering landscape. "
            "If the article is mostly hype, market noise, or has weak technical substance, lower quality sharply. "
            "Keep globally important AI events even if resume relevance is low. Return JSON only."
        )
        prompt = (
            f"Resume focus summary: {profile.focus_summary}\n"
            f"Resume salient terms: {', '.join(profile.salient_terms[:18])}\n\n"
            f"Article title: {article.title}\n"
            f"Source: {article.source_name}\n"
            f"Published: {article.published}\n"
            f"Source tags: {', '.join(article.tags)}\n"
            f"Local relevance score: {ranked_article.local_score.relevance_score}\n"
            f"Local impact score: {ranked_article.local_score.impact_score}\n"
            f"Local quality score: {ranked_article.local_score.quality_score}\n"
            f"Local discovery score: {ranked_article.local_score.discovery_score}\n"
            f"Embedding score: {ranked_article.embedding_score}\n"
            f"Topic cluster size: {ranked_article.topic_cluster_size}\n"
            f"Duplicate count: {ranked_article.duplicate_count}\n\n"
            f"Article summary:\n{ranked_article.generated_summary[:1200]}\n\n"
            f"Article content:\n{article.content[:6000]}"
        )
        schema = {
            "type": "object",
            "properties": {
                "keep": {"type": "boolean"},
                "keep_reason": {"type": "string"},
                "retention_class": {"type": "string"},
                "content_kind": {"type": "string"},
                "relevance_score": {"type": "number"},
                "impact_score": {"type": "number"},
                "quality_score": {"type": "number"},
                "discovery_score": {"type": "number"},
                "industry_heavyweight": {"type": "boolean"},
                "summary": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "keep",
                "keep_reason",
                "retention_class",
                "content_kind",
                "relevance_score",
                "impact_score",
                "quality_score",
                "discovery_score",
                "industry_heavyweight",
                "summary",
                "tags",
            ],
            "additionalProperties": False,
        }
        if self.generation_api == "chat-completions":
            payload = self._evaluate_via_chat_completions(instructions, prompt, schema)
        else:
            payload = self._evaluate_via_responses(instructions, prompt, schema)
        return AiAssessment(
            keep=bool(payload["keep"]),
            keep_reason=payload["keep_reason"],
            retention_class=payload["retention_class"],
            content_kind=payload["content_kind"],
            relevance_score=round(float(payload["relevance_score"]), 2),
            impact_score=round(float(payload["impact_score"]), 2),
            quality_score=round(float(payload["quality_score"]), 2),
            discovery_score=round(float(payload["discovery_score"]), 2),
            embedding_score=ranked_article.embedding_score,
            industry_heavyweight=bool(payload["industry_heavyweight"]),
            summary=payload["summary"],
            tags=payload["tags"],
        )

    def _evaluate_via_responses(self, instructions: str, prompt: str, schema: dict) -> dict:
        response = self.client.responses.create(
            model=self.model,
            store=False,
            instructions=instructions,
            input=prompt,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "hotspot_assessment",
                    "strict": True,
                    "schema": schema,
                }
            },
        )
        return json.loads(response.output_text)

    def _evaluate_via_chat_completions(self, instructions: str, prompt: str, schema: dict) -> dict:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "hotspot_assessment",
                    "strict": True,
                    "schema": schema,
                },
            },
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)


def _prefer_article(left: Article, right: Article) -> Article:
    left_len = len(left.content or left.summary)
    right_len = len(right.content or right.summary)
    return right if right_len > left_len else left


def _embedding_text(article: Article) -> str:
    return (
        f"Title: {article.title}\n"
        f"Source: {article.source_name}\n"
        f"Summary: {article.summary[:1500]}\n"
        f"Content: {article.content[:4000]}"
    )


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = sum(a * a for a in left) ** 0.5
    right_norm = sum(b * b for b in right) ** 0.5
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return max(0.0, min(1.0, numerator / (left_norm * right_norm)))


def _action_bucket(item: RankedArticle) -> str:
    if not item.keep:
        return "watchlist"
    if item.final_relevance_score >= 55 and item.final_quality_score >= 60:
        return "worth-reading-now"
    if item.final_relevance_score >= 40 and item.final_quality_score >= 55:
        return "demo-candidate"
    if item.final_impact_score >= 75 or item.local_score.industry_heavyweight:
        return "industry-watch"
    return "watchlist"
