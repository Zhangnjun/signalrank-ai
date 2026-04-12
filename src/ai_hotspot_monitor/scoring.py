from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ai_hotspot_monitor.models import Article, LocalScore, ResumeProfile

TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9\+#\./-]{1,}")
ENGLISH_PHRASE_PATTERN = re.compile(
    r"\b([A-Za-z][A-Za-z0-9\+#\./-]{2,}(?:\s+[A-Za-z][A-Za-z0-9\+#\./-]{2,}){1,2})\b"
)
SENTENCE_PATTERN = re.compile(r"(?<=[。！？.!?])\s+")
SECTION_HEADER_HINTS = {
    "summary",
    "profile",
    "projects",
    "project experience",
    "project details",
    "work experience",
    "experience",
    "employment",
    "education",
    "education background",
    "internship",
    "internships",
    "research experience",
    "technical skills",
    "skills",
    "tech stack",
    "responsibilities",
    "responsibility",
    "achievements",
    "leadership",
    "publications",
    "certifications",
    "项目描述",
    "负责内容",
    "技术栈",
    "工作经历",
    "教育经历",
    "项目经验",
    "实习经历",
    "校园经历",
    "个人总结",
    "技能清单",
    "教育背景",
    "研究经历",
}
EDUCATION_HINTS = {
    "university",
    "college",
    "school",
    "academy",
    "institute",
    "bachelor",
    "master",
    "masters",
    "phd",
    "doctorate",
    "major",
    "minor",
    "gpa",
    "faculty",
    "campus",
    "大学",
    "学院",
    "本科",
    "硕士",
    "博士",
    "专业",
    "学位",
}
TECH_CONTEXT_HINTS = {
    "agent",
    "rag",
    "retrieval",
    "inference",
    "serving",
    "runtime",
    "deployment",
    "deploy",
    "scheduler",
    "batching",
    "compiler",
    "quantization",
    "evaluation",
    "benchmark",
    "orchestration",
    "pipeline",
    "tooling",
    "api",
    "sdk",
    "model",
    "training",
    "embedding",
    "reranker",
    "vector",
    "database",
    "infra",
    "platform",
    "docker",
    "kubernetes",
    "redis",
    "python",
    "gpu",
    "cpu",
    "cluster",
    "latency",
    "throughput",
    "缓存",
    "推理",
    "部署",
    "服务",
    "调度",
    "评测",
    "向量",
    "数据库",
    "平台",
    "编译",
    "容器",
    "工程",
}
DOMAIN_HINTS = {
    "agent",
    "agents",
    "rag",
    "retrieval",
    "inference",
    "serving",
    "runtime",
    "deployment",
    "scheduler",
    "batching",
    "compiler",
    "quantization",
    "evaluation",
    "benchmark",
    "tooling",
    "orchestration",
    "workflow",
    "vector",
    "embedding",
    "reranker",
    "multimodal",
    "interoperability",
    "open-source",
    "infrastructure",
    "infra",
    "platform",
    "推理",
    "部署",
    "调度",
    "评测",
    "工具链",
    "平台",
}
STACK_HINTS = {
    "python",
    "java",
    "golang",
    "go",
    "rust",
    "c++",
    "cuda",
    "docker",
    "kubernetes",
    "redis",
    "postgres",
    "mysql",
    "spark",
    "pytorch",
    "tensorflow",
    "onnx",
    "triton",
    "ray",
    "airflow",
    "grpc",
    "fastapi",
    "flask",
    "linux",
    "git",
    "jenkins",
    "aws",
    "azure",
    "gcp",
    "modelarts",
    "mindie",
    "ascend",
}
EXPANSION_MAP = {
    "agent": {"tool calling", "function calling", "agent runtime", "orchestration", "workflow", "planner"},
    "agents": {"tool calling", "function calling", "agent runtime", "orchestration", "workflow", "planner"},
    "rag": {"retrieval augmented generation", "retrieval pipeline", "vector database", "semantic search", "reranker", "chunking"},
    "retrieval": {"rag", "retrieval pipeline", "vector database", "semantic search", "reranker"},
    "inference": {"serving", "model serving", "runtime", "throughput", "latency", "batching", "kv cache"},
    "serving": {"inference", "runtime", "model serving", "throughput", "latency", "batching"},
    "runtime": {"serving", "inference", "scheduler", "batching", "memory management"},
    "deployment": {"serving", "orchestration", "scheduler", "runtime", "rollout"},
    "scheduler": {"batching", "throughput", "latency", "runtime"},
    "batch": {"dynamic batching", "batching", "throughput", "scheduler"},
    "batching": {"dynamic batching", "throughput", "scheduler", "latency"},
    "embedding": {"semantic search", "vector retrieval", "reranker", "similarity search"},
    "reranker": {"embedding", "retrieval", "relevance ranking", "semantic search"},
    "vector search": {"vector database", "retrieval", "semantic search", "embedding"},
    "distributed inference": {"multi-node deployment", "serving", "runtime", "scheduler"},
    "multi-node deployment": {"distributed inference", "orchestration", "serving", "rollout"},
    "dynamic batching": {"batching", "scheduler", "throughput", "latency"},
    "redis": {"cache", "caching", "message queue", "state store"},
    "python": {"fastapi", "backend service", "api service", "automation"},
    "docker": {"containerization", "deployment", "image build", "runtime packaging"},
    "grpc": {"rpc", "service mesh", "backend interface"},
    "modelarts": {"training platform", "deployment platform", "ml platform"},
    "mindie": {"inference engine", "serving runtime", "deployment runtime"},
    "ascend": {"npu", "ai accelerator", "serving hardware", "inference hardware"},
}
WEAK_PLATFORM_HINTS = {
    "welink",
    "slack",
    "discord",
    "notion",
    "trello",
    "kaggle",
    "hackathon",
    "hackathons",
    "wechat",
    "teams",
    "zoom",
}
GENERIC_WEAK_TERMS = {
    "function",
    "calling",
    "content",
    "project",
    "projects",
    "description",
    "descriptions",
    "responsible",
    "responsibilities",
    "details",
    "detail",
    "experience",
    "university",
    "system",
    "systems",
    "technology",
    "technical",
    "solution",
    "solutions",
    "development",
    "engineer",
    "engineering",
    "platform",
    "service",
    "services",
    "能力",
    "项目",
    "内容",
    "经历",
    "负责",
    "技术",
    "平台",
    "系统",
    "熟练使用",
    "熟悉",
    "参与",
    "负责内容",
    "项目描述",
    "技术栈",
}
STOPWORDS = {
    "about",
    "after",
    "also",
    "and",
    "are",
    "for",
    "from",
    "have",
    "into",
    "that",
    "the",
    "their",
    "this",
    "with",
    "using",
    "your",
    "will",
    "into",
    "through",
    "into",
    "一个",
    "一种",
    "我们",
    "你们",
    "以及",
    "这个",
    "那个",
    "有关",
    "进行",
    "相关",
}
TECHNICAL_SIGNIFICANCE_TYPES = {
    "infra-platform",
    "serving-runtime",
    "open-source-tooling",
    "model-ecosystem",
    "ai-hardware",
}
SIGNIFICANCE_RULES = [
    (
        "ai-hardware",
        {
            "gpu",
            "cpu",
            "accelerator",
            "chip",
            "silicon",
            "datacenter",
            "data center",
            "server rack",
            "hbm",
            "arm",
            "nvidia",
            "mtia",
            "asic",
            "hardware",
        },
    ),
    (
        "serving-runtime",
        {
            "inference",
            "serving",
            "runtime",
            "scheduler",
            "batching",
            "latency",
            "throughput",
            "kv cache",
            "engine",
            "deployment",
            "compiler",
            "quantization",
            "memory",
        },
    ),
    (
        "open-source-tooling",
        {
            "sdk",
            "library",
            "tool",
            "tooling",
            "framework",
            "cli",
            "open source",
            "github",
            "foundation",
            "serialization",
            "safetensors",
        },
    ),
    (
        "model-ecosystem",
        {
            "model",
            "weights",
            "benchmark",
            "multimodal",
            "embedding",
            "reranker",
            "dataset",
            "fine-tuning",
            "open model",
            "interop",
            "agent",
        },
    ),
    (
        "policy-commentary",
        {
            "policy",
            "regulation",
            "governance",
            "risk review",
            "compliance",
            "europe",
            "law",
            "commentary",
        },
    ),
    (
        "consumer-newsroom",
        {
            "instagram",
            "whatsapp",
            "facebook",
            "threads",
            "teen accounts",
            "glasses",
            "consumer",
            "creator",
            "audience",
            "messaging",
            "photo sharing",
        },
    ),
]
LOW_SIGNAL_TITLE_TERMS = {
    "creator",
    "creators",
    "whatsapp",
    "instagram",
    "facebook",
    "audience",
    "messenger",
    "threads",
    "reels",
    "marketing",
    "advertisers",
    "ads",
    "shopping",
    "consumer",
}


def build_resume_profile(resume_text: str) -> ResumeProfile:
    normalized = normalize_text(resume_text)
    focus_terms, stack_terms, background_terms, excluded_terms = _extract_resume_terms(resume_text)
    rule_expanded_terms = _expand_resume_terms(focus_terms, stack_terms)
    summary_terms = (focus_terms[:5] + stack_terms[:3])[:8]
    summary = ", ".join(summary_terms) if summary_terms else "general software engineering"
    return ResumeProfile(
        raw_text=resume_text,
        normalized_text=normalized,
        focus_terms=focus_terms,
        stack_terms=stack_terms,
        rule_expanded_terms=rule_expanded_terms,
        ai_expanded_terms=[],
        expanded_terms=rule_expanded_terms,
        background_terms=background_terms,
        excluded_terms=excluded_terms,
        focus_summary=summary,
    )


def score_article(
    profile: ResumeProfile,
    article: Article,
    duplicate_count: int,
    topic_cluster_size: int,
    min_relevance: float,
    min_quality: float,
    heavyweight_impact: float,
) -> tuple[LocalScore, list[str], list[str]]:
    article_text = normalize_text(article.full_text)
    title_text = normalize_text(article.title)

    semantic_score = _cosine_score(profile.normalized_text, article_text)
    focus_overlap_score, matched_focus = _weighted_term_overlap(profile.focus_terms, article_text)
    stack_overlap_score, matched_stack = _weighted_term_overlap(profile.stack_terms, article_text)
    expanded_overlap_score, matched_expanded = _weighted_term_overlap(profile.expanded_terms, article_text)
    title_alignment_score = _title_alignment(profile.salient_terms, title_text)
    matched_terms = (matched_focus + [term for term in matched_stack if term not in matched_focus])[:12]

    direct_resume_relevance = _clamp(
        0.40 * semantic_score
        + 0.27 * focus_overlap_score
        + 0.13 * stack_overlap_score
        + 0.10 * expanded_overlap_score
        + 0.10 * title_alignment_score
    )
    relevance = direct_resume_relevance

    authority_score = _clamp(article.metadata.get("authority_weight", 0.7) * 100.0)
    recency_score = _recency_score(article.published)
    resonance_score = _clamp(25.0 * max(0, duplicate_count - 1) + 18.0 * max(0, topic_cluster_size - 1))
    depth_score = _depth_score(article)
    noise_penalty = _noise_penalty(article)
    significance_type, significance_prior = _classify_significance(article)

    impact = _clamp(
        0.35 * authority_score
        + 0.18 * recency_score
        + 0.17 * resonance_score
        + 0.15 * depth_score
        + 0.15 * significance_prior
    )
    quality = _clamp(0.62 * depth_score + 0.28 * authority_score + 0.10 * significance_prior - noise_penalty)
    ecosystem_significance = _clamp(
        0.40 * impact + 0.25 * quality + 0.20 * significance_prior + 0.15 * resonance_score
    )
    discovery = _clamp(0.35 * direct_resume_relevance + 0.35 * ecosystem_significance + 0.30 * quality)
    final_score = _clamp(0.40 * direct_resume_relevance + 0.33 * impact + 0.27 * quality)

    technical_ecosystem_heavyweight = (
        significance_type in TECHNICAL_SIGNIFICANCE_TYPES and ecosystem_significance >= heavyweight_impact
    )
    corporate_or_consumer_heavyweight = (
        significance_type in {"consumer-newsroom", "policy-commentary", "generic-corporate-pr"}
        and impact >= heavyweight_impact
    )
    keep, keep_reason, keep_reason_category, relevance_channel = _decide_keep(
        relevance=direct_resume_relevance,
        ecosystem_significance=ecosystem_significance,
        impact=impact,
        quality=quality,
        significance_type=significance_type,
        technical_ecosystem_heavyweight=technical_ecosystem_heavyweight,
        corporate_or_consumer_heavyweight=corporate_or_consumer_heavyweight,
        min_relevance=min_relevance,
        min_quality=min_quality,
        heavyweight_impact=heavyweight_impact,
    )

    return (
        LocalScore(
            relevance_score=round(relevance, 2),
            impact_score=round(impact, 2),
            quality_score=round(quality, 2),
            discovery_score=round(discovery, 2),
            final_score=round(final_score, 2),
            semantic_score=round(semantic_score, 2),
            term_overlap_score=round((0.55 * focus_overlap_score + 0.25 * stack_overlap_score + 0.20 * expanded_overlap_score), 2),
            title_alignment_score=round(title_alignment_score, 2),
            authority_score=round(authority_score, 2),
            recency_score=round(recency_score, 2),
            resonance_score=round(resonance_score, 2),
            depth_score=round(depth_score, 2),
            noise_penalty=round(noise_penalty, 2),
            expanded_term_score=round(expanded_overlap_score, 2),
            direct_resume_relevance=round(direct_resume_relevance, 2),
            ecosystem_significance=round(ecosystem_significance, 2),
            relevance_channel=relevance_channel,
            significance_type=significance_type,
            keep_reason_category=keep_reason_category,
            decision_source="local",
            keep=keep,
            keep_reason=keep_reason,
            industry_heavyweight=technical_ecosystem_heavyweight or corporate_or_consumer_heavyweight,
            technical_ecosystem_heavyweight=technical_ecosystem_heavyweight,
            corporate_or_consumer_heavyweight=corporate_or_consumer_heavyweight,
        ),
        matched_terms,
        matched_expanded[:12],
    )


def generate_summary(article: Article, max_sentences: int = 3) -> str:
    text = normalize_text(article.content or article.summary)
    if not text:
        return ""
    parts = [part.strip() for part in SENTENCE_PATTERN.split(text) if len(part.strip()) > 20]
    if not parts:
        return text[:320]
    return " ".join(parts[:max_sentences])[:520]


def normalize_text(text: str) -> str:
    return " ".join((text or "").replace("\u3000", " ").split())


def fingerprint_title(title: str) -> str:
    normalized = normalize_text(title).lower()
    tokens = [
        token
        for token in TOKEN_PATTERN.findall(normalized)
        if token not in STOPWORDS and len(token) > 2 and token not in GENERIC_WEAK_TERMS
    ]
    return " ".join(sorted(set(tokens[:10])))


def _extract_resume_terms(resume_text: str) -> tuple[list[str], list[str], list[str], list[str]]:
    focus_scores: Counter[str] = Counter()
    stack_scores: Counter[str] = Counter()
    background_scores: Counter[str] = Counter()
    excluded_scores: Counter[str] = Counter()

    for raw_line in resume_text.splitlines():
        line = normalize_text(raw_line)
        if not line:
            continue
        line_lower = line.lower().strip(":- ")
        if _is_section_header(line_lower):
            for token in TOKEN_PATTERN.findall(line_lower):
                excluded_scores[token.lower()] += 2
            continue

        is_education = _line_has_any(line_lower, EDUCATION_HINTS)
        tech_context = _line_has_any(line_lower, TECH_CONTEXT_HINTS) or _line_has_any(line_lower, STACK_HINTS)
        candidates = _extract_candidates_from_line(line)
        for candidate in candidates:
            term = candidate.lower()
            if _is_generic_noise(term):
                excluded_scores[term] += 1
                continue
            if is_education or _is_education_entity(term):
                background_scores[term] += 2
                continue
            if term in WEAK_PLATFORM_HINTS and not tech_context:
                background_scores[term] += 1
                continue
            if _looks_like_stack_term(term):
                score = 2 + int(tech_context)
                stack_scores[term] += score
                continue
            if _looks_like_focus_term(term, tech_context):
                score = 3 + int(tech_context)
                focus_scores[term] += score
                continue
            if tech_context and len(term) > 3:
                background_scores[term] += 1
            else:
                excluded_scores[term] += 1

    focus_terms = _rank_terms(focus_scores, max_terms=10)
    stack_terms = _rank_terms(stack_scores, max_terms=10, blocked=set(focus_terms))
    background_terms = _rank_terms(
        background_scores,
        max_terms=12,
        blocked=set(focus_terms) | set(stack_terms),
    )
    excluded_terms = _rank_terms(
        excluded_scores,
        max_terms=16,
        blocked=set(focus_terms) | set(stack_terms) | set(background_terms),
    )
    return focus_terms, stack_terms, background_terms, excluded_terms


def _extract_candidates_from_line(line: str) -> list[str]:
    candidates: list[str] = []
    lowered = line.lower()
    for phrase in ENGLISH_PHRASE_PATTERN.findall(line):
        normalized_phrase = normalize_text(phrase).lower()
        phrase_tokens = normalized_phrase.split()
        if any(token in DOMAIN_HINTS or token in STACK_HINTS for token in phrase_tokens):
            candidates.append(normalized_phrase)
    for token in TOKEN_PATTERN.findall(lowered):
        if _has_cjk(token) and len(token) > 10:
            continue
        candidates.append(token.lower())
    return candidates


def _rank_terms(counter: Counter[str], max_terms: int, blocked: set[str] | None = None) -> list[str]:
    blocked = blocked or set()
    ranked = sorted(counter.items(), key=lambda item: (-item[1], -len(item[0]), item[0]))
    terms: list[str] = []
    for term, _ in ranked:
        if term in blocked or _is_generic_noise(term):
            continue
        terms.append(term)
        if len(terms) >= max_terms:
            break
    return terms


def _expand_resume_terms(focus_terms: list[str], stack_terms: list[str], max_terms: int = 24) -> list[str]:
    expanded: list[str] = []
    seen = set(focus_terms) | set(stack_terms)
    seeds = focus_terms[:10] + stack_terms[:8]
    for term in seeds:
        normalized_term = term.lower()
        for candidate in EXPANSION_MAP.get(normalized_term, set()):
            candidate = candidate.lower()
            if candidate in seen or _is_generic_noise(candidate):
                continue
            expanded.append(candidate)
            seen.add(candidate)
        for rule_candidate in _rule_based_expansions(normalized_term):
            if rule_candidate in seen or _is_generic_noise(rule_candidate):
                continue
            expanded.append(rule_candidate)
            seen.add(rule_candidate)
        if len(expanded) >= max_terms:
            break
    return expanded[:max_terms]


def _rule_based_expansions(term: str) -> list[str]:
    expansions: list[str] = []
    if "agent" in term:
        expansions.extend(["tool calling", "agent workflow", "reasoning loop"])
    if "rag" in term or "retrieval" in term:
        expansions.extend(["context retrieval", "retrieval augmented generation", "vector retrieval"])
    if any(cue in term for cue in {"serve", "runtime", "inference", "deploy"}):
        expansions.extend(["model serving", "serving runtime", "throughput optimization"])
    if any(cue in term for cue in {"batch", "scheduler"}):
        expansions.extend(["dynamic batching", "request scheduling"])
    if any(cue in term for cue in {"embed", "vector", "rerank"}):
        expansions.extend(["semantic similarity", "retrieval ranking"])
    return expansions


def _cosine_score(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))
    matrix = vectorizer.fit_transform([left, right])
    return float(cosine_similarity(matrix[0:1], matrix[1:2])[0][0] * 100.0)


def _weighted_term_overlap(resume_terms: list[str], article_text: str) -> tuple[float, list[str]]:
    if not resume_terms or not article_text:
        return 0.0, []
    article_lower = article_text.lower()
    matched: list[str] = []
    total_weight = 0.0
    matched_weight = 0.0
    for index, term in enumerate(resume_terms):
        weight = max(0.8, 1.6 - index * 0.08)
        total_weight += weight
        if term.lower() in article_lower:
            matched.append(term)
            matched_weight += weight
    if total_weight == 0:
        return 0.0, []
    return (matched_weight / total_weight) * 100.0, matched[:12]


def _title_alignment(resume_terms: list[str], title_text: str) -> float:
    if not resume_terms or not title_text:
        return 0.0
    title_lower = title_text.lower()
    weighted_hits = 0.0
    for index, term in enumerate(resume_terms[:10]):
        if term.lower() in title_lower:
            weighted_hits += max(0.6, 1.4 - index * 0.12)
    return min(100.0, weighted_hits * 18.0)


def _recency_score(published: str) -> float:
    if not published:
        return 35.0
    try:
        value = datetime.fromisoformat(published.replace("Z", "+00:00"))
    except ValueError:
        return 35.0
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (datetime.now(timezone.utc) - value).total_seconds() / 86400.0)
    if age_days <= 2:
        return 100.0
    if age_days <= 7:
        return 85.0
    if age_days <= 30:
        return 65.0
    if age_days <= 90:
        return 45.0
    return 25.0


def _depth_score(article: Article) -> float:
    text = article.content or article.summary
    if not text:
        return 10.0
    length = len(text)
    sentence_count = max(1, len(SENTENCE_PATTERN.split(text)))
    numeric_ratio = min(1.0, len(re.findall(r"\d", text)) / max(1, length / 30))
    richness = min(1.0, length / 2800.0)
    sentence_score = min(1.0, sentence_count / 14.0)
    return (0.55 * richness + 0.25 * sentence_score + 0.20 * numeric_ratio) * 100.0


def _noise_penalty(article: Article) -> float:
    title = article.title or ""
    content = article.content or article.summary
    if not content:
        return 35.0

    penalty = 0.0
    if re.findall(r"[!?！？]{2,}", title):
        penalty += 10.0
    if len(content) < 260:
        penalty += 18.0
    upper_letters = [char for char in title if char.isalpha()]
    upper_ratio = sum(1 for char in upper_letters if char.isupper()) / max(1, len(upper_letters))
    if upper_ratio > 0.55:
        penalty += 10.0
    if len(set(title.lower().split())) <= 3:
        penalty += 6.0
    title_tokens = {token.lower() for token in TOKEN_PATTERN.findall(title)}
    if title_tokens & LOW_SIGNAL_TITLE_TERMS:
        penalty += 16.0
    return penalty


def _classify_significance(article: Article) -> tuple[str, float]:
    text = " ".join(
        [
            normalize_text(article.title).lower(),
            normalize_text(article.summary).lower(),
            normalize_text(article.content).lower(),
            " ".join(article.tags).lower(),
        ]
    )
    best_type = "generic-corporate-pr"
    best_score = 42.0
    for significance_type, cues in SIGNIFICANCE_RULES:
        hits = sum(1 for cue in cues if cue in text)
        if hits == 0:
            continue
        candidate_score = min(95.0, 48.0 + hits * 10.0)
        if candidate_score > best_score:
            best_type = significance_type
            best_score = candidate_score

    if best_type == "generic-corporate-pr" and any(token in text for token in {"announcement", "launch", "introducing", "partners with"}):
        best_score = 50.0

    return best_type, best_score


def _decide_keep(
    *,
    relevance: float,
    ecosystem_significance: float,
    impact: float,
    quality: float,
    significance_type: str,
    technical_ecosystem_heavyweight: bool,
    corporate_or_consumer_heavyweight: bool,
    min_relevance: float,
    min_quality: float,
    heavyweight_impact: float,
) -> tuple[bool, str, str, str]:
    if quality < min_quality:
        return False, "quality below threshold", "discard", "weak_match"

    high_resume_match = relevance >= min_relevance
    adjacent_resume_match = relevance >= max(22.0, min_relevance * 0.72)
    ecosystem_shift = ecosystem_significance >= heavyweight_impact - 6.0

    if high_resume_match and ecosystem_shift and significance_type in TECHNICAL_SIGNIFICANCE_TYPES:
        return True, "direct resume match with ecosystem-level technical impact", "both", "hybrid"
    if high_resume_match:
        return True, "strong direct alignment with resume focus", "resume_relevant", "direct_resume_match"
    if technical_ecosystem_heavyweight:
        return True, "technical ecosystem heavyweight event", "ecosystem_heavyweight", "ecosystem_shift"
    if adjacent_resume_match and ecosystem_shift and significance_type in TECHNICAL_SIGNIFICANCE_TYPES:
        return True, "adjacent to resume focus and important across the AI engineering ecosystem", "both", "hybrid"
    if corporate_or_consumer_heavyweight:
        return False, "corporate or consumer heavyweight without enough technical spillover", "discard", "weak_match"
    if ecosystem_shift and significance_type in TECHNICAL_SIGNIFICANCE_TYPES and impact >= heavyweight_impact - 4.0:
        return True, "ecosystem shift with meaningful technical spillover", "ecosystem_heavyweight", "ecosystem_shift"
    return False, "not relevant enough and ecosystem significance is limited", "discard", "weak_match"


def _is_section_header(line: str) -> bool:
    candidate = line.strip().strip(":：-").lower()
    if candidate in SECTION_HEADER_HINTS:
        return True
    if len(candidate) <= 40 and candidate.endswith(("experience", "skills", "projects", "education")):
        return True
    return False


def _is_education_entity(term: str) -> bool:
    if _line_has_any(term, EDUCATION_HINTS):
        return True
    return bool(re.search(r"(university|college|institute|学院|大学)$", term))


def _is_generic_noise(term: str) -> bool:
    if not term or term in STOPWORDS or term in GENERIC_WEAK_TERMS or term in SECTION_HEADER_HINTS:
        return True
    if len(term) <= 2:
        return True
    if _has_cjk(term) and len(term) > 10:
        return True
    if re.fullmatch(r"\d+", term):
        return True
    return False


def _looks_like_stack_term(term: str) -> bool:
    if term in STACK_HINTS:
        return True
    if "/" in term or "#" in term or "++" in term:
        return True
    return False


def _looks_like_focus_term(term: str, tech_context: bool) -> bool:
    if term in DOMAIN_HINTS:
        return True
    if tech_context and len(term) >= 4 and term not in WEAK_PLATFORM_HINTS and term not in GENERIC_WEAK_TERMS:
        return True
    return False


def _line_has_any(text: str, cues: set[str]) -> bool:
    return any(cue in text for cue in cues)


def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, value))


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)
