"""Avainsanaindeksi web-sivuston avainsanaselaimelle.

Avainsanat ovat julkaisijoiden omia (``keywords_fi``), joten samaa asiaa on
kirjoitettu monella tavalla ("Kunta", "kunta", "kunnat"), ja seassa on
teknistä kohinaa: lähteen nimi (``avoindata.fi``), luokitusmerkintä
(``ei-inspire``) ja PxWeb-kansioiden tunnisteet (``1._Ulkoiset_…``).

Indeksi lasketaan kerran muistiin, koska web-palvelin avaa kannan vain luku
-tilassa eikä 13 900 aineiston läpikäynti maksa juuri mitään (alle sekunti).
Se rakennetaan uudelleen, kun kannan aineistomäärä tai viimeisin keruu muuttuu.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass, field

from aura.lemmatize import lemmatize_text

#: Avainsanat jotka eivät kerro aineiston sisällöstä mitään.
NOISE_KEYWORDS = frozenset(
    {
        "avoindata.fi",
        "ei-inspire",
        "uusin",
        "arkisto",
    }
)
#: PxWeb-kansiotunnisteet: "1._Ulkoiset…", "06 Metsavarat".
_PATH_ID = re.compile(r"^\d+[._ ]")
#: Taulukoodit: "ktt011", "vaerak2".
_TABLE_CODE = re.compile(r"^[a-z]{2,8}\d{2,}$")
MIN_LENGTH = 2
#: Pidempi on kansion tai taulun nimi, ei avainsana ("Kuntien ja
#: kuntayhtymien raportoimat tiedot 1975-2014").
MAX_LENGTH = 40

#: Liittyväksi sanaksi vaaditaan vähintään näin monta yhteistä aineistoa,
#: ellei sanalla ole niin vähän aineistoja ettei se ole mahdollista.
MIN_COOCCURRENCE = 2
#: Yhdyssanan alkuosaksi kelpaava lyhin perusmuoto: "kunta" → "kuntatalous".
#: Lyhyempi ("maa") osuisi sattumalta ("maanviljely", "maalaji", "maatalous").
MIN_PREFIX = 5


def normalize(keyword: str) -> str:
    """Vertailuavain: pienet kirjaimet, yksi välilyönti sanojen välissä."""
    return " ".join(str(keyword).lower().split())


def is_noise(keyword: str) -> bool:
    """Onko avainsana teknistä kohinaa eikä sisältöä."""
    key = normalize(keyword)
    if len(key) < MIN_LENGTH or len(key) > MAX_LENGTH:
        return True
    if key in NOISE_KEYWORDS:
        return True
    # PxWeb-kansiotunnisteet: "1._Ulkoiset_tilinpaatoslaskelmat", "Kuntien_avainluvut".
    return "_" in key or bool(_PATH_ID.match(key)) or bool(_TABLE_CODE.match(key))


@dataclass
class KeywordEntry:
    """Yksi avainsana: näyttömuoto, aineistot ja perusmuoto vertailuun."""

    key: str
    label: str
    dataset_ids: list[str] = field(default_factory=list)
    lemma: str = ""

    @property
    def count(self) -> int:
        return len(self.dataset_ids)


class KeywordIndex:
    """Avainsanat, niiden aineistot ja yhteisesiintymät."""

    def __init__(self, entries: dict[str, KeywordEntry], by_dataset: dict[str, list[str]]):
        self._entries = entries
        self._by_dataset = by_dataset

    @classmethod
    def build(cls, conn: sqlite3.Connection) -> KeywordIndex:
        forms: dict[str, Counter[str]] = {}
        ids: dict[str, list[str]] = {}
        by_dataset: dict[str, list[str]] = {}
        for dataset_id, raw in conn.execute("SELECT id, keywords_fi FROM datasets"):
            try:
                keywords = json.loads(raw or "[]")
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(keywords, list):
                continue
            seen: set[str] = set()
            for keyword in keywords:
                if not isinstance(keyword, str) or is_noise(keyword):
                    continue
                key = normalize(keyword)
                if key in seen:
                    continue
                seen.add(key)
                forms.setdefault(key, Counter())[" ".join(keyword.split())] += 1
                ids.setdefault(key, []).append(str(dataset_id))
            if seen:
                by_dataset[str(dataset_id)] = sorted(seen)

        entries = {}
        for key, counter in forms.items():
            # Näyttömuoto: yleisin kirjoitusasu; tasatilanteessa pienet kirjaimet.
            label = max(counter.items(), key=lambda kv: (kv[1], kv[0].islower(), kv[0]))[0]
            entries[key] = KeywordEntry(
                key=key, label=label, dataset_ids=ids[key], lemma=lemmatize_text(key)
            )
        return cls(entries, by_dataset)

    def get(self, keyword: str) -> KeywordEntry | None:
        return self._entries.get(normalize(keyword))

    def entries(self) -> list[KeywordEntry]:
        """Kaikki avainsanat aakkosjärjestyksessä."""
        return sorted(self._entries.values(), key=lambda e: e.key)

    def top(self, n: int) -> list[KeywordEntry]:
        """Yleisimmät avainsanat."""
        return sorted(self._entries.values(), key=lambda e: (-e.count, e.key))[:n]

    def related(self, keyword: str, n: int = 15) -> list[KeywordEntry]:
        """Samoissa aineistoissa esiintyvät avainsanat, tyypillisyyden mukaan.

        Järjestys on kosinisamankaltaisuus (yhteiset / √(a·b)), ei pelkkä
        yhteisten määrä: muuten yleiset sanat kuten "kunta" olisivat aina
        kärjessä, vaikka ne liittyvät kaikkeen yhtä vähän.
        """
        entry = self.get(keyword)
        if entry is None:
            return []
        together: Counter[str] = Counter()
        for dataset_id in entry.dataset_ids:
            together.update(k for k in self._by_dataset.get(dataset_id, ()) if k != entry.key)
        threshold = min(MIN_COOCCURRENCE, entry.count)
        scored = [
            (shared / math.sqrt(entry.count * self._entries[key].count), shared, key)
            for key, shared in together.items()
            if shared >= threshold
        ]
        scored.sort(key=lambda s: (-s[0], -s[1], s[2]))
        return [self._entries[key] for _, _, key in scored[:n]]

    def similar(self, keyword: str, n: int = 15) -> list[KeywordEntry]:
        """Saman perusmuodon tai yhdyssanan osan jakavat avainsanat.

        "kunta" → "kunnat" (sama perusmuoto), "kuntatalous" ja "kuntayhtymä"
        (alkavat perusmuodolla). Lyhyitä perusmuotoja ei käytetä alkuosana.
        """
        entry = self.get(keyword)
        if entry is None or not entry.lemma:
            return []
        base = entry.lemma
        found = []
        for other in self._entries.values():
            if other.key == entry.key or not other.lemma:
                continue
            if other.lemma == base:
                found.append(other)
            elif len(base) >= MIN_PREFIX and other.lemma.startswith(base):
                found.append(other)
            elif len(other.lemma) >= MIN_PREFIX and base.startswith(other.lemma):
                found.append(other)
        found.sort(key=lambda e: (-e.count, e.key))
        return found[:n]


_cache: dict[str, object] = {}


def get_index(conn: sqlite3.Connection) -> KeywordIndex:
    """Muistiin laskettu indeksi; uusi vain jos kannan sisältö on muuttunut."""
    stamp = tuple(
        conn.execute("SELECT COUNT(*), COALESCE(MAX(harvested_at), '') FROM datasets").fetchone()
    )
    if _cache.get("stamp") != stamp:
        _cache["index"] = KeywordIndex.build(conn)
        _cache["stamp"] = stamp
    index = _cache["index"]
    assert isinstance(index, KeywordIndex)
    return index
