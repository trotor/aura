"""Vastauksen tosiasiat talteen samasta noudosta jonka probe jo tekee.

**Miksi tämä on olemassa.** Probe hakee jokaisen resurssin verkosta, lukee
siitä skeeman ja heittää vastauksen muun sisällön pois. Samassa vastauksessa
on kuitenkin valmiina kaikki mitä ``resource_health`` tarvitsee — statuskoodi,
vasteaika, ``Content-Type``, ``Content-Length`` — ja lisäksi
``Last-Modified``, joka kertoo milloin **data** muuttui. Katalogin
``metadata_modified`` kertoo vain milloin metatietue muuttui, ja juuri siitä
laatupisteiden ``timeliness`` lasketaan.

Ilman tätä moduulia nuo tiedot vaatisivat oman kierroksensa: ``aura.health``
hakee samat osoitteet uudelleen. Kannassa on 16 979 probattavaa resurssia ja
kierros kestää tunteja, joten toinen nouto ei ole vain hidas vaan myös
tarpeetonta kuormaa 192 ulkopuoliselle palvelimelle.

**Miksi context-muuttuja eikä proberin paluuarvo.** Neljä proberia palauttaa
``ProbeResult``:n yhteensä parikymmenestä eri kohdasta. Kenttien lisääminen
niihin kaikkiin olisi laaja muutos, jossa yksikin unohtunut paluupolku jäisi
hiljaa tyhjäksi. Sen sijaan tiedot poimitaan HTTP-kerroksesta tapahtumakoukulla,
ja ``ContextVar`` erottaa rinnakkaiset työntekijät toisistaan — asyncio antaa
jokaiselle taskille oman kontekstin, joten jaettu ``AsyncClient`` ei sekoita
niitä. Yksikään proberi ei muutu.

**Vain tosiasiat, ei tulkintaa.** Tähän ei lasketa esimerkiksi sitä onko
``Content-Type`` ristiriidassa katalogin ilmoittaman formaatin kanssa.
Sellainen on kyselyn asia ja tehtävissä jälkikäteen ilman verkkoa; tosiasian
poimiminen taas vaatii noudon. Se mikä vaatii verkon otetaan nyt, se mikä ei
vaadi jätetään myöhemmäksi.
"""

from __future__ import annotations

import time
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

#: HTTP-tilat joista ei kirjata: uudelleenohjaus ei ole vastaus resurssista
#: vaan osoite jonka takaa se löytyy.
_REDIRECT = range(300, 400)


@dataclass
class ResponseFacts:
    """Yhden probe-yrityksen ensimmäisen varsinaisen vastauksen tiedot."""

    url: str = ""
    status_code: int | None = None
    response_time_ms: int | None = None
    content_type: str = ""
    content_length: int | None = None
    last_modified: str = ""
    retry_after: str = ""
    _alku: float = 0.0

    @property
    def saatavilla(self) -> bool:
        """Onko resurssi noudettavissa."""
        return self.status_code is not None and 200 <= self.status_code < 300

    @property
    def rajoitettu(self) -> bool:
        """Hylkäsikö palvelu pyynnön kuormituksen takia."""
        return self.status_code == 429

    def odotus(self) -> float | None:
        """``Retry-After`` sekunteina, tai None jos otsaketta ei ole.

        Vain sekuntimuoto tuetaan. Standardi sallii myös HTTP-päiväyksen,
        mutta sitä ei ole tarpeen jäsentää arvaukseksi: jos otsake ei ole
        luettavissa sekunteina, kutsuja käyttää omaa peräytymistään.
        """
        arvo = self.retry_after.strip()
        return float(arvo) if arvo.isdigit() else None


_nykyinen: ContextVar[ResponseFacts | None] = ContextVar(
    "probe_response_facts", default=None
)


def aloita() -> ResponseFacts:
    """Aloita uusi poiminta tälle taskille ja palauta sen tulos."""
    facts = ResponseFacts(_alku=time.monotonic())
    _nykyinen.set(facts)
    return facts


async def _vastaus_koukku(response: Any) -> None:
    """httpx:n response-tapahtumakoukku.

    Kirjaa **ensimmäisen ei-uudelleenohjaavan** vastauksen. Ensimmäisyys on
    olennaista: WFS-proberi tekee kaksi pyyntöä (GetCapabilities ja
    DescribeFeatureType), ja resurssin terveydestä kertoo niistä ensimmäinen.
    Uudelleenohjaukset ohitetaan, koska ``avoindata.suomi.fi`` vastaa 302:lla
    ja varsinainen sisältö tulee S3:sta — 302 ei kerro onko data saatavilla.
    """
    facts = _nykyinen.get()
    if facts is None or facts.status_code is not None:
        return
    if response.status_code in _REDIRECT:
        return
    facts.status_code = response.status_code
    facts.response_time_ms = int((time.monotonic() - facts._alku) * 1000)
    facts.url = str(response.url)
    facts.content_type = response.headers.get("content-type", "")
    facts.last_modified = response.headers.get("last-modified", "")
    facts.retry_after = response.headers.get("retry-after", "")
    pituus = response.headers.get("content-length", "")
    if pituus.isdigit():
        facts.content_length = int(pituus)


def event_hooks() -> dict[str, list[Any]]:
    """Koukut ``httpx.AsyncClient``-oliolle."""
    return {"response": [_vastaus_koukku]}
