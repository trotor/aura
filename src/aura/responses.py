"""Strukturoidut työkaluvastaukset: skeemat, virheet ja tekstiyhteenveto.

Vanhat työkalut palauttavat markdown-proosaa. Agentti joutuu jäsentämään
arvot, yksiköt ja ajankohdat tekstistä, ja jokainen muotoilumuutos rikkoo
sen hiljaa. Aikomustason työkalut (``find_data``, ``inspect_dataset``,
``query_source``, ``area_snapshot``, ``find_related``) palauttavat sen
sijaan MCP:n ``structuredContent``in, jonka muoto on julkaistu
``outputSchema``na — ja rinnalle enintään viiden rivin tekstiyhteenvedon
ihmiselle ja asiakkaille jotka eivät lue strukturoitua sisältöä.

Mallit ovat tarkoituksella sallivia (``extra="allow"``): laajennus voi
lisätä kenttiä rikkomatta skeemaa, ja skeeman on silti
kuvattava jokainen kenttä jonka avoin Aura itse täyttää.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastmcp.tools.tool import ToolResult
from mcp.types import TextContent
from pydantic import BaseModel, ConfigDict, Field

#: Tekstiyhteenvedon rivikatto. Yhteenveto on otsikko, ei vastaus.
MAX_SUMMARY_LINES = 5


class Model(BaseModel):
    model_config = ConfigDict(extra="allow")


class NextAction(Model):
    """Ehdotettu seuraava kutsu valmiine argumentteineen."""

    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    why: str | None = None


class ToolError(Model):
    """Koneluettava virhe: mitä meni pieleen ja miten korjataan."""

    code: str = Field(description="Pysyvä virhekoodi, esim. dataset_not_found")
    message: str
    hint: str | None = None
    suggested_call: NextAction | None = None


class Provenance(Model):
    """Mistä luku tai rivi tuli."""

    source: str = Field(description="Julkaisija")
    source_url: str | None = Field(default=None, description="Kyselyn täsmällinen URL")
    license: str | None = None
    retrieved_at: str | None = None
    dataset_id: str | None = None
    query: dict[str, Any] | None = Field(
        default=None, description="POST-kyselyn runko jos kysely ei mahdu URL:iin (PxWeb)"
    )


class AreaRef(Model):
    """Tulkittu alue."""

    level: str
    code: str
    name_fi: str
    name_sv: str = ""
    statfin_code: str | None = None
    query: str | None = None
    note: str | None = None


class Envelope(Model):
    """Kaikille vastauksille yhteiset kentät."""

    notes: list[str] = Field(default_factory=list)
    next_actions: list[NextAction] = Field(default_factory=list)
    error: ToolError | None = None


def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def schema_of(model: type[BaseModel]) -> dict[str, Any]:
    """outputSchema mallista. MCP vaatii objektiskeeman juureen."""
    schema = model.model_json_schema()
    schema.setdefault("type", "object")
    return schema


def respond(payload: BaseModel, summary: list[str] | str) -> ToolResult:
    """Rakenna MCP-vastaus: strukturoitu sisältö + lyhyt tekstiyhteenveto."""
    lines = [summary] if isinstance(summary, str) else list(summary)
    lines = [ln for ln in lines if ln][:MAX_SUMMARY_LINES]
    data = payload.model_dump(mode="json", exclude_none=True)
    return ToolResult(
        content=[TextContent(type="text", text="\n".join(lines) or "OK")],
        structured_content=data,
    )


def fail(
    model: type[Envelope],
    code: str,
    message: str,
    *,
    hint: str | None = None,
    suggested_call: NextAction | None = None,
    **fields: Any,
) -> ToolResult:
    """Virhevastaus samassa skeemassa kuin onnistunut vastaus.

    Virhe on osa vastausta eikä poikkeus: agentti saa koodin, vihjeen ja
    valmiin korjatun kutsun, ja skeema pysyy samana kumpaankin suuntaan.
    """
    err = ToolError(code=code, message=message, hint=hint, suggested_call=suggested_call)
    payload = model(error=err, **fields)
    summary = [f"Virhe ({code}): {message}"]
    if hint:
        summary.append(hint)
    return respond(payload, summary)
