"""inspect_dataset: tekstiyhteenveto, kyselyohje ja WFS-kenttien kerros.

Ulkoinen arvio 27.9.2026: tekstiyhteenvedossa oli vain otsikko, lisenssi,
formaatit ja laatu — kuvaus, päivitys, kentät ja saatavuus olivat vain
rakenteisessa sisällössä. Kyselyohje ``query_source(dataset_id)`` ei
kertonut resurssia, ja kerroksettoman WFS-resurssin kentät olivat palvelun
ensimmäisestä kerroksesta (HSY:n ilmanlaatuaineisto näytti asuntotuotannon
kenttiä) ilman mainintaa siitä.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import jsonschema
import pytest
from fastmcp import Client

from aura.database import init_db, upsert_dataset
from aura.models import Dataset, Resource
from aura.server import apply_tool_profile, mcp, reset_tool_profile
from aura.tools.inspection import _first_sentence

HSY = "https://kartta.hsy.fi/geoserver/wfs"


@pytest.fixture()
def public() -> Iterator[sqlite3.Connection]:
    c = sqlite3.connect(":memory:", check_same_thread=False)
    c.row_factory = sqlite3.Row
    init_db(c)
    upsert_dataset(
        c,
        Dataset(
            id="hsy-no2",
            name="hsy-no2",
            title="Typpidioksidin vuosikeskiarvot",
            title_fi="Typpidioksidin vuosikeskiarvot",
            notes_fi=(
                "Ilmanlaadun mittauspisteiden typpidioksidipitoisuuden vuosikeskiarvot "
                "pääkaupunkiseudulla. Aineisto päivitetään vuosittain."
            ),
            organization_title="HSY",
            license_title="CC BY 4.0",
            metadata_modified="2026-03-01T10:00:00",
            source="avoindata.fi",
            resources=[
                Resource(id="r-xlsx", name="Excel", format="XLSX", url="https://x/no2.xlsx"),
                Resource(id="r-wfs", name="WFS", format="WFS", url=HSY),
                Resource(id="r-wms", name="WMS", format="WMS", url="https://x/wms"),
            ],
        ),
    )
    c.executemany(
        "INSERT INTO resource_schema (resource_id, dataset_id, field_name, field_type)"
        " VALUES (?, ?, ?, ?)",
        [
            ("r-wfs", "hsy-no2", "Sijaintikunta", "string"),
            ("r-wfs", "hsy-no2", "Talotyyppi", "string"),
        ],
    )
    c.execute(
        "INSERT INTO enrichments (id, dataset_id, field, value, source_type)"
        " VALUES ('e1', 'hsy-no2', 'example_request', ?, 'probe')",
        (
            f"{HSY}?service=WFS&request=GetFeature&count=20"
            "&typeNames=asuminen_ja_maankaytto%3Aaloitetut_asunnot_mal_2012_15",
        ),
    )
    c.executemany(
        "INSERT INTO resource_health (resource_id, dataset_id, url, is_available, checked_at)"
        " VALUES (?, 'hsy-no2', ?, ?, ?)",
        [
            ("r-xlsx", "https://x/no2.xlsx", 0, "2026-09-20 10:00:00"),
            ("r-wfs", HSY, 0, "2026-09-21 10:00:00"),
        ],
    )
    c.commit()
    apply_tool_profile(mcp, profile="public")
    try:
        with patch("aura.server._get_conn", return_value=c):
            yield c
    finally:
        reset_tool_profile(mcp)


async def _inspect(dataset_id: str) -> tuple[dict[str, Any], list[str]]:
    async with Client(mcp) as client:
        tools = {t.name: t for t in await client.list_tools()}
        result = await client.call_tool(
            "inspect_dataset", {"dataset_id": dataset_id}, raise_on_error=False
        )
    data = result.structured_content
    assert isinstance(data, dict)
    jsonschema.validate(data, tools["inspect_dataset"].output_schema)
    lines = result.content[0].text.splitlines()  # type: ignore[union-attr]
    assert 0 < len(lines) <= 5
    return data, lines


async def test_yhteenveto_kertoo_kuvauksen_paivityksen_kentat_ja_saatavuuden(
    public: sqlite3.Connection,
) -> None:
    _, lines = await _inspect("hsy-no2")
    assert lines[0].startswith("Typpidioksidin vuosikeskiarvot [hsy-no2] — HSY")
    assert lines[1] == (
        "Ilmanlaadun mittauspisteiden typpidioksidipitoisuuden vuosikeskiarvot pääkaupunkiseudulla."
    )
    assert "Päivitetty 2026-03-01." in lines[2]
    assert lines[3] == "Kenttiä 2, ei vastannut 2026-09-21."


async def test_kyselyohje_nimeaa_ensimmaisen_kyseltavan_resurssin(
    public: sqlite3.Connection,
) -> None:
    data, _ = await _inspect("hsy-no2")
    first = data["next_actions"][0]
    assert first["tool"] == "query_source"
    assert first["args"] == {"dataset_id": "hsy-no2", "resource_index": 1}


async def test_kerroksettoman_wfsn_kentat_merkitaan_ensimmaisen_kerroksen(
    public: sqlite3.Connection,
) -> None:
    data, _ = await _inspect("hsy-no2")
    assert {f["layer"] for f in data["fields"]} == {
        "asuminen_ja_maankaytto:aloitetut_asunnot_mal_2012_15"
    }
    note = next(n for n in data["notes"] if "ensimmäisestä kerroksesta" in n)
    assert note.startswith("Resurssin 1 kentät")
    assert "aloitetut_asunnot_mal_2012_15" in note


async def test_kerros_urlissa_ei_huomautusta_ja_layer_ohjeessa(
    public: sqlite3.Connection,
) -> None:
    url = f"{HSY}?service=WFS&typeName=ilmanlaatu:no2_vuosikeskiarvot"
    upsert_dataset(
        public,
        Dataset(
            id="hsy-no2-b",
            name="hsy-no2-b",
            title="NO2",
            source="avoindata.fi",
            resources=[Resource(id="rb", name="WFS", format="", url=url)],
        ),
    )
    public.execute(
        "INSERT INTO resource_schema (resource_id, dataset_id, field_name) VALUES (?, ?, ?)",
        ("rb", "hsy-no2-b", "no2"),
    )
    public.commit()
    data, lines = await _inspect("hsy-no2-b")
    assert data["resources"][0]["format"] == "WFS"  # päätelty URL:sta
    assert data["fields"][0]["layer"] == "ilmanlaatu:no2_vuosikeskiarvot"
    assert not any("ensimmäisestä kerroksesta" in n for n in data["notes"])
    assert data["next_actions"][0]["args"] == {
        "dataset_id": "hsy-no2-b",
        "resource_index": 0,
        "layer": "ilmanlaatu:no2_vuosikeskiarvot",
    }
    assert lines[-1] == "Kenttiä 1."


def test_ensimmainen_virke_lyhennetaan_sanarajalla() -> None:
    assert _first_sentence("## Otsikko\n\nEka virke. Toka.") == "Otsikko Eka virke."
    long = "sana " * 60
    out = _first_sentence(long)
    assert len(out) <= 160 and out.endswith("…")
    assert _first_sentence("") == ""
