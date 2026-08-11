"""Suomen kielen lemmatisointi hakuindeksointiin ja kyselyihin.

Suomi on taivuttava ja yhdyssanoja kasaava kieli, joten FTS5:n unicode61-
tokenizer ei löydä sanaa ``pyörätie`` haulla ``pyörätiet``. Tämä moduuli
palauttaa sanat perusmuotoon sekä indeksoitaessa (``lemmatize_text``) että
haettaessa (``build_fts_query``).

Lemmatisointi vaatii ``simplemma``-paketin. Jos sitä ei ole asennettu,
moduuli degradoituu hallitusti: lemmat ovat identtisiä pintamuotojen kanssa
eikä haku parane, mutta mikään ei hajoa.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3

from aura.decompound import Lexicon
from aura.decompound import expand as decompound_expand

logger = logging.getLogger(__name__)

try:
    import simplemma

    LEMMATIZER_AVAILABLE = True
except ImportError:  # pragma: no cover - riippuu asennuksesta
    simplemma = None  # type: ignore[assignment]
    LEMMATIZER_AVAILABLE = False
    logger.info("[lemmatize] simplemma puuttuu — lemmatisointi pois käytöstä")


# Tokenisointi: kirjaimet ja numerot, sallitaan väliviiva yhdyssanoissa
_TOKEN_RE = re.compile(r"[^\W_]+(?:-[^\W_]+)*", re.UNICODE)

# Lyhyemmät tokenit ovat hakukohinaa
MIN_TOKEN_LENGTH = 3

# Kysymys- ja funktiosanat. Nämä eivät esiinny datasettien metatiedoissa,
# joten AND-haussa yksikin niistä takaa nollatuloksen. Vrt. kysely
# "kuinka paljon Helsingissä on sähköautojen latauspisteitä".
STOPWORDS: frozenset[str] = frozenset(
    {
        # kysymyssanat
        "kuinka", "paljon", "mitä", "mikä", "mitkä", "missä", "mistä", "mihin",
        "miten", "milloin", "kuka", "ketkä", "kenen", "montako", "moni",
        # verbit ja apuverbit
        "on", "ovat", "oli", "olivat", "olisi", "ole", "onko", "voiko", "saako",
        "löytyy", "löytyykö", "haluan", "haluaisin", "tarvitsen", "etsin",
        # konjunktiot ja partikkelit
        "ja", "tai", "sekä", "että", "mutta", "kun", "jos", "vaikka", "koska",
        "myös", "vain", "siis", "noin", "eli", "kuten", "joka", "jonka", "jotka",
        # pronominit
        "se", "sen", "ne", "niiden", "tämä", "tämän", "nämä", "näiden",
        "hän", "he", "me", "te", "minä", "sinä",
        # kieltosanat
        "ei", "eivät", "eikä",
        # yleiset englanninkieliset
        "the", "and", "or", "of", "in", "for", "is", "are", "was", "were",
        "how", "what", "where", "when", "which", "many", "much", "with",
        "data", "dataset",
    }
)


def tokenize(text: str) -> list[str]:
    """Pilko teksti hakutokeneiksi.

    Poistaa välimerkit, pienentää kirjainkoon ja suodattaa liian lyhyet
    tokenit sekä stopsanat.
    """
    if not text:
        return []
    return [
        token
        for raw in _TOKEN_RE.findall(text.lower())
        if len(token := raw) >= MIN_TOKEN_LENGTH and token not in STOPWORDS
    ]


_lemma_cache: dict[str, str] = {}


def lemma(token: str) -> str:
    """Palauta yhden tokenin perusmuoto.

    Tulokset välimuistitetaan: 11 000 datasetin indeksoinnissa sanasto
    toistuu voimakkaasti.
    """
    if not LEMMATIZER_AVAILABLE:
        return token

    cached = _lemma_cache.get(token)
    if cached is not None:
        return cached

    try:
        result = simplemma.lemmatize(token, lang="fi").lower()
    except Exception:  # simplemma voi kaatua oudoilla syötteillä
        result = token

    _lemma_cache[token] = result
    return result


def lemmatize_text(text: str) -> str:
    """Lemmatisoi teksti indeksointia varten.

    Palauttaa välilyönnein erotetut uniikit perusmuodot. Järjestys säilyy,
    duplikaatit poistetaan (FTS5 ei hyödy toistosta lemma-sarakkeessa, ja
    lyhyempi teksti pitää bm25-normalisoinnin järkevänä).
    """
    seen: set[str] = set()
    out: list[str] = []
    for token in tokenize(text):
        base = lemma(token)
        if base not in seen:
            seen.add(base)
            out.append(base)
    return " ".join(out)


def _quote(term: str) -> str:
    """Lainaa termi FTS5-merkkijonoliteraaliksi."""
    return '"' + term.replace('"', '""') + '"'


def build_fts_query(
    query: str,
    *,
    strict: bool = True,
    lemma_column: str | None = "lemmas",
    lexicon: Lexicon | None = None,
) -> str:
    """Rakenna FTS5-hakulauseke, joka osuu sekä pinta- että perusmuotoon.

    Rakenne on tarkoituksella epäsymmetrinen:

    - **AND tokenien välillä** säilyttää tarkkuuden. Jokaisen hakusanan on
      osuttava johonkin.
    - **OR pintamuodon ja lemman välillä** palauttaa kattavuuden. Kyse on
      samasta sanasta kahdessa muodossa, joten tämä ei laimenna osumia.

    Tämä eroaa ratkaisevasti sanasto- ja YSO-laajennuksesta, jossa kymmenet
    *eri* termit OR-attiin yhteen — se tuhosi tarkkuuden (haku
    "metsänhakkuut Pirkanmaa" palautti Tampereen bussipysäkit).

    Args:
        query: Käyttäjän hakusanat.
        strict: Jos True, tokenit yhdistetään AND:lla. Jos False, OR:lla —
            käytetään asteittaisessa löysennyksessä kun tiukka haku ei tuota
            riittävästi tuloksia.
        lemma_column: Sarake, johon perusmuoto rajataan. ``None`` hakee
            perusmuotoa kaikista sarakkeista — tarpeen tauluille joissa ei ole
            lemma-saraketta (esim. ``enrichments_fts``).
        lexicon: Yhdyssanasanasto (``aura.decompound``). Jos annettu, yhdyssanan
            osat lisätään **saman tokenin OR-haaraan** — ei erillisiksi
            AND-termeiksi, mikä vaatisi kaikkien osien esiintyvän eikä toisi
            mitään. Sama periaate kuin pinta- ja perusmuodolla: kyse on samasta
            sanasta eri muodossa.

    Returns:
        FTS5 MATCH -lauseke, tai tyhjä merkkijono jos kysely on tyhjä
        tokenisoinnin jälkeen (esim. pelkkiä stopsanoja).
    """
    tokens = tokenize(query)
    if not tokens:
        return ""

    branches: list[str] = []
    for token in tokens:
        base = lemma(token)
        alts: list[str] = [_quote(token)]
        if base != token:
            if lemma_column:
                # Pintamuoto mistä tahansa sarakkeesta, perusmuoto lemmasta
                alts.append(f"{lemma_column} : {_quote(base)}")
            else:
                alts.append(_quote(base))

        if lexicon:
            # Yhdyssanan osat perusmuodosta: satotilasto → sato, tilasto
            for part in decompound_expand(base, lexicon)[1:]:
                alts.append(_quote(part))

        branches.append(alts[0] if len(alts) == 1 else "(" + " OR ".join(alts) + ")")

    operator = " AND " if strict else " OR "
    return operator.join(branches)


# Kentät joista lemmat kootaan. Kuvaus katkaistaan: pitkän tekstin häntä on
# harvoin hakurelevanttia ja lemma-sarake pysyy tiiviinä (bm25 normalisoi
# dokumentin pituudella, joten turha pituus haittaa pisteytystä).
_LEMMA_TEXT_FIELDS = ("title_fi", "title", "notes_fi", "notes", "organization_title")
# JSON-taulukkokentät. geographical_coverage on mukana, jotta aluerajattu haku
# ("pyörätiet Tampere") osuu myös aineistoihin joiden otsikossa aluetta ei
# mainita. Huom: 72 % korpuksesta ilmoittaa kattavuudekseen ["Suomi"], joten
# tämä auttaa vain siltä osin kuin kenttä on oikeasti täytetty.
_LEMMA_LIST_FIELDS = ("keywords_fi", "geographical_coverage")
_NOTES_LIMIT = 2000


def dataset_lemma_text(row: sqlite3.Row) -> str:
    """Kokoa yhden datasetin lemmatisoitava lähdeteksti."""
    available = set(row.keys())
    parts: list[str] = []

    for field in _LEMMA_TEXT_FIELDS:
        value = row[field] if field in available else None
        if isinstance(value, str) and value:
            parts.append(value[:_NOTES_LIMIT] if field.startswith("notes") else value)

    for field in _LEMMA_LIST_FIELDS:
        raw = row[field] if field in available else None
        if not isinstance(raw, str) or not raw:
            continue
        try:
            items = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            parts.append(raw)
            continue
        if isinstance(items, list):
            parts.extend(str(item) for item in items)

    return lemmatize_text(" ".join(parts))


def index_lemmas(conn: sqlite3.Connection, *, batch_size: int = 500) -> int:
    """Populoi datasets.lemmas koko korpukselle.

    FTS5-indeksi pysyy synkassa datasets_au-triggerin kautta, joten erillistä
    rebuildia ei tarvita. Palauttaa päivitettyjen rivien määrän.
    """
    if not LEMMATIZER_AVAILABLE:
        logger.warning("[lemmatize] simplemma puuttuu — lemmoja ei voi indeksoida")
        return 0

    rows = conn.execute(
        "SELECT rowid, title_fi, title, notes_fi, notes, organization_title, "
        "keywords_fi, geographical_coverage FROM datasets"
    ).fetchall()

    updated = 0
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        conn.executemany(
            "UPDATE datasets SET lemmas = ? WHERE rowid = ?",
            [(dataset_lemma_text(row), row["rowid"]) for row in batch],
        )
        conn.commit()
        updated += len(batch)
        logger.info("[lemmatize] %d/%d datasettiä indeksoitu", updated, len(rows))

    return updated
