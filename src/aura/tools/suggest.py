"""Esimerkkikysymysten ehdotus: suggest_questions."""

from __future__ import annotations

from typing import Any

from fastmcp import Context

import aura.server as _server
from aura.server import mcp
from aura.tools.search import _resolve_region

# Teemat ja niihin liittyvät hakusanat + mallilauseet
_THEMES: list[dict[str, Any]] = [
    {
        "name": "Väestö",
        "keywords": ["väestö", "asukas", "muutto", "syntyvyys", "kuolleisuus"],
        "questions": [
            ("Hae {region} väestörakenne", 'search_by_region("{region}", "väestörakenne")'),
            ("Väestöennuste alueittain", 'search("väestöennuste")'),
            (
                "{region} muuttoliike",
                'search_by_region("{region}", "muuttoliike")',
            ),
        ],
    },
    {
        "name": "Talous",
        "keywords": ["talous", "budjetti", "vero", "työllisyys", "työttömyys"],
        "questions": [
            ("Kuntatalouden tunnusluvut", 'search("kuntatalous")'),
            ("{region} talousarvio", 'search_by_region("{region}", "talousarvio")'),
            ("Työttömyysaste alueittain", 'search("työttömyysaste")'),
        ],
    },
    {
        "name": "Liikenne",
        "keywords": ["liikenne", "tie", "joukkoliikenne", "pysäköinti", "rata"],
        "questions": [
            ("{region} liikennemäärät", 'search_by_region("{region}", "liikenne")'),
            ("Joukkoliikenteen reittidata", 'search("joukkoliikenne", format="JSON")'),
            ("Nopeusrajoitukset kartalla", 'search("nopeusrajoitus", format="WFS")'),
        ],
    },
    {
        "name": "Ympäristö",
        "keywords": ["ympäristö", "ilmanlaatu", "vesi", "luonto", "metsä", "sää"],
        "questions": [
            ("{region} ilmanlaatu", 'search_by_region("{region}", "ilmanlaatu")'),
            ("Vesistöjen tila", 'search("vesistö tila")'),
            ("Säähavainnot reaaliajassa", 'search("säähavainto", source="fmi")'),
        ],
    },
    {
        "name": "Kartat ja paikkatieto",
        "keywords": ["kartta", "paikkatieto", "kiinteistö", "kaava", "maasto"],
        "questions": [
            ("{region} ajantasa-asemakaava", 'search_by_region("{region}", "asemakaava")'),
            ("Kiinteistörajat kartalla", 'search("kiinteistöraja", format="WFS")'),
            ("{region} rakennukset", 'search_by_region("{region}", "rakennus")'),
        ],
    },
    {
        "name": "Koulutus",
        "keywords": ["koulu", "oppilas", "koulutus", "päiväkoti"],
        "questions": [
            ("{region} kouluverkko", 'search_by_region("{region}", "koulu")'),
            ("Oppilaitokset kartalla", 'search("oppilaitos", format="WFS")'),
        ],
    },
    {
        "name": "Terveys ja hyvinvointi",
        "keywords": ["terveys", "sote", "hyvinvointi", "sairastavuus"],
        "questions": [
            ("{region} terveystilastot", 'search_by_region("{region}", "terveys")'),
            ("Sairastavuusindeksi kunnittain", 'search("sairastavuusindeksi")'),
        ],
    },
    {
        "name": "Asuminen ja rakentaminen",
        "keywords": ["asuminen", "asunto", "rakentaminen", "rakennuslupa"],
        "questions": [
            ("{region} asuntokanta", 'search_by_region("{region}", "asuntokanta")'),
            ("Rakennusluvat kunnittain", 'search("rakennuslupa")'),
        ],
    },
    {
        "name": "Energia",
        "keywords": ["energia", "sähkö", "kaukolämpö", "tuulivoima"],
        "questions": [
            ("Sähkönkulutus alueittain", 'search("sähkönkulutus")'),
            ("Tuulivoimaloiden sijainnit", 'search("tuulivoima", format="WFS")'),
        ],
    },
]


def _count_theme_datasets(
    conn: Any, theme_keywords: list[str], region_names: list[str] | None,
) -> int:
    """Laske kuinka monta datasettiä teemaan osuu."""
    keyword_conditions = " OR ".join(
        "(d.keywords_fi LIKE ? OR d.title_fi LIKE ?)" for _ in theme_keywords
    )
    params: list[str] = []
    for kw in theme_keywords:
        params.extend([f"%{kw}%", f"%{kw}%"])

    region_clause = ""
    if region_names:
        region_parts = " OR ".join(
            "d.geographical_coverage LIKE ?" for _ in region_names
        )
        region_clause = f" AND ({region_parts})"
        params.extend(f"%{name}%" for name in region_names)

    sql = f"""
        SELECT COUNT(*) FROM datasets d
        WHERE ({keyword_conditions}){region_clause}
    """
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else 0


@mcp.tool()
def suggest_questions(
    region: str = "",
    theme: str = "",
    ctx: Context | None = None,
) -> str:
    """Ehdota konkreettisia kysymyksiä joihin Aura voi vastata.

    Auttaa ensikäyttäjää pääsemään alkuun näyttämällä esimerkkejä
    siitä, mitä dataa on saatavilla ja miten sitä voi hakea.

    Args:
        region: Alue (esim. "Tampere", "Pirkanmaa") — räätälöi kysymykset alueelle
        theme: Teema (esim. "väestö", "liikenne") — rajaa tiettyyn aihepiiriin
    """
    conn = _server._get_conn(ctx)

    # Resolvoi alue
    region_clean = region.strip()
    region_names: list[str] | None = None
    display_region = region_clean or "Tampere"  # oletus esimerkkeihin

    if region_clean:
        region_names = _resolve_region(conn, region_clean)
        if not region_names:
            region_names = [region_clean]

    # Suodata teemat
    theme_lower = theme.strip().lower()
    themes_to_show = _THEMES
    if theme_lower:
        themes_to_show = [
            t for t in _THEMES
            if theme_lower in t["name"].lower()
            or any(theme_lower in kw for kw in t["keywords"])
        ]
        if not themes_to_show:
            themes_to_show = _THEMES  # fallback: näytä kaikki

    parts: list[str] = []
    title = "Esimerkkikysymyksiä"
    if region_clean:
        title += f" — {region_clean}"
    if theme:
        title += f" ({theme})"
    parts.append(f"# {title}\n")

    shown_themes = 0
    for t in themes_to_show:
        # Laske osumat
        count = _count_theme_datasets(conn, t["keywords"], region_names)

        # Ohita tyhjät teemat jos on aluerajaus
        if region_clean and count == 0:
            continue

        shown_themes += 1
        count_str = f" — {count} datasettiä" if count > 0 else ""
        parts.append(f"## {t['name']}{count_str}\n")

        for question_tpl, tool_tpl in t["questions"]:
            question = question_tpl.format(region=display_region)
            tool_call = tool_tpl.format(region=display_region)
            parts.append(f"- \"{question}\" → `{tool_call}`")
        parts.append("")

    if shown_themes == 0:
        parts.append(
            "Alueelle ei löytynyt kohdistettua dataa. "
            "Kokeile laajempaa aluetta tai jätä alue tyhjäksi.\n"
        )

    # Lisää yleisiä vinkkejä
    parts.append("## Yleiset työkalut\n")
    parts.append(
        "- **Vertaile kuntia**: "
        '`compare_municipalities(["Tampere", "Turku", "Oulu"])`'
    )
    parts.append(
        f"- **Alueprofiili**: `area_profile(\"{display_region}\")`"
    )
    parts.append(
        "- **Datan laatu**: `quality_overview()`"
    )
    parts.append(
        "- **Tietyn datasetin esikatselu**: "
        '`query_data("datasetin-id")`'
    )
    parts.append("")

    return "\n".join(parts)
