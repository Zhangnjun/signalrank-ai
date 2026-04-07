from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ai_hotspot_monitor.models import Article, LocalScore, ResumeProfile

TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9\+#\./-]{1,}")
SENTENCE_PATTERN = re.compile(r"(?<=[。！？.!?])\s+")
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
    "我们",
    "你们",
    "以及",
    "这个",
    "那个",
    "有关",
    "进行",
    "相关",
    "一个",
    "一种",
    "技术",
    "系统",
    "能力",
    "负责",
    "参与",
}
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


def build_resume_profile(resume_text: str, max_terms: int = 18) -> ResumeProfile:
    normalized = normalize_text(resume_text)
    terms = extract_salient_terms(normalized, max_terms=max_terms)
    summary = ", ".join(terms[:8]) if terms else "general software engineering"
    return ResumeProfile(
        raw_text=resume_text,
        normalized_text=normalized,
        salient_terms=terms,
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
) -> tuple[LocalScore, list[str]]:
    article_text = normalize_text(article.full_text)
    title_text = normalize_text(article.title)

    semantic_score = _cosine_score(profile.normalized_text, article_text)
    term_overlap_score, matched_terms = _term_overlap(profile.salient_terms, article_text)
    title_alignment_score = _title_alignment(profile.salient_terms, title_text)

    relevance = _clamp(
        0.55 * semantic_score + 0.30 * term_overlap_score + 0.15 * title_alignment_score
    )
    authority_score = _clamp(article.metadata.get("authority_weight", 0.7) * 100.0)
    recency_score = _recency_score(article.published)
    resonance_score = _clamp(25.0 * max(0, duplicate_count - 1) + 18.0 * max(0, topic_cluster_size - 1))
    depth_score = _depth_score(article)
    noise_penalty = _noise_penalty(article)

    impact = _clamp(
        0.45 * authority_score + 0.20 * recency_score + 0.20 * resonance_score + 0.15 * depth_score
    )
    quality = _clamp(0.65 * depth_score + 0.35 * authority_score - noise_penalty)
    discovery = _clamp(0.30 * relevance + 0.40 * impact + 0.30 * quality)
    final_score = _clamp(0.38 * relevance + 0.34 * impact + 0.28 * quality)

    keep, keep_reason = _decide_keep(
        relevance=relevance,
        impact=impact,
        quality=quality,
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
            term_overlap_score=round(term_overlap_score, 2),
            title_alignment_score=round(title_alignment_score, 2),
            authority_score=round(authority_score, 2),
            recency_score=round(recency_score, 2),
            resonance_score=round(resonance_score, 2),
            depth_score=round(depth_score, 2),
            noise_penalty=round(noise_penalty, 2),
            keep=keep,
            keep_reason=keep_reason,
            industry_heavyweight=impact >= heavyweight_impact,
        ),
        matched_terms,
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
        if token not in STOPWORDS and len(token) > 2
    ]
    return " ".join(sorted(set(tokens[:10])))


def extract_salient_terms(text: str, max_terms: int = 18) -> list[str]:
    tokens = [
        token.lower()
        for token in TOKEN_PATTERN.findall(text)
        if token.lower() not in STOPWORDS and len(token) > 2
    ]
    if not tokens:
        return []
    counts = Counter(tokens)
    ranked = sorted(counts.items(), key=lambda item: (-item[1], -len(item[0]), item[0]))
    return [term for term, _ in ranked[:max_terms]]


def _cosine_score(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))
    matrix = vectorizer.fit_transform([left, right])
    return float(cosine_similarity(matrix[0:1], matrix[1:2])[0][0] * 100.0)


def _term_overlap(resume_terms: list[str], article_text: str) -> tuple[float, list[str]]:
    if not resume_terms or not article_text:
        return 0.0, []
    article_tokens = set(token.lower() for token in TOKEN_PATTERN.findall(article_text))
    matched = [term for term in resume_terms if term.lower() in article_tokens]
    recall = len(matched) / len(resume_terms)
    return recall * 100.0, matched[:12]


def _title_alignment(resume_terms: list[str], title_text: str) -> float:
    if not resume_terms or not title_text:
        return 0.0
    title_tokens = set(token.lower() for token in TOKEN_PATTERN.findall(title_text))
    weighted_hits = sum(1 for term in resume_terms[:8] if term.lower() in title_tokens)
    return min(100.0, weighted_hits * 20.0)


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


def _decide_keep(
    *,
    relevance: float,
    impact: float,
    quality: float,
    min_relevance: float,
    min_quality: float,
    heavyweight_impact: float,
) -> tuple[bool, str]:
    if quality < min_quality:
        return False, "quality below threshold"
    if relevance >= min_relevance and impact >= 35:
        return True, "high resume relevance with credible industry signal"
    if relevance >= min_relevance:
        return True, "high resume relevance"
    if impact >= heavyweight_impact:
        return True, "industry heavyweight event"
    if impact >= max(60.0, heavyweight_impact - 10.0) and quality >= max(55.0, min_quality + 10.0):
        return True, "high-impact discovery candidate"
    if relevance >= max(20.0, min_relevance * 0.55) and quality >= max(55.0, min_quality + 10.0):
        return True, "adjacent to resume focus with strong substance"
    return False, "not relevant enough and impact is limited"


def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, value))
