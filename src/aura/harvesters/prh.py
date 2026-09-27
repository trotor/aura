"""Harvester Patentti- ja rekisterihallituksen (PRH) YTJ-koodistoille.

PRH:n avoin YTJ-rajapinta (``avoindata.prh.fi/opendata-ytj-api/v3``) on jo
katalogissa avoindata.fi:n kautta — sekä hakurajapinta
(``dd9dc2c5-9682-4bab-bfe0-9728160ba5e9``) että koko rekisteri JSON-tiedostona
(``06ce8cf9-8ccc-420b-b558-6cad81c9495a``). Niitä **ei** kerätä tässä
uudelleen: sama aineisto kahdesti eri tunnisteella hajottaa haun järjestyksen
(ks. CKAN-lähteiden päällekkäisyys).

Katalogista puuttuvat rajapinnan koodistot, joilla YTJ:n tietueet luetaan:
yritysmuodot, rekisterit, tilamerkinnät, kielet ja postinumerot. Ilman niitä
``companyForms.type = "16"`` ei kerro mitään. Nämä kerätään staattisesti.

**Lisenssi.** PRH:n avoin data julkaistaan CC BY 4.0 -lisenssillä; rajapinta
ei vaadi avainta (tarkistettu 27.9.2026).
"""

from __future__ import annotations

from aura.harvesters.static import StaticHarvester

API = "https://avoindata.prh.fi/opendata-ytj-api/v3"

#: Koodisto → (otsikko, kuvaus). Koodiston tunniste on rajapinnan ``code``-arvo.
CODE_LISTS = {
    "YRMU": ("Yritysmuodot", "companyForms.type — esim. 16 Osakeyhtiö, 2 Asunto-osakeyhtiö"),
    "REK": ("Rekisterit", "registeredEntries.register — kauppa-, säätiö-, yhdistysrekisteri"),
    "SELTILA": ("Tilamerkinnät", "companySituations.type — selvitystila, konkurssi"),
    "KIELI": ("Kielet", "languageCode — kuvausten ja nimien kieli"),
}


class PrhHarvester(StaticHarvester):
    """YTJ-rajapinnan koodistot ja postinumerot."""

    name = "prh"
    description = "Patentti- ja rekisterihallitus — YTJ-rajapinnan koodistot"
    url = "https://avoindata.prh.fi"
    org_id = "prh"
    org_name = "prh"
    org_title = "Patentti- ja rekisterihallitus"
    default_update_frequency = "tarvittaessa"

    datasets_config = [
        {
            "id": "prh-ytj-koodistot",
            "title": "YTJ-rajapinnan koodistot",
            "notes_fi": (
                "Koodit joilla YTJ:n yritystietueet luetaan: "
                + "; ".join(f"{t} ({c}): {d}" for c, (t, d) in CODE_LISTS.items())
                + ". Yritystiedot itse: katalogin aineistot 'API: YTJ-tiedot "
                "kaupparekisteriin merkityistä yrityksistä' ja 'YTJ:n avoimet tiedot "
                "JSON-tiedostona'."
            ),
            "keywords_fi": [
                "YTJ",
                "yritysmuoto",
                "yritys",
                "kaupparekisteri",
                "koodisto",
                "PRH",
            ],
            "resources": [
                {
                    "format": "CSV",
                    "url": f"{API}/description?code={code}&lang=fi",
                    "name_fi": f"{title} ({code}), sarkaineroteltu",
                }
                for code, (title, _) in CODE_LISTS.items()
            ],
        },
        {
            "id": "prh-ytj-postinumerot",
            "title": "YTJ-rajapinnan postinumerot",
            "notes_fi": (
                "Postinumerot ja postitoimipaikat joita YTJ:n osoitetiedoissa "
                "käytetään. Yritysosoitteiden kuntakoodi on kentässä "
                "addresses.postOffices.municipalityCode."
            ),
            "keywords_fi": ["postinumero", "postitoimipaikka", "YTJ", "osoite"],
            "resources": [
                {
                    "format": "JSON",
                    "url": f"{API}/post_codes?lang=fi",
                    "name_fi": "Postinumerot (JSON)",
                }
            ],
        },
    ]
