from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any

import requests

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
    normalize_text,
    score_article,
)


LOGGER = logging.getLogger("ai_hotspot_monitor")


class MonitorPipeline:
    def __init__(
        self,
        fetcher: ArticleFetcher | None = None,
        ai_evaluator: "AiHotspotEvaluator | None" = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.fetcher = fetcher or ArticleFetcher(logger=logger or LOGGER)
        self.ai_evaluator = ai_evaluator
        self.logger = logger or LOGGER

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
        ai_expand_resume: bool = False,
    ) -> MonitorResult:
        self.logger.info(
            "Pipeline run started: sources=%s per_source_limit=%s ai_enabled=%s",
            len(sources),
            per_source_limit,
            self.ai_evaluator is not None,
        )
        profile = build_resume_profile(resume_text)
        ai_error = ""
        degrade_reason = ""
        if ai_expand_resume and self.ai_evaluator:
            try:
                ai_expanded_terms = self.ai_evaluator.expand_resume_terms(profile)
                if ai_expanded_terms:
                    profile.ai_expanded_terms = ai_expanded_terms
                    profile.expanded_terms = _merge_expanded_terms(profile.rule_expanded_terms, ai_expanded_terms)
                    self.logger.info(
                        "AI resume expansion completed: added=%s total_expanded=%s",
                        len(ai_expanded_terms),
                        len(profile.expanded_terms),
                    )
            except Exception as exc:
                ai_error = str(exc)
                degrade_reason = "ai resume expansion failed; using rule-based expansion only"
                self.logger.warning("AI resume expansion failed, falling back to local expansion: %s", exc)
        fetched_articles, source_failed_count = self._fetch_all(sources, per_source_limit)
        deduped_articles, duplicate_counts, topic_cluster_sizes = self._dedupe_articles(fetched_articles)
        self.logger.info(
            "Collection complete: fetched=%s deduped=%s",
            len(fetched_articles),
            len(deduped_articles),
        )

        ranked: list[RankedArticle] = []
        for article in deduped_articles:
            canonical_key = article.url.strip() or article.title.strip()
            topic_key = fingerprint_title(article.title) or article.title.strip().lower()
            local_score, matched_terms, matched_expanded_terms = score_article(
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
                    matched_expanded_terms=matched_expanded_terms,
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

        refinement_mode = "disabled"
        ai_refined_count = 0
        ai_override_count = 0
        degraded_count = 0
        if self.ai_evaluator:
            try:
                refine_result = self.ai_evaluator.refine(
                    profile=profile,
                    ranked=ranked,
                    ai_top_k=ai_top_k,
                    ai_candidate_pool=ai_candidate_pool,
                )
                refinement_mode = str(refine_result["mode"])
                ai_error = ai_error or str(refine_result.get("ai_error", ""))
                degrade_reason = degrade_reason or str(refine_result.get("degrade_reason", ""))
                ai_refined_count = int(refine_result.get("ai_refined_count", 0))
                ai_override_count = int(refine_result.get("ai_override_count", 0))
                degraded_count = int(refine_result.get("degraded_count", 0))
                self.logger.info("AI refinement completed with mode=%s", refinement_mode)
            except Exception as exc:
                refinement_mode = "failed-fallback"
                ai_error = str(exc)
                degrade_reason = "ai refine failed; local ranking preserved"
                degraded_count = len(ranked)
                self.logger.exception(
                    "AI refinement failed; falling back to local ranking only: error=%s",
                    exc,
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
                refinement_mode=refinement_mode,
                ai_error=ai_error,
                degrade_reason=degrade_reason,
                ai_refined_count=ai_refined_count,
                ai_override_count=ai_override_count,
                degraded_count=degraded_count,
                source_failed_count=source_failed_count,
            ),
            generated_at=datetime.now(timezone.utc),
        )

    def _fetch_all(self, sources: list[Source], per_source_limit: int) -> tuple[list[Article], int]:
        articles: list[Article] = []
        failed_count = 0
        for source in sources:
            try:
                source_articles = self.fetcher.fetch(source, per_source_limit)
                self.logger.info("Fetched source=%s count=%s", source.name, len(source_articles))
                articles.extend(source_articles)
            except Exception as exc:
                failed_count += 1
                self.logger.warning("Source fetch failed: source=%s error=%s", source.name, exc)
                continue
        return articles, failed_count

    def _dedupe_articles(
        self, articles: list[Article]
    ) -> tuple[list[Article], dict[str, int], dict[str, int]]:
        deduped: list[Article] = []
        duplicate_counts: dict[str, int] = defaultdict(int)
        topic_cluster_sizes: dict[str, int] = defaultdict(int)
        seen_urls: dict[str, Article] = {}

        for article in articles:
            canonical_key = article.url.strip() or article.title.strip()
            topic_key = fingerprint_title(article.title) or article.title.strip().lower()
            duplicate_counts[canonical_key] += 1
            topic_cluster_sizes[topic_key] += 1

            if article.url and article.url in seen_urls:
                preferred = _prefer_article(seen_urls[article.url], article)
                seen_urls[article.url] = preferred
                if preferred is article and preferred not in deduped:
                    deduped.append(preferred)
                continue

            if self._is_near_duplicate(article, deduped):
                duplicate_counts[canonical_key] += 1
                continue

            deduped.append(article)
            if article.url:
                seen_urls[article.url] = article

        return deduped, duplicate_counts, topic_cluster_sizes

    def _is_near_duplicate(self, candidate: Article, existing_articles: list[Article]) -> bool:
        candidate_title = _normalized_title(candidate.title)
        candidate_body = _normalized_body(candidate.content or candidate.summary)
        for existing in existing_articles:
            existing_title = _normalized_title(existing.title)
            if candidate_title and candidate_title == existing_title:
                return True
            if candidate_title and existing_title:
                title_ratio = SequenceMatcher(None, candidate_title, existing_title).ratio()
                if title_ratio >= 0.94:
                    return True

            existing_body = _normalized_body(existing.content or existing.summary)
            if candidate_body and existing_body:
                body_ratio = SequenceMatcher(None, candidate_body[:1200], existing_body[:1200]).ratio()
                if body_ratio >= 0.9 and candidate_title == existing_title:
                    return True
        return False


class AiHotspotEvaluator:
    def __init__(
        self,
        chat_api_key: str | None,
        chat_api_key_env: str,
        chat_model: str,
        embedding_model: str,
        generation_api: str = "responses",
        chat_base_url: str | None = None,
        embedding_api_key: str | None = None,
        embedding_api_key_env: str = "OPENAI_EMBEDDING_API_KEY",
        embedding_base_url: str | None = None,
        chat_timeout: int = 300,
        embedding_timeout: int = 60,
        logger: logging.Logger | None = None,
    ) -> None:
        self.logger = logger or LOGGER
        chat_api_key = chat_api_key or os.getenv(chat_api_key_env)
        if not chat_api_key:
            raise ValueError(
                f"Either chat API key parameter or environment variable {chat_api_key_env} is required."
            )
        self.chat_api_key = chat_api_key
        self.chat_model = chat_model
        self.embedding_model = embedding_model
        self.generation_api = generation_api
        self.chat_base_url = (chat_base_url or "").rstrip("/")
        self.embedding_api_key = embedding_api_key or os.getenv(embedding_api_key_env) or chat_api_key
        self.embedding_base_url = (embedding_base_url or chat_base_url or "").rstrip("/")
        self.chat_timeout = chat_timeout
        self.embedding_timeout = embedding_timeout
        self.embedding_available = False

        if embedding_model and self.embedding_base_url and self.embedding_api_key:
            self.embedding_available = True

        self.logger.info(
            "AI evaluator initialized: generation_api=%s chat_model=%s embedding_model=%s chat_base_url=%s embedding_base_url=%s embedding_enabled=%s",
            self.generation_api,
            self.chat_model,
            self.embedding_model,
            self.chat_base_url or "<default>",
            self.embedding_base_url or "<default>",
            self.embedding_available,
        )

    def expand_resume_terms(self, profile: ResumeProfile) -> list[str]:
        instructions = (
            "You are expanding a resume profile for AI engineering intelligence filtering. "
            "Generate concise expansion terms from the resume focus and stack. "
            "Prefer technical synonyms, engineering aliases, infrastructure/runtime terms, adjacent tooling terms, and scenario terms. "
            "Do not repeat source terms. Do not return generic soft-skill words, education entities, or broad corporate words. "
            "Return JSON only."
        )
        prompt = (
            f"Resume focus summary: {profile.focus_summary}\n"
            f"Focus terms: {', '.join(profile.focus_terms[:12])}\n"
            f"Stack terms: {', '.join(profile.stack_terms[:12])}\n"
            f"Background terms: {', '.join(profile.background_terms[:10])}\n"
            f"Excluded terms: {', '.join(profile.excluded_terms[:12])}\n"
            "Return at most 18 high-signal expansion terms."
        )
        schema = {
            "type": "object",
            "properties": {
                "expanded_terms": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["expanded_terms"],
            "additionalProperties": False,
        }
        payload = (
            self._evaluate_via_chat_completions(instructions, prompt, schema)
            if self.generation_api == "chat-completions"
            else self._evaluate_via_responses(instructions, prompt, schema)
        )
        source_terms = {term.lower() for term in profile.focus_terms + profile.stack_terms + profile.rule_expanded_terms}
        expanded: list[str] = []
        for term in payload.get("expanded_terms", []):
            normalized = normalize_text(str(term)).lower()
            if not normalized or normalized in source_terms or normalized in expanded:
                continue
            expanded.append(normalized)
            if len(expanded) >= 18:
                break
        return expanded

    def refine(
        self,
        *,
        profile: ResumeProfile,
        ranked: list[RankedArticle],
        ai_top_k: int,
        ai_candidate_pool: int,
    ) -> dict[str, Any]:
        if not ranked:
            return {
                "mode": "disabled",
                "ai_error": "",
                "degrade_reason": "",
                "ai_refined_count": 0,
                "ai_override_count": 0,
                "degraded_count": 0,
            }

        refinement_mode = "chat-only"
        ai_error = ""
        degrade_reason = ""
        ai_refined_count = 0
        ai_override_count = 0
        degraded_count = 0
        candidate_pool = ranked[: max(ai_candidate_pool, ai_top_k)]

        if self.embedding_available:
            self.logger.info("Starting embedding rerank for %s candidates", len(candidate_pool))
            try:
                self.apply_embedding_rerank(profile, candidate_pool)
                refinement_mode = "full"
                self.logger.info("Embedding rerank completed successfully")
            except Exception as exc:
                refinement_mode = "chat-only"
                ai_error = str(exc)
                degrade_reason = "embedding rerank failed; degraded to chat-only"
                degraded_count += len(candidate_pool)
                self.logger.warning("Embedding rerank failed, falling back to chat-only mode: %s", exc)
        else:
            degrade_reason = "embedding unavailable; chat-only refinement"
            self.logger.info("Embedding rerank skipped because embedding configuration is unavailable")

        rerank_candidates = sorted(
            candidate_pool,
            key=lambda item: (
                item.local_score.keep,
                item.embedding_score,
                item.final_discovery_score,
                item.final_score,
            ),
            reverse=True,
        )
        self.logger.info("Starting chat evaluation for %s candidates", min(ai_top_k, len(rerank_candidates)))
        for item in rerank_candidates[:ai_top_k]:
            try:
                assessment = self.evaluate(profile, item)
            except Exception as exc:
                if not ai_error:
                    ai_error = str(exc)
                degrade_reason = "one or more chat evaluations failed; kept local ranking for those items"
                degraded_count += 1
                self.logger.warning(
                    "Chat evaluation failed for article=%s url=%s error=%s; keeping local ranking for this item",
                    item.article.title,
                    item.article.url,
                    exc,
                )
                continue

            ai_refined_count += 1
            ai_override = _assessment_overrides_local(item, assessment)
            item.ai_override = ai_override
            assessment.ai_override = ai_override
            assessment.decision_source = "ai_override" if ai_override else ("hybrid" if item.embedding_applied else "hybrid")
            if ai_override:
                ai_override_count += 1
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
        self.logger.info("Chat evaluation finished")
        if ai_refined_count == 0:
            refinement_mode = "local-only"
            if not degrade_reason:
                degrade_reason = "ai refinement requested but no item was successfully refined"
        return {
            "mode": refinement_mode,
            "ai_error": ai_error,
            "degrade_reason": degrade_reason,
            "ai_refined_count": ai_refined_count,
            "ai_override_count": ai_override_count,
            "degraded_count": degraded_count,
        }

    def apply_embedding_rerank(self, profile: ResumeProfile, ranked_articles: list[RankedArticle]) -> None:
        if not ranked_articles or not self.embedding_available:
            raise RuntimeError("Embedding rerank is not configured")
        texts = [_profile_embedding_text(profile)]
        texts.extend(_embedding_text(item.article) for item in ranked_articles)
        payload = {"model": self.embedding_model, "input": texts}
        response_payload = self._post_json(
            url=f"{self.embedding_base_url}/embeddings",
            api_key=self.embedding_api_key,
            payload=payload,
            timeout=self.embedding_timeout,
            request_name="embedding",
        )
        vectors = [item["embedding"] for item in response_payload["data"]]
        resume_vector = vectors[0]
        article_vectors = vectors[1:]

        for item, vector in zip(ranked_articles, article_vectors):
            embedding_score = round(_cosine_similarity(resume_vector, vector) * 100.0, 2)
            item.embedding_score = embedding_score
            item.embedding_applied = True
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
            "Judge a single article on resume relevance, AI engineering ecosystem significance, industry impact, and content quality. "
            "Avoid fixed keyword matching. Infer from the resume profile, article substance, source authority, and likely engineering value. "
            "Classify significance_type using one of: infra-platform, serving-runtime, open-source-tooling, model-ecosystem, ai-hardware, consumer-newsroom, policy-commentary, generic-corporate-pr. "
            "Classify relevance_channel using one of: direct_resume_match, ecosystem_shift, hybrid, weak_match. "
            "Classify keep_reason_category using one of: resume_relevant, ecosystem_heavyweight, both, discard. "
            "Set technical_ecosystem_heavyweight true only for ecosystem-level technical shifts. "
            "Set corporate_or_consumer_heavyweight true for large company, policy, or consumer announcements that are not inherently technical ecosystem shifts. "
            "Consumer newsroom, policy commentary, and generic corporate PR should be demoted unless there is clear technical spillover into AI engineering workflows. "
            "Use 0-100 scores. Return JSON only."
        )
        prompt = (
            f"Resume focus summary: {profile.focus_summary}\n"
            f"Resume focus terms: {', '.join(profile.focus_terms[:12])}\n"
            f"Resume stack terms: {', '.join(profile.stack_terms[:12])}\n"
            f"Expanded resume terms: {', '.join(profile.expanded_terms[:18])}\n"
            f"Resume background terms: {', '.join(profile.background_terms[:10])}\n\n"
            f"Article title: {article.title}\n"
            f"Source: {article.source_name}\n"
            f"Published: {article.published}\n"
            f"Source tags: {', '.join(article.tags)}\n"
            f"Local relevance score: {ranked_article.local_score.relevance_score}\n"
            f"Local impact score: {ranked_article.local_score.impact_score}\n"
            f"Local quality score: {ranked_article.local_score.quality_score}\n"
            f"Local discovery score: {ranked_article.local_score.discovery_score}\n"
            f"Local direct resume relevance: {ranked_article.local_score.direct_resume_relevance}\n"
            f"Local ecosystem significance: {ranked_article.local_score.ecosystem_significance}\n"
            f"Local relevance channel: {ranked_article.local_score.relevance_channel}\n"
            f"Local significance type: {ranked_article.local_score.significance_type}\n"
            f"Local keep reason category: {ranked_article.local_score.keep_reason_category}\n"
            f"Matched resume terms: {', '.join(ranked_article.matched_resume_terms[:10])}\n"
            f"Matched expanded terms: {', '.join(ranked_article.matched_expanded_terms[:10])}\n"
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
                "significance_type": {"type": "string"},
                "relevance_channel": {"type": "string"},
                "keep_reason_category": {"type": "string"},
                "relevance_score": {"type": "number"},
                "impact_score": {"type": "number"},
                "quality_score": {"type": "number"},
                "discovery_score": {"type": "number"},
                "industry_heavyweight": {"type": "boolean"},
                "technical_ecosystem_heavyweight": {"type": "boolean"},
                "corporate_or_consumer_heavyweight": {"type": "boolean"},
                "summary": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "keep",
                "keep_reason",
                "retention_class",
                "significance_type",
                "relevance_channel",
                "keep_reason_category",
                "relevance_score",
                "impact_score",
                "quality_score",
                "discovery_score",
                "industry_heavyweight",
                "technical_ecosystem_heavyweight",
                "corporate_or_consumer_heavyweight",
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
            significance_type=payload["significance_type"],
            relevance_channel=payload["relevance_channel"],
            keep_reason_category=payload["keep_reason_category"],
            decision_source="hybrid",
            relevance_score=round(_normalize_ai_score(payload["relevance_score"]), 2),
            impact_score=round(_normalize_ai_score(payload["impact_score"]), 2),
            quality_score=round(_normalize_ai_score(payload["quality_score"]), 2),
            discovery_score=round(_normalize_ai_score(payload["discovery_score"]), 2),
            embedding_score=ranked_article.embedding_score,
            industry_heavyweight=bool(payload["industry_heavyweight"]),
            technical_ecosystem_heavyweight=bool(payload["technical_ecosystem_heavyweight"]),
            corporate_or_consumer_heavyweight=bool(payload["corporate_or_consumer_heavyweight"]),
            summary=payload["summary"],
            tags=payload["tags"],
        )

    def _evaluate_via_responses(self, instructions: str, prompt: str, schema: dict) -> dict:
        payload = {
            "model": self.chat_model,
            "store": False,
            "instructions": instructions,
            "input": prompt,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "hotspot_assessment",
                    "strict": True,
                    "schema": schema,
                }
            },
        }
        response_payload = self._post_json(
            url=f"{self.chat_base_url}/responses",
            api_key=self.chat_api_key,
            payload=payload,
            timeout=self.chat_timeout,
            request_name="responses",
        )
        output_text = response_payload.get("output_text")
        if output_text:
            return json.loads(output_text)
        for item in response_payload.get("output", []):
            for content in item.get("content", []):
                text = content.get("text")
                if text:
                    return json.loads(text)
        raise RuntimeError("Responses API returned no JSON text payload")

    def _evaluate_via_chat_completions(self, instructions: str, prompt: str, schema: dict) -> dict:
        payload = {
            "model": self.chat_model,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "hotspot_assessment",
                    "strict": True,
                    "schema": schema,
                },
            },
        }
        response_payload = self._post_json(
            url=f"{self.chat_base_url}/chat/completions",
            api_key=self.chat_api_key,
            payload=payload,
            timeout=self.chat_timeout,
            request_name="chat-completions",
        )
        content = response_payload["choices"][0]["message"].get("content") or "{}"
        if isinstance(content, list):
            text_chunks = [item.get("text", "") for item in content if isinstance(item, dict)]
            content = "".join(text_chunks) or "{}"
        return json.loads(content)

    def _post_json(
        self,
        *,
        url: str,
        api_key: str | None,
        payload: dict[str, Any],
        timeout: int,
        request_name: str,
    ) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key or ''}",
        }
        self.logger.info("HTTP request start: name=%s url=%s timeout=%ss", request_name, url, timeout)
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        except Exception as exc:
            self.logger.error("HTTP request failed before response: name=%s url=%s timeout=%ss error=%s", request_name, url, timeout, exc)
            raise

        content_type = response.headers.get("content-type", "")
        preview = response.text[:300].replace("\n", " ")
        self.logger.info(
            "HTTP response: name=%s url=%s status=%s content_type=%s body_preview=%s",
            request_name,
            url,
            response.status_code,
            content_type,
            preview,
        )
        response.raise_for_status()
        return response.json()


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


def _profile_embedding_text(profile: ResumeProfile) -> str:
    return (
        f"Resume focus: {profile.focus_summary}\n"
        f"Focus terms: {', '.join(profile.focus_terms[:12])}\n"
        f"Stack terms: {', '.join(profile.stack_terms[:12])}\n"
        f"Expanded terms: {', '.join(profile.expanded_terms[:18])}\n"
        f"Background terms: {', '.join(profile.background_terms[:10])}\n"
        f"Resume text: {profile.raw_text[:5000]}"
    )


def _merge_expanded_terms(rule_terms: list[str], ai_terms: list[str], max_terms: int = 36) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for term in rule_terms + ai_terms:
        normalized = normalize_text(term).lower()
        if not normalized or normalized in seen:
            continue
        merged.append(normalized)
        seen.add(normalized)
        if len(merged) >= max_terms:
            break
    return merged


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
    if item.keep_reason_category == "both" or (
        item.final_relevance_score >= 55 and item.final_quality_score >= 60
    ):
        return "worth-reading-now"
    if item.keep_reason_category == "resume_relevant" or (
        item.final_relevance_score >= 40 and item.final_quality_score >= 55
    ):
        return "demo-candidate"
    if item.keep_reason_category == "ecosystem_heavyweight" or item.final_impact_score >= 75:
        return "industry-watch"
    return "watchlist"


def _assessment_overrides_local(item: RankedArticle, assessment: AiAssessment) -> bool:
    if assessment.keep != item.local_score.keep:
        return True
    if assessment.keep_reason_category != item.local_score.keep_reason_category:
        return True
    if assessment.relevance_channel != item.local_score.relevance_channel:
        return True
    if assessment.significance_type != item.local_score.significance_type:
        return True
    return False


def _normalize_ai_score(value: Any) -> float:
    score = float(value)
    if 0.0 <= score <= 10.0:
        return score * 10.0
    return score


def _normalized_title(title: str) -> str:
    return normalize_text(title).lower()


def _normalized_body(text: str) -> str:
    normalized = normalize_text(text).lower()
    return normalized[:2000]
