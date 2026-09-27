"""Harvester Patentti- ja rekisterihallituksen (PRH) YTJ-rajapinnalle.

PRH:n avoin YTJ-rajapinta (``avoindata.prh.fi/opendata-ytj-api/v3``) on jo
katalogissa avoindata.fi:n kautta — sekä hakurajapinta
(``dd9dc2c5-9682-4bab-bfe0-9728160ba5e9``) että koko rekisteri JSON-tiedostona
(``06ce8cf9-8ccc-420b-b558-6cad81c9495a``). Koko rekisteriä **ei** kerätä
tässä uudelleen: sama aineisto kahdesti eri tunnisteella hajottaa haun
järjestyksen (ks. CKAN-lähteiden päällekkäisyys).

**Yrityshaku on poikkeus.** avoindata.fi:n hakurajapinta-aineiston ainoa
resurssi osoittaa sivuston juureen (``http://avoindata.prh.fi/``), joten
``query_source`` ei saa siitä yhtään yritystä. Ulkoinen arvio 27.9.2026:
kysymykseen "tamperelaiset ohjelmistoyritykset" ei löytynyt kyseltävää
aineistoa, vaikka rajapinta vastaa suoraan. ``prh-ytj-yrityshaku`` antaa
toimivan hakuosoitteen ja parametrit (luettu rajapinnan OpenAPI-kuvauksesta
``/opendata-ytj-api/v3/schema``, tarkistettu elävää rajapintaa vasten
27.9.2026: ``location=Tampere&mainBusinessLine=62010`` → 10 yritystä).

Katalogista puuttuvat rajapinnan koodistot, joilla YTJ:n tietueet luetaan:
yritysmuodot, rekisterit, tilamerkinnät, kielet ja postinumerot. Ilman niitä
``companyForms.type = "16"`` ei kerro mitään. Nämä kerätään staattisesti.

**Lisenssi.** PRH:n avoin data julkaistaan CC BY 4.0 -lisenssillä; rajapinta
ei vaadi avainta (tarkistettu 27.9.2026; OpenAPI-kuvauksen ``info.license``:
"Creative Commons Nimeä 4.0").
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


#: Yrityshaun pääparametrit (OpenAPI-kuvaus 27.9.2026).
COMPANY_SEARCH_PARAMS = (
    "name (toiminimi, myös aiemmat ja aputoiminimet)",
    "location (postitoimipaikka, esim. Tampere)",
    "businessId (Y-tunnus)",
    "companyForm (yritysmuoto: OY, OYJ, AY, KY, OK, ASY, SÄÄ, TYH ...)",
    "mainBusinessLine (päätoimiala TOL-koodina tai sen alkuna, esim. 62 tai 62010)",
    "postCode (käynti- tai postiosoitteen postinumero)",
    "registrationDateStart / registrationDateEnd (vvvv-kk-pp)",
    "page (100 tulosta sivulla)",
)


class PrhHarvester(StaticHarvester):
    """YTJ-yrityshaku, rajapinnan koodistot ja postinumerot."""

    name = "prh"
    description = "Patentti- ja rekisterihallitus — YTJ-yrityshaku ja koodistot"
    url = "https://avoindata.prh.fi"
    org_id = "prh"
    org_name = "prh"
    org_title = "Patentti- ja rekisterihallitus"
    default_update_frequency = "tarvittaessa"

    datasets_config = [
        {
            "id": "prh-ytj-yrityshaku",
            "title": "YTJ-yrityshaku (PRH:n avoin rajapinta)",
            "notes_fi": (
                "Kaupparekisteriin merkittyjen yritysten perustiedot hakuehdoilla: "
                "toiminimi, Y-tunnus, yritysmuoto, päätoimiala, osoitteet ja "
                "rekisterimerkinnät. JSON-vastaus: totalResults ja companies[]. "
                "Parametrit: "
                + "; ".join(COMPANY_SEARCH_PARAMS)
                + ". Yrityksen kuntakoodi on kentässä addresses[].postOffices[]"
                ".municipalityCode. Koodien selitteet: aineisto 'YTJ-rajapinnan "
                "koodistot' (prh-ytj-koodistot)."
            ),
            "keywords_fi": [
                "yritys",
                "yritykset",
                "yrityshaku",
                "yritysrekisteri",
                "kaupparekisteri",
                "Y-tunnus",
                "toimiala",
                "päätoimiala",
                "toiminimi",
                "YTJ",
                "PRH",
            ],
            "resources": [
                {
                    "id": "prh-ytj-yrityshaku-json",
                    "format": "JSON",
                    "url": f"{API}/companies?location=Tampere&mainBusinessLine=62",
                    "name_fi": (
                        "Esimerkkihaku: ohjelmistoalan (TOL 62) yritykset Tampereella "
                        "(JSON, 100/sivu)"
                    ),
                }
            ],
        },
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
