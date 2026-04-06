from __future__ import annotations

from email.utils import parsedate_to_datetime
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlparse
import json
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

from ai_hotspot_monitor.models import Article, Source

USER_AGENT = "Mozilla/5.0 (compatible; ai-hotspot-monitor/0.1; +https://example.local)"
ATOM_NS = "{http://www.w3.org/2005/Atom}"
CONTENT_CANDIDATES = [
    "article",
    "main",
    "[role='main']",
    "[class*='content']",
    "[class*='article']",
    "[class*='post']",
    "[class*='body']",
    "body",
]


class ArticleFetcher:
    def __init__(self, timeout: int = 20) -> None:
        self.timeout = timeout

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
            summary = _html_to_text(_find_text(item, "description"))
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
            summary = _html_to_text(
                _find_text(entry, f"{ATOM_NS}summary") or _find_text(entry, f"{ATOM_NS}content")
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
            summary = _html_to_text(item.get("summary", ""))
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
        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()

        texts = []
        for selector in CONTENT_CANDIDATES:
            for node in soup.select(selector):
                text = node.get_text("\n", strip=True)
                if len(text) > 160:
                    texts.append(text)
        if texts:
            texts.sort(key=len, reverse=True)
            return texts[0][:8000]
        return soup.get_text("\n", strip=True)[:8000]

    def _safe_fetch_article_text(self, url: str, headers: dict[str, str], fallback: str) -> str:
        if not _should_fetch_page(url):
            return fallback
        try:
            return self._fetch_article_text(url, headers) or fallback
        except (HTTPError, URLError, TimeoutError, ValueError):
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
