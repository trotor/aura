"""Yhdyssanojen pilkkominen korpuksen omasta sanastosta.

**Miksi.** Suomen yhdyssanat kirjoitetaan yhteen, ja lemmatisointi tuottaa
koko yhdyssanan perusmuodon: ``satotilastot`` → ``satotilasto``. Jos korpuksessa
on osat erikseen (``sato``, ``tilasto``), osumaa ei synny. Evaluaatio osoitti
tämän suurimmaksi yksittäiseksi hakupuutteeksi — kysely ``maatalouden
satotilastot`` sai recall 0,00 vaikka Lukella on kuusi satoaineistoa.

**Sanasto tulee korpuksesta itsestään.** Ei uutta riippuvuutta eikä ulkoista
sanakirjaa: sana kelpaa jakokohdaksi jos se esiintyy itsenäisenä useammassa
kuin yhdessä datasetissä. Sanasto on siten automaattisesti viritetty juuri
tähän aineistoon — ``peruslohko`` ja ``kantorahatulo`` ovat sanoja täällä
vaikka eivät yleiskielen sanakirjassa.

**Jako on additiivinen.** Alkuperäinen sana säilyy aina ja osat lisätään sen
rinnalle. Jako voi siis vain lisätä osumia, ei kadottaa niitä — sama sääntö
kuin dimensiokerroksella: laajentaa kattavuutta, ei syrjäytä.
"""

from __future__ import annotations

import collections
import logging
import sqlite3
from collections.abc import Mapping
from typing import NamedTuple

logger = logging.getLogger(__name__)

#: Lyhyempää sanaa ei yritetä jakaa. Alle kahdeksan merkin sana on harvoin
#: yhdyssana, ja jako tuottaisi lähinnä kohinaa.
MIN_WORD_LENGTH = 8

#: Osan vähimmäispituus.
#:
#: Neljä eikä kolme, koska kolmella mukaan tulevat yleiskielen täytesanat:
#: ``maakunta`` → ``maa`` + ``kunta`` tarkoittaisi että kysely ``kunta``
#: osuu jokaiseen maakunta-aineistoon. Hinta on että ``sääasema`` jää
#: jakamatta (``sää`` on kolme merkkiä). Vaihtoehdot mitattiin kultaisella
#: setillä ja neljä voitti.
MIN_PART_LENGTH = 4

#: Monessako datasetissä sanan on esiinnyttävä päästäkseen sanastoon.
#: Kahdella suodattuvat kirjoitusvirheet ja kertaesiintymät.
MIN_DATASETS = 2

#: Osuus korpuksesta, jota yleisempää osaa ei anneta hakuun.
#:
#: Tämä on jaon tärkein raja ja se löytyi mittaamalla. Ilman sitä
#: ``tulvariskialue`` → ``tulvariski`` + ``alue``, ja ``alue`` esiintyy
#: 12 %:ssa korpuksesta — löysä haku palautti 50 tulosta kun laatuportti
#: sallii alle 20.
#:
#: Pelkkä frekvenssikatto ei riittäisi valintaperusteeksi, koska haluttu
#: ``tilasto`` (20 %) on yleisempi kuin ongelmallinen ``alue`` (12 %).
#: Ratkaisu on eri: **yleinen osa pudotetaan, erotteleva säilyy.**
#: ``satotilasto`` → ``sato`` riittää löytämään satoaineistot, ``tilasto``
#: ei toisi mitään. Sana joka esiintyy joka kymmenennessä datasetissä ei
#: erottele.
MAX_PART_SHARE = 0.10

class Lexicon(NamedTuple):
    """Sanasto jakoa varten.

    ``counts`` kertoo monessako datasetissä sana esiintyy ja sitä käytetään
    sekä sananrajan tunnistamiseen että osan erottelukyvyn arviointiin.
    ``total`` tarvitaan koska erottelukyky on osuus, ei absoluuttinen luku.
    """

    counts: Mapping[str, int]
    total: int

    def knows(self, word: str) -> bool:
        """Kelpaako sana sananrajaksi."""
        return word in self.counts

    def is_informative(self, word: str) -> bool:
        """Kannattaako sana antaa hakuun, vai onko se liian yleinen."""
        if not self.total:
            return True
        return self.counts.get(word, 0) / self.total < MAX_PART_SHARE


_lexicon: Lexicon | None = None
_split_cache: dict[str, list[str] | None] = {}


def build_lexicon(
    conn: sqlite3.Connection, *, min_datasets: int = MIN_DATASETS
) -> Lexicon:
    """Kokoa sanasto korpuksen lemmoista.

    Sanasto rakennetaan nykyisistä lemmoista, jotka on tuotettu ilman jakoa.
    Kun indeksointi myöhemmin lisää osia, ne päätyvät myös sanastoon —
    silmukka suppenee, koska osat ovat jo valmiiksi jakamattomia sanoja.
    """
    counts: collections.Counter[str] = collections.Counter()
    for (lemmas,) in conn.execute(
        "SELECT lemmas FROM datasets WHERE lemmas IS NOT NULL AND lemmas != ''"
    ):
        counts.update(set(str(lemmas).split()))

    total = int(
        conn.execute(
            "SELECT COUNT(*) FROM datasets WHERE lemmas IS NOT NULL AND lemmas != ''"
        ).fetchone()[0]
    )
    kept = {
        word: n
        for word, n in counts.items()
        if n >= min_datasets and len(word) >= MIN_PART_LENGTH
    }
    logger.info(
        "[decompound] Sanasto: %d sanaa, %d datasettiä", len(kept), total
    )
    return Lexicon(kept, total)


def load_lexicon(conn: sqlite3.Connection) -> Lexicon:
    """Rakenna sanasto kerran prosessia kohti ja pidä se muistissa."""
    global _lexicon
    if _lexicon is None:
        _lexicon = build_lexicon(conn)
        _split_cache.clear()
    return _lexicon


def reset_lexicon() -> None:
    """Unohda välimuistiin jäänyt sanasto (testit, uudelleenindeksointi)."""
    global _lexicon
    _lexicon = None
    _split_cache.clear()


def split_compound(word: str, lexicon: Lexicon) -> list[str] | None:
    """Jaa yhdyssana kahteen osaan, tai palauta ``None`` jos ei onnistu.

    Kahtiajako riittää: kolmiosaisen sanan osat ovat itsekin sanastossa, joten
    ne löytyvät jakamalla osat edelleen — eikä syvempi rekursio tuo lisää
    osumia mutta tuo lisää kohinaa.

    Useasta mahdollisesta jakokohdasta valitaan se, jonka **harvinaisempi osa
    esiintyy korpuksessa useimmin**. Pituuteen perustuva valinta ei toimi:
    keksitty jako ``satoti`` + ``lasto`` on tasapainoisempi kuin oikea
    ``sato`` + ``tilasto``, mutta sen osat ovat harvinaisia. Yleisyys erottaa
    aidot sananrajat keinotekoisista.
    """
    if len(word) < MIN_WORD_LENGTH or not word.isalpha():
        return None

    best: tuple[int, str, str] | None = None
    for i in range(MIN_PART_LENGTH, len(word) - MIN_PART_LENGTH + 1):
        head, tail = word[:i], word[i:]
        head_n = lexicon.counts.get(head, 0)
        tail_n = lexicon.counts.get(tail, 0)
        if head_n and tail_n:
            score = min(head_n, tail_n)
            if best is None or score > best[0]:
                best = (score, head, tail)
    return [best[1], best[2]] if best else None


def expand(word: str, lexicon: Lexicon) -> list[str]:
    """Palauta sana ja sen osat, alkuperäinen aina ensimmäisenä.

    Tämä on se muoto jota sekä indeksointi että kysely käyttävät.
    """
    cached = _split_cache.get(word)
    if cached is None and word in _split_cache:
        return [word]

    parts = split_compound(word, lexicon)
    if parts:
        # Yleiset osat pudotetaan: ne eivät erottele, mutta laajentavat
        # tulosjoukon hallitsemattomaksi löysässä vaiheessa.
        parts = [p for p in parts if lexicon.is_informative(p)]
    _split_cache[word] = parts or None
    if not parts:
        return [word]
    return [word, *parts]


def expand_tokens(tokens: list[str], lexicon: Lexicon) -> list[str]:
    """Laajenna sanalista osineen, järjestys säilyttäen ja ilman duplikaatteja."""
    seen: set[str] = set()
    out: list[str] = []
    for token in tokens:
        for part in expand(token, lexicon):
            if part not in seen:
                seen.add(part)
                out.append(part)
    return out
