"""Harvester Suomi.fi-palvelutietovarannon (PTV) avoimelle rajapinnalle.

Katalogissa oli PTV:stä yksi rivi: avoindata.fi:n kautta tullut
"Suomi.fi-palvelutietovaranto", jonka ainoa resurssi oli **Swagger-sivu**
``api.palvelutietovaranto.suomi.fi/swagger/ui/``. Se on kirjanmerkki, ei
rajapinta: ``query_data`` ei voi tehdä sille mitään eikä ``describe`` osaa
opastaa käyttöön.

PTV on kuitenkin julkishallinnon keskitetty tietovaranto palveluista ja
asiointikanavista, ja sen rajapinta on **auki ilman API-avainta**. Mitattuna
18.8.2026:

======================  =========  ==================================
kokonaisuus             määrä      mitä sisältää
======================  =========  ==================================
organisaatiot             ~1 630   julkishallinnon toimijat
palvelut                 ~30 000   palvelukuvaukset luokituksineen
palvelukanavat           ~72 000   **yhteystiedot**
palvelupaikat            ~38 000   käyntiosoitteet, aukioloajat
palvelukokoelmat             706   temaattiset kokoelmat
pohjakuvaukset               308   valtakunnalliset mallikuvaukset
======================  =========  ==================================

Palvelukanavan kentissä ovat ``addresses`` (katu, numero, postinumero),
``phoneNumbers``, ``emails``, ``webPages`` ja ``serviceHours``. Juuri tämä
puuttui katalogista kokonaan.

**Miksi palveluja ei tuoda datasetteinä.** Sama päättely kuin Finlexin
säädöksillä: 30 000 palvelua ja 72 000 kanavaa olisi kahdeksankertainen
määrä nykyiseen katalogiin (12 912) nähden, ja lopputulos olisi
puhelinluettelo datakatalogin sisällä. Yksittäinen palvelupiste ei
myöskään ole *aineisto* siinä merkityksessä kuin muut tämän katalogin
rivit.

Sen sijaan jokainen kokonaisuus on yksi datasetti, jonka resurssi on
**kyselykelpoinen list-pääte**. Kuntarajaus hoitaa sen mitä
palvelukohtainen harvestointi lupaisi:

    …/ServiceChannel/area/Municipality/code/297
    → 987 palvelukanavaa Kuopion alueelta yhteystietoineen

**Luokitukset ovat jo katalogissa.** PTV:n palveluluokat, kohderyhmät,
elämäntilanteet, tuottajatyypit ja tuotantotavat tulevat ``koodistot``
-harvesterin kautta (``koodistot-ptv-*``), ja niiden koodiarvot ovat
haettavissa. Tämä harvesteri ei siis toista niitä, vaan viittaa niihin.
Ainoa kattamaton käsitejoukko on palvelukohtainen JUPO-ontologia, joka ei
ole koodistopalvelussa.

Päätepisteet on todennettu yksitellen. ``/Service/active`` ja
``/ServiceChannel/active`` vastaavat HTTP 401:llä ja ``/Service/serviceClass``
404:llä, joten niitä ei ole tässä.
"""

from __future__ import annotations

from aura.harvesters.static import StaticHarvester

API = "https://api.palvelutietovaranto.suomi.fi/api/v11"

#: Palvelun esittelysivu. ``suomi.fi/palvelut`` vastaa HTTP 404:llä —
#: tarkistettu 18.8.2026, ei arvattu.
WEB = "https://palveluhallinta.suomi.fi/fi/sivut/palvelutietovaranto/esittely"

#: Yhteinen käyttöohje jokaisen datasetin kuvaukseen. Tämä on se osa jonka
#: takia rivi ylipäätään kannattaa olla katalogissa: agentti näkee
#: ``describe()``:stä miten rajapintaa kysellään.
OHJE = (
    "Kysely REST-rajapinnalla: vastaus on sivutettu (pageNumber, pageSize, "
    "pageCount, itemList), ja ?page=N hakee seuraavan sivun. Sivukoko on "
    "1000 listapäätteissä. Yksittäinen tietue haetaan lisäämällä polkuun "
    "tunniste: /Organization/{id}. Rajapinta ei vaadi API-avainta mutta "
    "vaatii User-Agent-otsakkeen. Kuntarajaus: lisää polkuun "
    "/area/Municipality/code/{kuntakoodi} — esimerkiksi 297 on Kuopio."
)

#: Luokitukset joihin PTV viittaa. Ne ovat katalogissa omina riveinään
#: koodistot-harvesterin kautta, joten tässä vain osoitetaan yhteys.
LUOKITUKSET = (
    "Palvelut on luokiteltu PTV:n omilla luokituksilla, jotka löytyvät "
    "katalogista erikseen: koodistot-ptv-ptvserclass2 (palveluluokat), "
    "koodistot-ptv-ptvkohderyhmat (kohderyhmät), koodistot-ptv-ptvelti "
    "(elämäntilanteet), koodistot-ptv-ptvtuotanto (tuotantotavat) ja "
    "koodistot-ptv-ptvjultuottaja (tuottajatyypit)."
)


def _dataset(
    ds_id: str,
    title: str,
    polku: str,
    kuvaus: str,
    keywords: list[str],
    koko: int,
    *,
    kuntarajaus: str = "",
    luokitukset: bool = False,
) -> dict[str, object]:
    """Luo yksi kyselykelpoinen rajapintarivi.

    Args:
        polku: Rajapinnan listapääte ``API``-juuren jälkeen.
        kuntarajaus: Kuntakohtainen polku, jos rajapinta tukee sitä.
        luokitukset: Liitetäänkö viittaus koodistoriveihin.
    """
    notes = f"{kuvaus} {OHJE}"
    if kuntarajaus:
        notes += f" Tälle kokonaisuudelle kuntarajaus on: {API}{kuntarajaus}."
    if luokitukset:
        notes += f" {LUOKITUKSET}"

    resources: list[dict[str, object]] = [
        {
            "id": f"{ds_id}-api",
            "format": "JSON",
            "name": f"{title} — REST-rajapinta",
            "name_fi": f"{title} — REST-rajapinta",
            "url": f"{API}{polku}",
        }
    ]
    if kuntarajaus:
        resources.append(
            {
                "id": f"{ds_id}-kunta",
                "format": "JSON",
                "name": f"{title} — kuntarajaus (esimerkkinä Kuopio)",
                "name_fi": f"{title} — kuntarajaus (esimerkkinä Kuopio)",
                "url": f"{API}{kuntarajaus}",
            }
        )
    resources.append(
        {
            "id": f"{ds_id}-web",
            "format": "HTML",
            "name": f"{title} — palvelun esittely",
            "name_fi": f"{title} — palvelun esittely",
            "url": WEB,
        }
    )
    return {
        "id": ds_id,
        "title": title,
        "notes_fi": notes,
        "keywords_fi": [*keywords, "Palvelutietovaranto", "PTV", "Suomi.fi"],
        "estimated_size_bytes": koko,
        "resources": resources,
    }


class PtvHarvester(StaticHarvester):
    """Palvelutietovarannon kokonaisuudet kyselykelpoisina rajapintariveinä."""

    name = "ptv"
    description = "Suomi.fi-palvelutietovaranto — julkishallinnon palvelut ja yhteystiedot"
    url = WEB
    org_id = "dvv"
    org_name = "dvv"
    org_title = "Digi- ja väestötietovirasto (DVV)"
    default_update_frequency = "jatkuvasti"

    datasets_config = [
        _dataset(
            "ptv-organisaatiot",
            "Julkishallinnon organisaatiot",
            "/Organization",
            "Palvelutietovarantoon rekisteröityneet julkishallinnon toimijat: "
            "valtion virastot, kunnat, hyvinvointialueet, kuntayhtymät ja "
            "julkisia palveluja tuottavat yhtiöt.",
            ["organisaatiot", "julkishallinto", "virastot", "kunnat"],
            64 * 1024**2,
            kuntarajaus="/Organization/area/Municipality/code/297",
        ),
        _dataset(
            "ptv-palvelut",
            "Julkishallinnon palvelut",
            "/Service",
            "Julkishallinnon palvelukuvaukset: mitä palvelu on, kenelle se on "
            "tarkoitettu, mitkä ovat ehdot ja mihin lainsäädäntöön se perustuu. "
            "Noin 30 000 palvelua.",
            ["palvelut", "julkiset palvelut", "asiointi", "palvelukuvaus"],
            512 * 1024**2,
            kuntarajaus="/Service/list/area/Municipality/code/297",
            luokitukset=True,
        ),
        _dataset(
            "ptv-palvelukanavat",
            "Palvelukanavat ja yhteystiedot",
            "/ServiceChannel",
            "Asiointikanavat joilla palveluja käytetään, yhteystietoineen: "
            "puhelinnumerot (phoneNumbers), sähköpostit (emails), verkkosivut "
            "(webPages), aukioloajat (serviceHours) ja käyntiosoitteet "
            "(addresses). Kanavatyyppejä on viisi: ServiceLocation, Phone, "
            "EChannel, WebPage ja PrintableForm. Noin 72 000 kanavaa.",
            ["yhteystiedot", "asiointikanavat", "puhelinnumerot", "sähköposti", "aukioloajat"],
            1024**3,
            kuntarajaus="/ServiceChannel/area/Municipality/code/297",
        ),
        _dataset(
            "ptv-palvelupaikat",
            "Palvelupaikat ja käyntiosoitteet",
            "/ServiceChannel/type/ServiceLocation",
            "Fyysiset palvelupisteet joissa asioidaan paikan päällä. Sisältää "
            "käyntiosoitteen katutasolla (streetAddress: katu, numero, "
            "postinumero, postitoimipaikka), aukioloajat ja esteettömyystiedot. "
            "Noin 38 000 palvelupaikkaa.",
            ["palvelupisteet", "käyntiosoitteet", "toimipisteet", "esteettömyys"],
            512 * 1024**2,
        ),
        _dataset(
            "ptv-palvelukokoelmat",
            "Palvelukokoelmat",
            "/ServiceCollection",
            "Temaattiset kokoelmat joilla organisaatiot ryhmittelevät palvelujaan "
            "asiakkaan tilanteen mukaan. 706 kokoelmaa.",
            ["palvelukokoelmat", "teemat", "ryhmittely"],
            16 * 1024**2,
        ),
        _dataset(
            "ptv-pohjakuvaukset",
            "Palvelujen pohjakuvaukset",
            "/GeneralDescription",
            "Valtakunnalliset mallikuvaukset palveluista joita monet kunnat "
            "tuottavat samalla tavalla. Kunta täydentää pohjakuvausta omilla "
            "tiedoillaan, joten sama palvelu on vertailukelpoinen kuntien "
            "välillä. 308 pohjakuvausta.",
            ["pohjakuvaukset", "mallikuvaukset", "kuntavertailu"],
            32 * 1024**2,
            luokitukset=True,
        ),
    ]
