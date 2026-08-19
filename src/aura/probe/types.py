"""Probe-vaiheen tulostyypit.

Prober ei kirjoita kantaan eikä tiedä orkestroinnista. Se palauttaa tämän
rakenteen, ja orkestrointi päättää mitä sille tehdään. Siksi jokainen
prober on testattavissa tallennetulla vastauksella ilman kantaa ja verkkoa.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class ProbeStatus:
    """Probe-yrityksen lopputulos.

    Neljä epäonnistumistapaa erotellaan, koska ne tarkoittavat eri asioita
    ja johtavat eri TTL:ään: palvelu joka on poissa on eri asia kuin
    palvelu joka vastasi jotain odottamatonta.
    """

    OK = "ok"
    HTTP_ERROR = "http_error"      # palvelu vastasi kieltävästi
    TIMEOUT = "timeout"            # palvelu ei vastannut
    PARSE_ERROR = "parse_error"    # vastasi jotain muuta kuin lupasi
    EMPTY = "empty"                # vastasi oikein muttei sisältänyt kenttiä


@dataclass(frozen=True)
class ProbeResult:
    """Yhden proberin tulos.

    Attributes:
        status: ``ProbeStatus``-vakio.
        detail: Ihmisluettava syy epäonnistumiselle, esim. "HTTP 404".
        fields: Sarakkeet ``(nimi, tyyppi)`` — menevät resource_schemaan.
        enrichments: ``(kenttä, arvo)`` — menevät enrichmenteiksi.
        http_status: Viimeisin statuskoodi, josta auth_method johdetaan.
    """

    status: str
    detail: str = ""
    fields: list[tuple[str, str]] = field(default_factory=list)
    enrichments: list[tuple[str, str]] = field(default_factory=list)
    http_status: int | None = None

    @property
    def ok(self) -> bool:
        return self.status == ProbeStatus.OK
