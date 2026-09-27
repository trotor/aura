"""Harvester Kelan tilastotietokanta Kelaston raporteille.

Kelasto siirtyi Kelan Tietotarjottimeen (``tietotarjotin.fi``), joka on
yhden sivun sovellus. Sen takana ei ole datarajapintaa: raportit ovat
WebFOCUS- (``raportit.kela.fi``) ja Cognos-raportteja (``tilastot.kela.fi``),
joissa valinnat tehdään lomakkeella. Raporttiluettelo on kuitenkin
koneluettava Tietotarjottimen artikkelirajapinnasta (``/api/node-cache``),
kolmella kielellä ja aihe-otsikoittain.

Tämä harvesteri tekee raporteista löydettäviä. ``query_source`` ei voi
kysellä niitä — resurssi on ihmiselle tarkoitettu raporttilomake. Osa
Kelan tilastoista on avoimena datana avoindata.fi:ssä, ja ne tulevat
katalogiin sitä kautta.

Lisenssi: artikkeli ilmoittaa CC BY 4.0:n (tarkistettu 27.9.2026).
"""

from __future__ import annotations

import html
import logging
import re
from typing import Any
from urllib.parse import parse_qs, unquote_plus, urlparse

from aura.database import upsert_dataset
from aura.harvesters.base import BaseHarvester
from aura.models import Resource

logger = logging.getLogger(__name__)

ARTICLE_URL = "https://tietotarjotin.fi/api/node-cache/articles/2051231"
PAGE_URL = "https://tietotarjotin.fi/tilastotietokanta-kelasto"

_TOKEN = re.compile(
    r"<h([2-4])[^>]*>(?P<heading>.*?)</h\1>"
    r"|<a[^>]+href=\"(?P<href>https?://(?:raportit|tilastot)\.kela\.fi/[^\"]+)\"[^>]*>"
    r"(?P<text>.*?)</a>",
    re.S,
)
_TAGS = re.compile(r"<[^>]+>")


def _clean(fragment: str) -> str:
    return " ".join(html.unescape(_TAGS.sub(" ", fragment)).split())


def report_key(url: str) -> str | None:
    """Raportin kielestä riippumaton avain: WebFOCUS-koodi tai Cognos-polku."""
    parsed = urlparse(html.unescape(url))
    query = parse_qs(parsed.query)
    if "IBIF_ex" in query:
        return query["IBIF_ex"][0]
    if "pathRef" in query:
        # Polku on koodattu kahteen kertaan (``%2528`` → ``(``). Raportin
        # nimen lopussa on sulkeissa koodi, joka on sama kaikilla kielillä.
        name = unquote_plus(query["pathRef"][0]).rstrip("/").rsplit("/", 1)[-1]
        code = re.search(r"\((\w+)\)\s*$", name)
        return code.group(1) if code else name
    return None


def parse_reports(content: str) -> list[dict[str, Any]]:
    """Raportit artikkelin HTML:stä: avain, otsikko, url ja otsikkopolku."""
    headings: dict[int, str] = {}
    reports: list[dict[str, Any]] = []
    seen: set[str] = set()
    for m in _TOKEN.finditer(content):
        if m.group("heading") is not None:
            level = int(m.group(1))
            headings = {k: v for k, v in headings.items() if k < level}
            headings[level] = _clean(m.group("heading"))
            continue
        url = html.unescape(m.group("href"))
        key = report_key(url)
        title = _clean(m.group("text"))
        if not key or not title or key in seen:
            continue
        seen.add(key)
        reports.append(
            {
                "key": key,
                "title": title,
                "url": url,
                "themes": [headings[k] for k in sorted(headings)],
            }
        )
    return reports


def _slug(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-")[:80]


class KelastoHarvester(BaseHarvester):
    """Kerää Kelaston raportit Tietotarjottimen artikkelista."""

    name = "kelasto"
    description = "Kelasto — Kelan tilastotietokannan raportit (Tietotarjotin)"
    url = PAGE_URL

    async def harvest(self) -> int:
        async with self._make_client(timeout=60.0) as client:
            article: dict[str, Any] = (await self._fetch(client, ARTICLE_URL)).json()[0]

        def content(lang: str) -> str:
            return " ".join(part.get("content", "") for part in article.get(f"content_{lang}", []))

        reports = parse_reports(content("fi"))
        other = {lang: {r["key"]: r for r in parse_reports(content(lang))} for lang in ("en", "sv")}
        for report in reports:
            self._save(report, other["en"].get(report["key"]), other["sv"].get(report["key"]))
        self.conn.commit()
        logger.info("[kelasto] %d raporttia", len(reports))
        return len(reports)

    def _save(
        self,
        report: dict[str, Any],
        en: dict[str, Any] | None,
        sv: dict[str, Any] | None,
    ) -> None:
        dataset_id = f"kelasto-{_slug(report['key'])}"
        engine = "WebFOCUS" if "raportit.kela.fi" in report["url"] else "Cognos"
        themes = report["themes"]
        notes = (
            f"Kelan tilastotietokanta Kelaston raportti ({engine}). Raportissa "
            "valinnat tehdään lomakkeella; tiedot päivittyvät kuukausittain. "
            f"Aihe: {' / '.join(themes) or 'Kelasto'}."
        )
        resources = [
            Resource(
                id=f"{dataset_id}-fi",
                name=f"{report['title']} (raportti)",
                name_fi="Kelasto-raportti (suomi)",
                format="HTML",
                url=report["url"],
            )
        ]
        if en and en["url"] != report["url"]:
            resources.append(
                Resource(
                    id=f"{dataset_id}-en",
                    name=f"{en['title']} (report)",
                    name_fi="Kelasto-raportti (englanti)",
                    format="HTML",
                    url=en["url"],
                )
            )
        dataset = self._make_dataset(
            id=dataset_id,
            name=dataset_id,
            title=report["title"],
            title_fi=report["title"],
            title_en=en["title"] if en else "",
            title_sv=sv["title"] if sv else "",
            notes=notes,
            notes_fi=notes,
            organization_id="kela",
            organization_name="kela",
            organization_title="Kansaneläkelaitos (Kela)",
            keywords_fi=list(dict.fromkeys(["Kela", "sosiaaliturva", *themes])),
            keywords_en=list(
                dict.fromkeys(["Kela", "social security", *(en or {}).get("themes", [])])
            ),
            update_frequency="kuukausittain",
            resources=resources,
        )
        upsert_dataset(self.conn, dataset)
