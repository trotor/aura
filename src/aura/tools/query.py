"""PxWeb-kyselyapufunktiot.

Käytetään query_data-työkalusta. Ei rekisteröi omia MCP-työkaluja.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)
_HTTP_TIMEOUT = 30.0
_MAX_RESULT_ROWS = 500


def _find_pxweb_url(dataset: dict[str, Any]) -> str | None:
    """Etsi PXWEB-resurssin URL datasetistä."""
    for r in dataset.get("resources", []):
        if (r.get("format") or "").upper() == "PXWEB":
            return r.get("url")
    return None


def _resolve_values(
    meta_var: dict[str, Any],
    user_values: list[str],
) -> list[str]:
    """Muunna käyttäjän tekstiarvot PxWeb-koodeiksi.

    Esim. "Tampere" → "KU837", "Helsinki" → "KU091".
    Jos arvo on jo koodi, käytetään sellaisenaan.
    """
    values = meta_var.get("values", [])
    value_texts = meta_var.get("valueTexts", [])

    # Rakennetaan text → code -mapping
    text_to_code: dict[str, str] = {}
    for i, txt in enumerate(value_texts):
        if i < len(values):
            text_to_code[txt.lower()] = values[i]

    resolved = []
    for uv in user_values:
        uv_lower = uv.lower()
        # Tarkista onko jo koodi
        if uv in values:
            resolved.append(uv)
            continue
        # Tarkista tarkka vastaavuus textiin
        if uv_lower in text_to_code:
            resolved.append(text_to_code[uv_lower])
            continue
        # Osittainen haku (esim. "Tampere" osuu "Tampere - Tammerfors")
        matches = [
            code for txt, code in text_to_code.items()
            if uv_lower in txt
        ]
        if len(matches) == 1:
            resolved.append(matches[0])
        elif matches:
            # Useita osumia — käytä ensimmäistä
            resolved.append(matches[0])
        else:
            # Ei löytynyt — käytä sellaisenaan
            resolved.append(uv)

    return resolved


def _format_dimensions_help(
    variables: list[dict[str, Any]],
    ds_name: str,
) -> str:
    """Muotoile ohje dimensioista kun filttereitä ei annettu."""
    parts = ["**Taulun dimensiot:**\n"]

    filter_example: dict[str, list[str]] = {}
    for var in variables:
        code = var.get("code", "")
        text = var.get("text", code)
        values = var.get("values", [])
        value_texts = var.get("valueTexts", [])
        examples = value_texts[:5] if value_texts else values[:5]
        ex_str = ", ".join(f'"{x}"' for x in examples)

        parts.append(f"- **{text}** (`{code}`): {len(values)} arvoa")
        if ex_str:
            parts.append(f"  Esim: {ex_str}")

        # Rakenna esimerkkifiltteri
        if value_texts:
            filter_example[code] = [value_texts[0]]
        elif values:
            filter_example[code] = [values[0]]

    # Näytä esimerkkikysely
    filter_json = json.dumps(filter_example, ensure_ascii=False)
    parts.append(
        f'\n**Esimerkki:**\n```\nquery_pxweb(\n'
        f'  dataset_id="{ds_name}",\n'
        f'  filters={filter_json}\n'
        f')\n```'
    )

    return "\n".join(parts)


def _parse_json_stat2(data: dict[str, Any], max_rows: int) -> str:
    """Parsii json-stat2-vastauksen markdown-taulukoksi."""
    # json-stat2: dimension + id + size + value
    dim_ids = data.get("id", [])
    sizes = data.get("size", [])
    dimensions = data.get("dimension", {})
    flat_values = data.get("value", [])

    if not dim_ids or not flat_values:
        return "Tyhjä vastaus PxWeb-palvelimelta."

    # Rakennetaan dimensioiden label-listat
    dim_labels: list[list[str]] = []
    for dim_id in dim_ids:
        dim_info = dimensions.get(dim_id, {})
        cat = dim_info.get("category", {})
        cat_index = cat.get("index", {})
        cat_label = cat.get("label", {})

        # Järjestä indeksin mukaan
        if isinstance(cat_index, dict):
            ordered = sorted(cat_index.items(), key=lambda x: x[1])
            labels = [cat_label.get(code, code) for code, _ in ordered]
        else:
            dim_size = sizes[dim_ids.index(dim_id)]
            labels = list(cat_label.values()) if cat_label else [str(i) for i in range(dim_size)]
        dim_labels.append(labels)

    # Laske rivien kokonaismäärä
    total_rows = 1
    for s in sizes:
        total_rows *= s

    # Puretaan flat values taulukkoon
    headers = dim_ids + ["Arvo"]
    table_rows: list[list[str]] = []

    for flat_idx in range(min(total_rows, max_rows)):
        row_labels: list[str] = []
        remaining = flat_idx
        for d_idx in range(len(dim_ids) - 1, -1, -1):
            s = sizes[d_idx]
            pos = remaining % s
            remaining //= s
            label = dim_labels[d_idx][pos] if pos < len(dim_labels[d_idx]) else str(pos)
            row_labels.insert(0, label)

        val = flat_values[flat_idx] if flat_idx < len(flat_values) else ""
        if val is None:
            val = ".."
        row_labels.append(str(val))
        table_rows.append(row_labels)

    # Markdown-taulukko
    parts = ["| " + " | ".join(headers) + " |"]
    parts.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in table_rows:
        cells = [str(c).replace("|", "\\|")[:60] for c in row]
        parts.append("| " + " | ".join(cells) + " |")

    footer = ""
    if total_rows > max_rows:
        footer = f"\n\n*Näytetään {len(table_rows)}/{total_rows} riviä.*"

    return "\n".join(parts) + footer


async def query_pxweb(
    dataset_id: str,
    filters: dict[str, list[str]] | None = None,
    columns: list[str] | None = None,
    max_rows: int = 20,
    ctx: Any = None,
) -> str:
    """Backward-compat alias: delegoi query_data-työkaluun."""
    from aura.tools.data import query_data

    return await query_data(
        dataset_id=dataset_id,
        filters=filters,
        columns=columns,
        max_rows=max_rows,
        ctx=ctx,
    )
