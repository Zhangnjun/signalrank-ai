from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from ai_hotspot_monitor.config import load_sources
from ai_hotspot_monitor.pipeline import AiHotspotEvaluator, MonitorPipeline
from ai_hotspot_monitor.resume import load_resume_text


LOGGER = logging.getLogger("ai_hotspot_monitor")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Monitor AI industry hotspots and rank them by CV relevance, industry impact, and content quality."
    )
    parser.add_argument("--resume", required=True, help="Path to CV or resume file.")
    parser.add_argument(
        "--sources",
        default="sources.json",
        help="Path to source configuration JSON.",
    )
    parser.add_argument("--per-source-limit", type=int, default=8, help="Maximum items to fetch per source.")
    parser.add_argument("--top-n", type=int, default=30, help="Maximum ranked items to keep in the report.")
    parser.add_argument("--min-relevance", type=float, default=32.0, help="Minimum relevance score to keep an item by fit.")
    parser.add_argument("--min-quality", type=float, default=30.0, help="Minimum quality score to keep an item.")
    parser.add_argument(
        "--heavyweight-impact",
        type=float,
        default=68.0,
        help="Impact score threshold for retaining major industry events even when CV fit is low.",
    )
    parser.add_argument("--output-dir", default="reports", help="Directory for report files.")
    parser.add_argument("--json-only", action="store_true", help="Only generate JSON report.")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Logging verbosity.")

    parser.add_argument("--ai-evaluate", action="store_true", help="Use AI to refine the top articles.")
    parser.add_argument("--ai-top-k", type=int, default=8, help="How many ranked items to send to the AI evaluator.")
    parser.add_argument("--ai-candidate-pool", type=int, default=20, help="How many locally recalled items to send through embedding rerank before final AI evaluation.")
    parser.add_argument("--generation-api", default="responses", choices=["responses", "chat-completions"], help="Generation API for AI rerank. Use chat-completions for gateways that do not support /v1/responses.")

    parser.add_argument("--ai-model", default="gpt-5-mini", help="Chat/generation model for refinement.")
    parser.add_argument("--openai-api-key", default="", help="Direct chat API key. Overrides the environment variable if both are provided.")
    parser.add_argument("--openai-api-key-env", default="OPENAI_API_KEY", help="Environment variable with chat API key.")
    parser.add_argument("--openai-base-url", default="", help="Optional OpenAI-compatible base URL for the chat/generation endpoint.")

    parser.add_argument("--embedding-model", default="text-embedding-3-small", help="Embedding model for semantic rerank.")
    parser.add_argument("--embedding-api-key", default="", help="Direct embedding API key. Overrides the embedding environment variable if both are provided.")
    parser.add_argument("--embedding-api-key-env", default="OPENAI_EMBEDDING_API_KEY", help="Environment variable with embedding API key.")
    parser.add_argument("--embedding-base-url", default="", help="Optional OpenAI-compatible base URL for the embedding endpoint.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    _configure_logging(args.log_level)

    LOGGER.info(
        "CLI configuration loaded: ai_evaluate=%s generation_api=%s ai_model=%s embedding_model=%s chat_base_url=%s embedding_base_url=%s",
        args.ai_evaluate,
        args.generation_api,
        args.ai_model,
        args.embedding_model,
        args.openai_base_url or "<default>",
        args.embedding_base_url or args.openai_base_url or "<default>",
    )

    resume_text = load_resume_text(args.resume)
    sources = load_sources(args.sources)
    ai_evaluator = None
    if args.ai_evaluate:
        ai_evaluator = AiHotspotEvaluator(
            chat_api_key=args.openai_api_key or None,
            chat_api_key_env=args.openai_api_key_env,
            chat_model=args.ai_model,
            embedding_model=args.embedding_model,
            generation_api=args.generation_api,
            chat_base_url=args.openai_base_url or None,
            embedding_api_key=args.embedding_api_key or None,
            embedding_api_key_env=args.embedding_api_key_env,
            embedding_base_url=args.embedding_base_url or None,
            logger=LOGGER,
        )
    else:
        LOGGER.info("AI evaluate disabled; running local scoring only.")

    pipeline = MonitorPipeline(ai_evaluator=ai_evaluator, logger=LOGGER)
    result = pipeline.run(
        resume_text=resume_text,
        sources=sources,
        per_source_limit=args.per_source_limit,
        min_relevance=args.min_relevance,
        min_quality=args.min_quality,
        heavyweight_impact=args.heavyweight_impact,
        top_n=args.top_n,
        ai_top_k=args.ai_top_k,
        ai_candidate_pool=args.ai_candidate_pool,
    )
    markdown_path, json_path = write_reports(result, args)

    LOGGER.info("Report generation complete: refinement_mode=%s markdown=%s json=%s", result.stats.refinement_mode, markdown_path, json_path)
    print(f"Fetched: {result.stats.fetched_count}")
    print(f"After dedupe: {result.stats.deduped_count}")
    print(f"Kept: {result.stats.kept_count}")
    print(f"AI refinement mode: {result.stats.refinement_mode}")
    if markdown_path:
        print(f"Markdown report: {markdown_path}")
    print(f"JSON report: {json_path}")


def write_reports(result, args) -> tuple[Path | None, Path]:
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = result.generated_at.astimezone().strftime("%Y%m%d_%H%M%S")
    markdown_path = None if args.json_only else output_dir / f"ai_hotspots_{timestamp}.md"
    json_path = output_dir / f"ai_hotspots_{timestamp}.json"

    records = [_to_record(item) for item in result.ranked_articles]
    json_path.write_text(
        json.dumps(
            {
                "generated_at": result.generated_at.isoformat(),
                "resume_focus": result.profile.focus_summary,
                "resume_terms": result.profile.salient_terms,
                "stats": {
                    "fetched_count": result.stats.fetched_count,
                    "deduped_count": result.stats.deduped_count,
                    "kept_count": result.stats.kept_count,
                    "discarded_count": result.stats.discarded_count,
                    "refinement_mode": result.stats.refinement_mode,
                },
                "items": records,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    if markdown_path is not None:
        markdown_path.write_text(_build_markdown(result, records, args), encoding="utf-8")
    return markdown_path, json_path


def _to_record(item) -> dict:
    article = item.article
    ai = item.ai_assessment
    return {
        "keep": item.keep,
        "keep_reason": item.keep_reason,
        "title": article.title,
        "url": article.url,
        "source_name": article.source_name,
        "published": article.published,
        "summary": item.generated_summary,
        "action_bucket": item.action_bucket,
        "retention_class": ai.retention_class if ai else _retention_class_from_bucket(item.action_bucket),
        "content_kind": ai.content_kind if ai else "unknown",
        "matched_resume_terms": item.matched_resume_terms,
        "duplicate_count": item.duplicate_count,
        "topic_cluster_size": item.topic_cluster_size,
        "scores": {
            "relevance": item.final_relevance_score,
            "impact": item.final_impact_score,
            "quality": item.final_quality_score,
            "discovery": item.final_discovery_score,
            "final": item.final_score,
        },
        "local_scores": {
            "semantic": item.local_score.semantic_score,
            "term_overlap": item.local_score.term_overlap_score,
            "title_alignment": item.local_score.title_alignment_score,
            "authority": item.local_score.authority_score,
            "recency": item.local_score.recency_score,
            "resonance": item.local_score.resonance_score,
            "depth": item.local_score.depth_score,
            "noise_penalty": item.local_score.noise_penalty,
            "discovery": item.local_score.discovery_score,
        },
        "embedding_score": item.embedding_score,
        "industry_heavyweight": ai.industry_heavyweight if ai else item.local_score.industry_heavyweight,
        "tags": ai.tags if ai else article.tags,
        "ai_refined": ai is not None,
    }


def _build_markdown(result, records: list[dict], args) -> str:
    lines = [
        "# AI Hotspot Monitor Report",
        "",
        f"- Generated at: {result.generated_at.isoformat()}",
        f"- Resume focus: {result.profile.focus_summary}",
        f"- Resume salient terms: {', '.join(result.profile.salient_terms[:18])}",
        f"- Sources config: {Path(args.sources).expanduser().resolve()}",
        f"- Fetched / deduped / kept: {result.stats.fetched_count} / {result.stats.deduped_count} / {result.stats.kept_count}",
        f"- AI refinement: {result.stats.refinement_mode}",
        f"- Thresholds: min_relevance={args.min_relevance}, min_quality={args.min_quality}, heavyweight_impact={args.heavyweight_impact}",
        "",
    ]

    kept = [item for item in records if item["keep"]]
    dropped = [item for item in records if not item["keep"]]
    bucket_order = ["worth-reading-now", "demo-candidate", "industry-watch", "watchlist"]

    if not records:
        lines.append("No items were collected.")
        return "\n".join(lines)

    lines.extend(["## Kept Items", ""])
    if not kept:
        lines.append("No items passed the current thresholds.")
    else:
        visible_kept = [item for item in kept if item["action_bucket"] != "watchlist"]
        for bucket in bucket_order:
            bucket_items = [item for item in visible_kept if item["action_bucket"] == bucket]
            if not bucket_items:
                continue
            lines.extend([f"### {bucket}", ""])
            for idx, item in enumerate(bucket_items, start=1):
                lines.extend(_markdown_block(idx, item))

    if dropped:
        lines.extend(["## Dropped Items", ""])
        for idx, item in enumerate(dropped, start=1):
            lines.extend(_markdown_block(idx, item))

    return "\n".join(lines)


def _markdown_block(idx: int, item: dict) -> list[str]:
    return [
        f"### {idx}. {item['title']}",
        "",
        f"- Keep: {item['keep']}",
        f"- Keep reason: {item['keep_reason']}",
        f"- Action bucket: {item['action_bucket']}",
        f"- Retention class: {item['retention_class']}",
        f"- Content kind: {item['content_kind']}",
        f"- Source: {item['source_name']}",
        f"- Published: {item['published'] or 'unknown'}",
        f"- URL: {item['url']}",
        f"- Relevance / Impact / Quality / Discovery / Final: {item['scores']['relevance']} / {item['scores']['impact']} / {item['scores']['quality']} / {item['scores']['discovery']} / {item['scores']['final']}",
        f"- Embedding score: {item['embedding_score']}",
        f"- Matched CV terms: {', '.join(item['matched_resume_terms']) or 'none'}",
        f"- Heavyweight event: {item['industry_heavyweight']}",
        f"- Duplicate count: {item['duplicate_count']}",
        f"- Topic cluster size: {item['topic_cluster_size']}",
        "",
        "#### Summary",
        "",
        item["summary"] or "No summary available.",
        "",
    ]


def _retention_class_from_bucket(bucket: str) -> str:
    mapping = {
        "worth-reading-now": "resume-fit",
        "demo-candidate": "demo-potential",
        "industry-watch": "industry-heavyweight",
        "watchlist": "watchlist",
    }
    return mapping.get(bucket, "watchlist")


def _configure_logging(level_name: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level_name.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


if __name__ == "__main__":
    main()
