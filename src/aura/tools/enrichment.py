"""Rikastustyökalut: enrich, batch_enrich, suggest_yso_tags, get_enrichments_tool."""

from __future__ import annotations

from fastmcp import Context

import aura.server as _server
from aura.database import (
    add_enrichment,
    get_dataset,
    get_latest_enrichments,
)
from aura.search import format_enrichments
from aura.server import mcp
from aura.yso import YsoClient

VALID_ENRICHMENT_FIELDS = {
    "description_extended", "api_endpoint", "api_format",
    "data_fields", "keywords", "tags",
    "related_datasets", "related_services", "quality_notes",
    "use_case", "access_instructions", "organization_context",
    "temporal_coverage", "update_frequency_actual",
    "yso_concepts",
}

MAX_ENRICHMENT_VALUE_LENGTH = 10_000


@mcp.tool()
def enrich(
    dataset_id: str,
    field: str,
    value: str,
    confidence: str = "medium",
    source_type: str = "mcp_session",
    source_detail: str = "",
    ctx: Context | None = None,
) -> str:
    """Rikasta datasetin tietoja. Tallentaa löydetyn tiedon kantaan.

    Käytä tätä kun löydät uutta tietoa datasetistä tutkimuksen aikana.

    Args:
        dataset_id: Datasetin ID tai nimi
        field: Rikastettava kenttä. Tuetut kentät:
            - description_extended: laajennettu kuvaus
            - api_endpoint: löydetty rajapinta-URL
            - api_format: rajapinnan formaatti (REST, WFS, OData, jne.)
            - data_fields: JSON-lista datasetin kentistä/sarakkeista
            - keywords: lisäavainsanat JSON-listana (esim. '["maatalous", "peltolohko"]')
            - tags: vapaamuotoiset tagit JSON-listana (esim. '["paikkatietoaineisto", "INSPIRE"]')
            - related_datasets: liittyvät datasetit
            - related_services: palvelut jotka käyttävät dataa JSON-listana
                (esim. '["Reittiopas", "Karttapalvelu"]')
            - quality_notes: huomioita datan laadusta
            - use_case: käyttötapausesimerkki
            - access_instructions: ohjeet datan hakemiseen
            - organization_context: taustatietoa julkaisijasta
            - temporal_coverage: ajallinen kattavuus
            - update_frequency_actual: havaittu päivitystiheys
        value: Rikastuksen arvo (teksti tai JSON-merkkijono)
        confidence: Luottamustaso: "low", "medium", "high", "verified"
        source_type: Lähdetyyppi: "mcp_session", "web_research",
            "manual", "ai_analysis"
        source_detail: Lähteen kuvaus tai URL
    """
    conn = _server._get_conn(ctx)

    if field not in VALID_ENRICHMENT_FIELDS:
        fields_list = ", ".join(sorted(VALID_ENRICHMENT_FIELDS))
        return f"Tuntematon kenttä '{field}'. Tuetut: {fields_list}"

    valid_confidence = {"low", "medium", "high", "verified"}
    if confidence not in valid_confidence:
        return f"Virheellinen luottamustaso '{confidence}'."

    if len(value) > MAX_ENRICHMENT_VALUE_LENGTH:
        return f"Arvo saa olla korkeintaan {MAX_ENRICHMENT_VALUE_LENGTH} merkkiä."

    if not get_dataset(conn, dataset_id):
        return f"Datasettiä '{dataset_id}' ei löytynyt."

    enrichment_id = add_enrichment(
        conn, dataset_id, field, value,
        confidence=confidence,
        source_type=source_type,
        source_detail=source_detail,
    )
    return (
        f"Rikastus tallennettu (id: {enrichment_id}). "
        f"Datasetti: {dataset_id}, kenttä: {field}."
    )


@mcp.tool()
def batch_enrich(
    enrichments: list[dict[str, str]],
    ctx: Context | None = None,
) -> str:
    """Tallenna useita rikastuksia kerralla.

    Tehokkaampi kuin yksittäiset enrich()-kutsut kun haluat
    tallentaa monta löydöstä samalla kertaa.

    Args:
        enrichments: Lista rikastuksista. Jokainen sisältää:
            - dataset_id: Datasetin ID tai nimi
            - field: Rikastettava kenttä (samat kuin enrich()-työkalussa)
            - value: Rikastuksen arvo
            - confidence: (valinnainen) "low"/"medium"/"high"/"verified"
            - source_type: (valinnainen) lähdetyyppi
            - source_detail: (valinnainen) lähteen kuvaus
    """
    conn = _server._get_conn(ctx)

    results: list[str] = []
    errors: list[str] = []

    for i, e in enumerate(enrichments):
        ds_id = e.get("dataset_id", "")
        field = e.get("field", "")
        value = e.get("value", "")

        if not ds_id or not field or not value:
            errors.append(f"#{i + 1}: puuttuva dataset_id/field/value")
            continue
        if field not in VALID_ENRICHMENT_FIELDS:
            errors.append(f"#{i + 1}: tuntematon kenttä '{field}'")
            continue
        if len(value) > MAX_ENRICHMENT_VALUE_LENGTH:
            errors.append(f"#{i + 1}: arvo liian pitkä ({len(value)} merkkiä)")
            continue
        if not get_dataset(conn, ds_id):
            errors.append(f"#{i + 1}: datasettiä '{ds_id}' ei löytynyt")
            continue

        add_enrichment(
            conn, ds_id, field, value,
            confidence=e.get("confidence", "medium"),
            source_type=e.get("source_type", "mcp_session"),
            source_detail=e.get("source_detail", ""),
        )
        results.append(f"- {ds_id}/{field}")

    parts: list[str] = []
    if results:
        parts.append(f"Tallennettu {len(results)} rikastusta:")
        parts.extend(results)
    if errors:
        parts.append(f"\nVirheet ({len(errors)}):")
        parts.extend(errors)
    if not results and not errors:
        parts.append("Ei rikastuksia tallennettavaksi.")

    return "\n".join(parts)


@mcp.tool()
async def suggest_yso_tags(
    dataset_id: str,
    save: bool = False,
    ctx: Context | None = None,
) -> str:
    """Ehdota YSO-ontologian mukaisia avainsanoja datasetille.

    Analysoi datasetin otsikon, kuvauksen ja olemassaolevat avainsanat
    ja etsii vastaavat YSO-käsitteet Finto API:sta.

    Args:
        dataset_id: Datasetin ID tai nimi
        save: Jos True, tallenna ehdotukset yso_concepts-enrichmentiksi
    """
    conn = _server._get_conn(ctx)
    yso = _server._get_yso(ctx)
    if not yso:
        yso = YsoClient()

    dataset = get_dataset(conn, dataset_id)
    if not dataset:
        return f"Datasettiä '{dataset_id}' ei löytynyt."

    from aura.tagger import format_suggestions
    from aura.tagger import suggest_tags as _suggest_tags

    suggestions = await _suggest_tags(dataset, yso)

    if save and suggestions:
        import json as _json

        concepts_json = _json.dumps(
            [s.to_dict() for s in suggestions], ensure_ascii=False,
        )
        add_enrichment(
            conn,
            dataset_id=dataset["id"],
            field="yso_concepts",
            value=concepts_json,
            confidence="high",
            source_type="ai_analysis",
            source_detail="YSO auto-tagger",
        )
        conn.commit()
        return (
            format_suggestions(suggestions)
            + f"\n\nTallennettu {len(suggestions)} YSO-käsitettä enrichmentiksi."
        )

    return format_suggestions(suggestions)


@mcp.tool()
def get_enrichments_tool(dataset_id: str, ctx: Context | None = None) -> str:
    """Näytä datasetin rikastukset (crowdsourced enrichments).

    Args:
        dataset_id: Datasetin ID tai nimi
    """
    conn = _server._get_conn(ctx)
    enrichments = get_latest_enrichments(conn, dataset_id)

    if not enrichments:
        return f"Ei rikastuksia datasetille '{dataset_id}'."

    return format_enrichments(enrichments)
