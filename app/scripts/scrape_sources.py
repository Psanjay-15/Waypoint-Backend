"""Scrape official state websites into clean, chunked JSON.

    python -m app.scripts.scrape_sources              # all states in app/data/sources/
    python -m app.scripts.scrape_sources --states ca  # just one

HOW THIS WORKS (the whole pipeline in one breath):
  1. Read the source registry (app/data/sources/{state}.json) — a hand-curated
     list of official URLs, each tagged with category/topic. The registry is the
     only thing you edit to scrape more pages.
  2. For each URL, politely download it: identify ourselves with a User-Agent,
     respect robots.txt, wait between requests so we never hammer a .gov server.
  3. Turn the raw download into clean text:
       - HTML: parse the tag tree with BeautifulSoup, delete navigation/menus/
         scripts, keep the main content (headings, paragraphs, list items).
       - PDF:  extract text page by page with pypdf, remembering page numbers
         so citations can say "page 12".
  4. Split long text into overlapping CHUNKS (~1,200 chars). LLM context and
     vector search both work on chunks, not 50-page documents: small pieces
     embed more precisely and retrieve more relevantly.
  5. Write everything to app/data/scraped/{state}.json — flat key/value records
     carrying full provenance (url, source name, page number, scraped_at,
     content_hash) so every chunk can be cited and re-verified later.

Nothing here touches Postgres or Qdrant — that is ingest_scraped.py's job.
Scrape once, inspect the JSON, ingest when happy.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
import re
from datetime import date
from urllib import robotparser
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader

from app.config import settings
from app.core.logging import configure_logging, get_logger

log = get_logger(__name__)

SOURCES_DIR = settings.data_dir.parent / "sources"
SCRAPED_DIR = settings.data_dir.parent / "scraped"

USER_AGENT = "StateShiftBot/0.1 (+hackathon research project; respectful crawler)"
DELAY_SECONDS = 1.0
TIMEOUT = httpx.Timeout(30.0)

CHUNK_TARGET = 1200
CHUNK_OVERLAP = 150
MIN_CHUNK_CHARS = 200

STRIP_TAGS = (
    "script",
    "style",
    "nav",
    "header",
    "footer",
    "aside",
    "form",
    "noscript",
    "iframe",
    "svg",
    "button",
)

_robots_cache: dict[str, robotparser.RobotFileParser] = {}


async def allowed_by_robots(client: httpx.AsyncClient, url: str) -> bool:
    """Check the site's robots.txt before fetching. Sites publish this file to
    say which paths crawlers may visit; ignoring it is rude (and sometimes
    legally risky). If robots.txt is missing/unreachable we assume allowed."""
    origin = "{0.scheme}://{0.netloc}".format(urlparse(url))
    rp = _robots_cache.get(origin)
    if rp is None:
        rp = robotparser.RobotFileParser()
        try:
            resp = await client.get(f"{origin}/robots.txt")
            rp.parse(resp.text.splitlines() if resp.status_code == 200 else [])
        except httpx.HTTPError:
            rp.parse([])
        _robots_cache[origin] = rp
    return rp.can_fetch(USER_AGENT, url)


def _clean(text: str) -> str:
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_html(html: str) -> str:
    """Parse the HTML tag tree and keep only readable content.

    BeautifulSoup turns the page into a tree we can walk. We delete chrome
    (menus, scripts, footers), then prefer the <main>/<article> element —
    the HTML5 marker for primary content — falling back to <body>.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(STRIP_TAGS):
        tag.decompose()

    root = soup.find("main") or soup.find("article") or soup.body or soup

    lines: list[str] = []
    for el in root.find_all(["h1", "h2", "h3", "h4", "p", "li", "td", "th"]):
        text = el.get_text(" ", strip=True)
        if not text:
            continue
        if el.name.startswith("h"):
            lines.append(f"\n## {text}\n")
        else:
            lines.append(text)
    return _clean("\n".join(lines))


def extract_pdf(data: bytes) -> list[tuple[int, str]]:
    """Return [(page_number, text), ...] so chunks can cite exact pages."""
    reader = PdfReader(io.BytesIO(data))
    pages: list[tuple[int, str]] = []
    for i, page in enumerate(reader.pages, start=1):
        text = _clean(page.extract_text() or "")
        if text:
            pages.append((i, text))
    return pages


def chunk_text(
    text: str, target: int = CHUNK_TARGET, overlap: int = CHUNK_OVERLAP
) -> list[str]:
    """Greedily pack paragraphs into ~target-char chunks with a small overlap."""
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if current and len(current) + len(para) + 1 > target:
            chunks.append(current)
            current = current[-overlap:] + "\n" + para
        else:
            current = f"{current}\n{para}" if current else para
    if current:
        chunks.append(current)
    return [c.strip() for c in chunks if len(c.strip()) >= MIN_CHUNK_CHARS]


def _record(
    source: dict, state: str, text: str, index: int, page_number: int | None
) -> dict:
    """One flat key/value record per chunk — full provenance for citations."""
    return {
        "state": state,
        "category": source["category"],
        "topic": source["topic"],
        "source_name": source["name"],
        "source_url": source["url"],
        "doc_type": source["type"],
        "page_number": page_number,
        "chunk_index": index,
        "text": text,
        "content_hash": hashlib.sha256(text.encode()).hexdigest()[:16],
        "scraped_at": date.today().isoformat(),
    }


async def scrape_source(
    client: httpx.AsyncClient, state: str, source: dict
) -> tuple[list[dict], str]:
    """Fetch one registry entry. Returns (chunk_records, status_string)."""
    url = source["url"]
    if not await allowed_by_robots(client, url):
        return [], "blocked by robots.txt"
    try:
        resp = await client.get(url)
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        return [], f"HTTP {exc.response.status_code}"
    except httpx.HTTPError as exc:
        return [], f"fetch failed: {type(exc).__name__}"

    records: list[dict] = []
    content_type = resp.headers.get("content-type", "")
    if source["type"] == "pdf" or "application/pdf" in content_type:
        try:
            pages = extract_pdf(resp.content)
        except Exception as exc:
            return [], f"pdf parse failed: {exc}"
        index = 0
        for page_no, page_text in pages:
            for piece in chunk_text(page_text):
                records.append(_record(source, state, piece, index, page_no))
                index += 1
    else:
        text = extract_html(resp.text)
        for index, piece in enumerate(chunk_text(text)):
            records.append(_record(source, state, piece, index, None))

    if not records:
        return [], "no usable text extracted"
    return records, f"ok ({len(records)} chunks)"


async def scrape_state(client: httpx.AsyncClient, registry_path) -> None:
    registry = json.loads(registry_path.read_text())
    state = registry["state"]
    all_chunks: list[dict] = []
    report: list[dict] = []

    prev_by_url: dict[str, list[dict]] = {}
    prev_path = SCRAPED_DIR / f"{state.lower()}.json"
    if prev_path.exists():
        for chunk in json.loads(prev_path.read_text()).get("chunks", []):
            prev_by_url.setdefault(chunk["source_url"], []).append(chunk)

    for source in registry["sources"]:
        records, status = await scrape_source(client, state, source)
        if not records and source["url"] in prev_by_url:
            records = prev_by_url[source["url"]]
            status = f"{status} — kept {len(records)} chunks from previous scrape"
        all_chunks.extend(records)
        report.append({"name": source["name"], "url": source["url"], "status": status})
        log.info("[%s] %-55s %s", state, source["name"][:55], status)
        await asyncio.sleep(DELAY_SECONDS)

    SCRAPED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SCRAPED_DIR / f"{state.lower()}.json"
    out_path.write_text(
        json.dumps(
            {
                "state": state,
                "scraped_at": date.today().isoformat(),
                "report": report,
                "chunks": all_chunks,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    ok = sum(1 for r in report if r["status"].startswith("ok"))
    log.info(
        "[%s] wrote %s — %d/%d sources ok, %d chunks",
        state,
        out_path.name,
        ok,
        len(report),
        len(all_chunks),
    )


async def main(states: list[str] | None) -> None:
    paths = sorted(SOURCES_DIR.glob("*.json"))
    if states:
        wanted = {s.strip().lower() for s in states}
        paths = [p for p in paths if p.stem in wanted]
    if not paths:
        log.error("no source registries found in %s", SOURCES_DIR)
        return
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, follow_redirects=True
    ) as client:
        for path in paths:
            await scrape_state(client, path)


if __name__ == "__main__":
    configure_logging()
    parser = argparse.ArgumentParser(
        description="Scrape official state sources into JSON"
    )
    parser.add_argument("--states", help="comma-separated registry names, e.g. ca,ny")
    args = parser.parse_args()
    asyncio.run(main(args.states.split(",") if args.states else None))
