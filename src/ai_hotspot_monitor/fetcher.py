from __future__ import annotations

import json
import logging
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from ai_hotspot_monitor.models import Article, Source


LOGGER = logging.getLogger("ai_hotspot_monitor")
USER_AGENT = "Mozilla/5.0 (compatible; ai-hotspot-monitor/0.1; +https://example.local)"
ATOM_NS = "{http://www.w3.org/2005/Atom}"
CONTENT_CANDIDATES = [
    "article",
    "main article",
    "main",
    "[role='main'] article",
    "[role='main']",
    "[class*='article-body']",
    "[class*='article-content']",
    "[class*='post-content']",
    "[class*='entry-content']",
    "[class*='content-body']",
    "[class*='content']",
    "[class*='article']",
    "[class*='post']",
    "body",
]
NOISE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"^skip to main content$",
        r"^main menu$",
        r"^table of contents$",
        r"^back to top$",
        r"^sign in$",
        r"^log in$",
        r"^subscribe$",
        r"^privacy policy$",
        r"^terms of use$",
        r"^all rights reserved$",
        r"^cookie(s)?$",
        r"^share$",
        r"^copy link$",
        r"^follow$",
    ]
]


class ArticleFetcher:
    def __init__(self, timeout: int = 20, logger: logging.Logger | None = None) -> None:
        self.timeout = timeout
        self.logger = logger or LOGGER

    def fetch(self, source: Source, default_limit: int) -> list[Article]:
        if source.kind in {"rss", "atom"}:
            return self._fetch_feed(source, source.article_limit or default_limit)
        if source.kind == "json_feed":
            return self._fetch_json_feed(source, source.article_limit or default_limit)
        raise ValueError(f"Unsupported source kind: {source.kind}")

    def _fetch_feed(self, source: Source, limit: int) -> list[Article]:
        root = ET.fromstring(self._download_text(source.url, source.headers))
        if root.tag == f"{ATOM_NS}feed":
            return self._parse_atom(source, root, limit)
        return self._parse_rss(source, root, limit)

    def _parse_rss(self, source: Source, root: ET.Element, limit: int) -> list[Article]:
        channel = root.find("channel") or root
        items = channel.findall(".//item")[:limit]
        articles: list[Article] = []
        for item in items:
            url = _find_text(item, "link")
            title = _find_text(item, "title")
            summary = _clean_text(_html_to_text(_find_text(item, "description")))
            published = _normalize_published(_find_text(item, "pubDate"))
            content = self._safe_fetch_article_text(url, source.headers, fallback=summary)
            articles.append(
                Article(
                    source_name=source.name,
                    source_kind=source.kind,
                    title=title,
                    url=url,
                    summary=summary,
                    published=published,
                    content=content or summary,
                    tags=list(source.tags),
                    metadata={"authority_weight": source.authority_weight},
                )
            )
        return articles

    def _parse_atom(self, source: Source, root: ET.Element, limit: int) -> list[Article]:
        entries = root.findall(f"{ATOM_NS}entry")[:limit]
        articles: list[Article] = []
        for entry in entries:
            title = _find_text(entry, f"{ATOM_NS}title")
            url = ""
            for link in entry.findall(f"{ATOM_NS}link"):
                if link.attrib.get("rel", "alternate") == "alternate":
                    url = link.attrib.get("href", "")
                    break
            summary = _clean_text(
                _html_to_text(_find_text(entry, f"{ATOM_NS}summary") or _find_text(entry, f"{ATOM_NS}content"))
            )
            published = _normalize_published(
                _find_text(entry, f"{ATOM_NS}published") or _find_text(entry, f"{ATOM_NS}updated")
            )
            content = self._safe_fetch_article_text(url, source.headers, fallback=summary)
            articles.append(
                Article(
                    source_name=source.name,
                    source_kind=source.kind,
                    title=title,
                    url=url,
                    summary=summary,
                    published=published,
                    content=content or summary,
                    tags=list(source.tags),
                    metadata={"authority_weight": source.authority_weight},
                )
            )
        return articles

    def _fetch_json_feed(self, source: Source, limit: int) -> list[Article]:
        payload = json.loads(self._download_text(source.url, source.headers))
        articles: list[Article] = []
        for item in payload.get("items", [])[:limit]:
            url = item.get("url") or item.get("external_url") or ""
            summary = _clean_text(_html_to_text(item.get("summary", "")))
            content = self._safe_fetch_article_text(url, source.headers, fallback=summary)
            articles.append(
                Article(
                    source_name=source.name,
                    source_kind=source.kind,
                    title=item.get("title", ""),
                    url=url,
                    summary=summary,
                    published=_normalize_published(item.get("date_published", "")),
                    content=content or summary,
                    author=item.get("author", {}).get("name", ""),
                    tags=list(source.tags),
                    metadata={"authority_weight": source.authority_weight},
                )
            )
        return articles

    def _fetch_article_text(self, url: str, headers: dict[str, str]) -> str:
        if not url:
            return ""
        html = self._download_text(url, headers)
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg", "header", "footer", "nav", "aside", "form"]):
            tag.decompose()

        texts = []
        for selector in CONTENT_CANDIDATES:
            for node in soup.select(selector):
                text = _clean_text(node.get_text("\n", strip=True))
                if len(text) > 200:
                    texts.append(text)
        if texts:
            texts.sort(key=len, reverse=True)
            return texts[0][:8000]
        return _clean_text(soup.get_text("\n", strip=True))[:8000]

    def _safe_fetch_article_text(self, url: str, headers: dict[str, str], fallback: str) -> str:
        if not _should_fetch_page(url):
            return fallback
        try:
            return self._fetch_article_text(url, headers) or fallback
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            self.logger.warning("Article fetch fallback: url=%s error=%s", url, exc)
            return fallback

    def _download_text(self, url: str, headers: dict[str, str] | None = None) -> str:
        request_headers = {"User-Agent": USER_AGENT}
        if headers:
            request_headers.update({key: value for key, value in headers.items() if value})
        request = Request(url, headers=request_headers)
        with urlopen(request, timeout=self.timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="ignore")


def _find_text(node: ET.Element, tag: str) -> str:
    child = node.find(tag)
    if child is None:
        return ""
    return "".join(child.itertext()).strip()


def _html_to_text(value: str) -> str:
    return unescape(BeautifulSoup(value or "", "html.parser").get_text(" ", strip=True))


def _normalize_published(value: str) -> str:
    if not value:
        return ""
    try:
        return parsedate_to_datetime(value).isoformat()
    except (TypeError, ValueError, IndexError):
        pass
    try:
        return value.replace("Z", "+00:00")
    except AttributeError:
        return ""


def _should_fetch_page(url: str) -> bool:
    if not url:
        return False
    hostname = urlparse(url).netloc.lower()
    return "arxiv.org" not in hostname


def _clean_text(text: str) -> str:
    lines = [line.strip() for line in (text or "").splitlines()]
    kept_lines: list[str] = []
    for line in lines:
        if len(line) < 2:
            continue
        if any(pattern.match(line) for pattern in NOISE_PATTERNS):
            continue
        if line.lower().startswith(("menu ", "search ", "language ", "languages ")):
            continue
        kept_lines.append(line)
    cleaned = " ".join(kept_lines)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned
