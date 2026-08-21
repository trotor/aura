"""Harvester Finlexin avoimen datan REST-rajapinnalle.

Katalogissa oli Finlexistä yksi rivi: avoindata.fi:n kautta tullut
"Finlex – laki ja oikeus avoimena linkitettynä datana", jonka ainoa resurssi
oli **ilman formaattia** ja osoitteena pelkkä palvelun juuri
``http://data.finlex.fi/``. Se on kirjanmerkki, ei rajapinta: ``query_data``
ei voi tehdä sille mitään eikä ``describe`` osaa opastaa käyttöön.

Finlexillä on kuitenkin dokumentoitu REST-rajapinta ja OpenAPI-kuvaus
(``opendata.finlex.fi/v3/api-docs``). Dokumentit ovat Akoma Ntoso -XML:ää,
kansainvälisen säädösstandardin Suomeen sovitettuna.

**Miksi säädöksiä ei tuoda datasetteinä.** Ilmeinen toive olisi, että haku
``jätelaki`` löytäisi jätelain. Mittaus kertoo miksi se ei kuulu tähän
katalogiin: pelkästään vuoden 2024 säädöksiä on yli 600 dokumenttia (suomi ja
ruotsi erikseen), ja rajapinta antaa enintään kymmenen riviä sivulta. Koko
säädöskannan tuonti olisi kymmeniätuhansia rivejä — enemmän kuin koko nykyinen
katalogi (12 897) — ja lopputulos olisi lakikirja datakatalogin sisällä.
Yksittäinen säädös ei myöskään ole *aineisto* siinä merkityksessä kuin muut
tämän katalogin rivit.

Sen sijaan jokainen aineistokokonaisuus on yksi datasetti, jonka resurssi on
**kyselykelpoinen list-pääte**. Rajapinnan ``titleContains``-parametri hoitaa
sen mitä säädöskohtainen harvestointi lupaisi:

    …/act/statute-consolidated/list?titleContains=jätelaki
    → Jätelaki 646/2011 ja sen konsolidoidut versiot

Kokonaisuuksia on Finlexin oman ohjeen mukaan viisi ja aineistoja 25.
Tässä on **viisi varmennettua** list-päätettä. Oikeuskäytännön
(``judgment``-polku) tyyppinimiä ei löytynyt OpenAPI-kuvauksesta eikä
ohjesivuilta, eikä niitä arvata tähän: kuollut osoite katalogissa on
pahempi kuin puuttuva rivi.
"""

from __future__ import annotations

from aura.harvesters.static import StaticHarvester

API = "https://opendata.finlex.fi/finlex/avoindata/v1/akn/fi"
WEB = "https://data.finlex.fi/fi"

# Yhteinen käyttöohje, joka menee jokaisen datasetin kuvaukseen. Tämä on se
# osa jonka takia rivi ylipäätään kannattaa olla katalogissa: agentti näkee
# describe():stä miten rajapintaa kysellään.
OHJE = (
    "Kysely REST-rajapinnalla: ?titleContains=<sana> hakee otsikosta, "
    "?startYear= ja ?endYear= rajaavat vuodet, ?page= ja ?limit= sivuttavat "
    "(limit enintään 10), ?format=json|xml valitsee muodon. Vastaus on lista "
    "dokumenttien osoitteita; itse dokumentti on Akoma Ntoso -XML:ää. "
    "Rajapinta vaatii User-Agent-otsakkeen."
)


def _dataset(
    ds_id: str,
    title: str,
    polku: str,
    kuvaus: str,
    keywords: list[str],
    web: str,
    koko: int,
) -> dict[str, object]:
    return {
        "id": ds_id,
        "title": title,
        "notes_fi": f"{kuvaus} {OHJE}",
        "keywords_fi": [*keywords, "Finlex", "säädökset", "oikeus"],
        "estimated_size_bytes": koko,
        "resources": [
            {
                "id": f"{ds_id}-api",
                "format": "JSON",
                "name": f"{title} — REST-rajapinta (list)",
                "name_fi": f"{title} — REST-rajapinta (list)",
                "url": f"{API}/{polku}/list",
            },
            {
                "id": f"{ds_id}-web",
                "format": "HTML",
                "name": f"{title} — verkkopalvelu",
                "name_fi": f"{title} — verkkopalvelu",
                "url": web,
            },
        ],
    }


class FinlexHarvester(StaticHarvester):
    """Finlexin aineistokokonaisuudet kyselykelpoisina rajapintariveinä."""

    name = "finlex"
    description = "Finlex — säädökset, valtiosopimukset ja viranomaisnormit (REST/Akoma Ntoso)"
    url = "https://data.finlex.fi/fi/avoin-data"
    org_id = "oikeusministerio"
    org_name = "oikeusministerio"
    org_title = "Oikeusministeriö"
    default_update_frequency = "jatkuvasti"

    datasets_config = [
        _dataset(
            "finlex-ajantasainen",
            "Ajantasainen lainsäädäntö",
            "act/statute-consolidated",
            "Voimassa oleva, muutokset huomioiva konsolidoitu lainsäädäntö. "
            "Sama säädös esiintyy useana ajallisena versiona; arvo "
            "langAndVersion=fin@latest hakee uusimman.",
            ["lainsäädäntö", "laki", "ajantasainen"],
            # Ajantasainen lainsäädäntö on /lainsaadanto-hakemiston juuri;
            # /lainsaadanto/ajantasainen vastaa HTTP 404:llä. (16.8.2026)
            f"{WEB}/lainsaadanto",
            2 * 1024**3,
        ),
        _dataset(
            "finlex-saadoskokoelma",
            "Suomen säädöskokoelma",
            "act/statute",
            "Säädökset alkuperäisessä muodossaan julkaisujärjestyksessä, muutoksia huomioimatta.",
            ["säädöskokoelma", "laki", "asetus"],
            f"{WEB}/lainsaadanto/saadoskokoelma",
            2 * 1024**3,
        ),
        _dataset(
            "finlex-valtiosopimukset",
            "Valtiosopimukset",
            "doc/treaty",
            "Suomen valtiosopimukset ja niiden voimaansaattamissäädökset.",
            ["valtiosopimukset", "kansainväliset sopimukset"],
            f"{WEB}/valtiosopimukset",
            512 * 1024**2,
        ),
        _dataset(
            "finlex-hallituksen-esitykset",
            "Hallituksen esitykset",
            "doc/government-proposal",
            "Hallituksen esitykset eduskunnalle perusteluineen. Säädösvalmistelun tausta-aineisto.",
            ["hallituksen esitykset", "lainvalmistelu", "eduskunta"],
            f"{WEB}/hallituksen-esitykset",
            1024**3,
        ),
        _dataset(
            "finlex-viranomaismaaraykset",
            "Viranomaisten määräyskokoelmat",
            "doc/authority-regulation",
            "Viranomaisten antamat määräykset ja ohjeet, esimerkiksi "
            "Traficomin määräyskokoelma. Osoitteessa tunnus on "
            "viranomaiskohtainen eikä vuosi–numero-muotoinen.",
            ["viranomaismääräykset", "määräyskokoelma", "ohjeet"],
            f"{WEB}/viranomaiset",
            512 * 1024**2,
        ),
    ]
