"""Harvester Suomen ympäristökeskuksen (SYKE) CKAN API:lle."""

from __future__ import annotations

from typing import Any

from aura.harvesters.ckan import CkanHarvester
from aura.models import Dataset, Resource

#: "Luonnonsuojelu- ja erämaa-alueet" SYKE:n CKANissa.
PROTECTED_AREAS_ID = "{C8FC4A42-A2C3-40C4-92CD-2299C688514E}"
PROTECTED_AREAS_WFS = "https://paikkatiedot.ymparisto.fi/geoserver/inspire_ps/wfs"

#: Kerros → (resurssin tunnisteen pääte, nimi). Kerrokset luettu palvelun
#: omista kyvyistä (GetCapabilities 27.9.2026); kohteita 1 091, 17 020 ja 12.
PROTECTED_AREA_LAYERS: tuple[tuple[str, str, str], ...] = (
    (
        "inspire_ps:PS.ProtectedSitesValtionOmistamaLuonnonsuojelualue",
        "valtio",
        "Valtion omistamat luonnonsuojelualueet (WFS)",
    ),
    (
        "inspire_ps:PS.ProtectedSitesYksityistenMaillaOlevaLuonnonsuojelualue",
        "yksityinen",
        "Yksityisten maiden luonnonsuojelualueet (WFS)",
    ),
    (
        "inspire_ps:PS.ProtectedSitesEramaaAlue",
        "eramaa",
        "Erämaa-alueet (WFS)",
    ),
)


class SykeHarvester(CkanHarvester):
    """Kerää datasetit SYKE:n CKAN-portaalista.

    Suomen ympäristökeskus (SYKE) julkaisee ympäristö-, vesistö- ja
    paikkatietoja ckan.ymparisto.fi:ssä. Sisältää mm. pohjavesialueet,
    Natura 2000 -alueet, maankäyttö-, vedenlaatu- ja satelliittihavaintodataa.
    """

    name = "syke"
    description = "Suomen ympäristökeskus — ympäristö-, vesistö- ja paikkatiedot"
    url = "https://ckan.ymparisto.fi"
    ckan_base_url = "https://ckan.ymparisto.fi/api/3/action"
    ckan_source = "syke"
    #: Portaali ei täytä ``title_translated``-kenttää; otsikot ovat suomeksi.
    source_language = "fi"

    def _to_dataset(self, raw: dict[str, Any]) -> Dataset:
        dataset = super()._to_dataset(raw)
        if dataset.id == PROTECTED_AREAS_ID:
            _add_protected_area_layers(dataset)
        return dataset


def _add_protected_area_layers(dataset: Dataset) -> None:
    """Kuratoitu lisäys: suojelualueiden WFS-kerrokset omina resursseinaan.

    Ulkoinen arvio 27.9.2026: aineiston ainoa WFS-resurssi on koko
    ``inspire_ps``-palvelu ilman kerrosta, ja palvelun ensimmäinen kerros on
    *rakennusten* suojelu — kysely palautti siis väärää aineistoa. Aineiston
    omat kerrokset lisätään resursseiksi palvelun omien kykyjen perusteella.
    Ne tulevat ensimmäisiksi, koska kyselyn oletusvalinta ottaa ensimmäisen
    kyseltävän resurssin. Lisäys on idempotentti: jos SYKE julkaisee kerrokset
    itse, samaa URL:ia ei lisätä toiseen kertaan.
    """
    existing = {r.url for r in dataset.resources}
    added = [
        Resource(
            id=f"{dataset.id}-wfs-{suffix}",
            name=title,
            name_fi=title,
            format="WFS",
            url=f"{PROTECTED_AREAS_WFS}?service=WFS&typeName={layer}",
            description_fi=f"Kerros {layer} (kuratoitu lisäys palvelun kyvyistä).",
        )
        for layer, suffix, title in PROTECTED_AREA_LAYERS
        if f"{PROTECTED_AREAS_WFS}?service=WFS&typeName={layer}" not in existing
    ]
    dataset.resources = [*added, *dataset.resources]
    dataset.num_resources = len(dataset.resources)
