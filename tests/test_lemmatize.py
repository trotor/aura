"""Testit suomen lemmatisoinnille (aura.lemmatize).

Moduuli on hakupinon perusta: ilman perusmuotoistusta FTS5:n unicode61 ei
löydä sanaa ``pyörätie`` haulla ``pyörätiet``. Testit kattavat tokenisoinnin,
stopsanakarsinnan, FTS5-kyselynrakentimen epäsymmetrisen rakenteen ja
korpusindeksoinnin.
"""

import json
import sqlite3

import pytest

from aura.database import init_db, upsert_dataset
from aura.lemmatize import (
    LEMMATIZER_AVAILABLE,
    MIN_TOKEN_LENGTH,
    STOPWORDS,
    build_fts_query,
    dataset_lemma_text,
    index_lemmas,
    lemma,
    lemmatize_text,
    tokenize,
)
from aura.models import Dataset


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


class TestTokenize:
    def test_empty_text(self) -> None:
        assert tokenize("") == []

    def test_lowercases(self) -> None:
        assert tokenize("Helsinki TAMPERE") == ["helsinki", "tampere"]

    def test_strips_punctuation(self) -> None:
        assert tokenize("vedenlaatu, järvissä!") == ["vedenlaatu", "järvissä"]

    def test_keeps_hyphenated_compound(self) -> None:
        # Väliviiva on osa yhdyssanaa, ei erotin
        assert tokenize("sosiaali-ja terveyspalvelut") == [
            "sosiaali-ja",
            "terveyspalvelut",
        ]

    def test_drops_short_tokens(self) -> None:
        assert tokenize("ab abc") == ["abc"]
        assert MIN_TOKEN_LENGTH == 3

    def test_drops_stopwords(self) -> None:
        """Yksikin stopsana AND-haussa takaisi nollatuloksen."""
        assert tokenize("kuinka paljon sähköä kulutetaan") == ["sähköä", "kulutetaan"]

    def test_question_words_are_stopwords(self) -> None:
        for word in ("kuinka", "paljon", "missä", "montako"):
            assert word in STOPWORDS

    def test_underscore_is_separator(self) -> None:
        assert tokenize("foo_bar") == ["foo", "bar"]

    def test_numbers_are_kept(self) -> None:
        assert tokenize("väestö 2024") == ["väestö", "2024"]


@pytest.mark.skipif(not LEMMATIZER_AVAILABLE, reason="simplemma puuttuu")
class TestLemma:
    def test_plural_to_singular(self) -> None:
        assert lemma("pyörätiet") == "pyörätie"

    def test_inessive_to_nominative(self) -> None:
        assert lemma("järvissä") == "järvi"

    def test_genitive_to_nominative(self) -> None:
        assert lemma("sähkön") == "sähkö"

    def test_base_form_unchanged(self) -> None:
        assert lemma("metsä") == "metsä"

    def test_result_is_lowercase(self) -> None:
        assert lemma("Helsingissä") == lemma("Helsingissä").lower()

    def test_cache_returns_same_value(self) -> None:
        first = lemma("kunnittain")
        assert lemma("kunnittain") == first

    def test_unknown_word_survives(self) -> None:
        """Tuntematon sana palautuu sellaisenaan, ei poikkeuksena."""
        assert lemma("xyzzyxyzzy") == "xyzzyxyzzy"


class TestLemmatizeText:
    def test_empty(self) -> None:
        assert lemmatize_text("") == ""

    def test_only_stopwords_yields_empty(self) -> None:
        assert lemmatize_text("kuinka paljon on") == ""

    def test_deduplicates_preserving_order(self) -> None:
        result = lemmatize_text("metsä metsä järvi").split()
        assert result == list(dict.fromkeys(result))
        assert result[0] == lemmatize_text("metsä")

    @pytest.mark.skipif(not LEMMATIZER_AVAILABLE, reason="simplemma puuttuu")
    def test_inflected_forms_collapse(self) -> None:
        """Taivutusmuodot yhdistyvät samaksi perusmuodoksi — juuri tämä on pointti."""
        assert lemmatize_text("järvi järvissä järvien") == "järvi"


class TestBuildFtsQuery:
    def test_empty_query(self) -> None:
        assert build_fts_query("") == ""

    def test_only_stopwords_returns_empty(self) -> None:
        assert build_fts_query("kuinka paljon on") == ""

    def test_strict_uses_and(self) -> None:
        assert " AND " in build_fts_query("metsä järvi", strict=True)

    def test_loose_uses_or(self) -> None:
        query = build_fts_query("metsä järvi", strict=False)
        assert " OR " in query
        assert " AND " not in query

    @pytest.mark.skipif(not LEMMATIZER_AVAILABLE, reason="simplemma puuttuu")
    def test_surface_and_lemma_are_ored(self) -> None:
        """Epäsymmetria: AND tokenien välillä, OR pinta- ja perusmuodon välillä.

        Kyse on samasta sanasta kahdessa muodossa, joten OR ei laimenna
        osumaa — toisin kuin YSO-laajennus, jossa kymmenet *eri* termit
        OR-attiin yhteen.
        """
        query = build_fts_query("pyörätiet", strict=True)
        assert '"pyörätiet"' in query
        assert 'lemmas : "pyörätie"' in query
        assert " OR " in query

    @pytest.mark.skipif(not LEMMATIZER_AVAILABLE, reason="simplemma puuttuu")
    def test_lemma_column_none_omits_column_prefix(self) -> None:
        """enrichments_fts:ssä ei ole lemmas-saraketta."""
        query = build_fts_query("pyörätiet", strict=True, lemma_column=None)
        assert "lemmas" not in query
        assert '"pyörätie"' in query

    def test_base_form_token_has_no_or_branch(self) -> None:
        """Kun pintamuoto == perusmuoto, haaraa ei tarvita."""
        query = build_fts_query("metsä", strict=True)
        assert query == '"metsä"'

    @pytest.mark.parametrize(
        "hostile",
        ['sana"merkki', "metsä AND OR", 'ns:"foo"', "haku*", "(sulut)", "-miinus"],
    )
    def test_hostile_input_stays_valid_fts5(self, hostile: str) -> None:
        """Käyttäjän syöte ei saa tuottaa kelvotonta FTS5-lauseketta.

        Tokenisoija poistaa erikoismerkit, joten ne eivät koskaan päädy
        lausekkeeseen operaattoreina. Tämä varmistetaan ajamalla lauseke
        oikeaa FTS5-taulua vasten — pelkkä merkkijonotarkistus ei todistaisi
        kelvollisuutta.
        """
        query = build_fts_query(hostile)
        conn = _memory_db()
        if not query:
            return
        conn.execute(
            "SELECT count(*) FROM datasets_fts WHERE datasets_fts MATCH ?", (query,)
        ).fetchone()

    def test_multiple_tokens_all_present(self) -> None:
        query = build_fts_query("vedenlaatu järvissä", strict=True)
        assert '"vedenlaatu"' in query
        assert '"järvissä"' in query


class TestDatasetLemmaText:
    def _row(self, **fields: object) -> sqlite3.Row:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        columns = ", ".join(f"{key} TEXT" for key in fields)
        conn.execute(f"CREATE TABLE t ({columns})")
        placeholders = ", ".join("?" for _ in fields)
        conn.execute(f"INSERT INTO t VALUES ({placeholders})", tuple(fields.values()))
        row: sqlite3.Row = conn.execute("SELECT * FROM t").fetchone()
        return row

    def test_collects_title_and_notes(self) -> None:
        row = self._row(title_fi="Metsävarakuviot", notes_fi="Puuston tilavuus")
        result = dataset_lemma_text(row)
        assert "metsävarakuvio" in result or "metsävarakuviot" in result
        assert "tilavuus" in result

    def test_missing_columns_do_not_crash(self) -> None:
        """Riviltä voi puuttua sarakkeita — esim. enrichments-kyselyissä."""
        assert dataset_lemma_text(self._row(title="Vain otsikko")) != ""

    def test_json_list_fields_are_expanded(self) -> None:
        row = self._row(
            title_fi="Testi",
            keywords_fi=json.dumps(["metsä", "puusto"]),
            geographical_coverage=json.dumps(["Tampere"]),
        )
        result = dataset_lemma_text(row)
        assert "puusto" in result
        assert "tampere" in result

    def test_invalid_json_falls_back_to_raw(self) -> None:
        row = self._row(title_fi="Testi", keywords_fi="ei-jsonia")
        assert "jsonia" in dataset_lemma_text(row)

    def test_notes_are_truncated(self) -> None:
        """Pitkän kuvauksen häntä ei saa paisuttaa lemma-saraketta."""
        row = self._row(title_fi="Otsikko", notes_fi="sana " * 2000)
        assert len(dataset_lemma_text(row)) < 2000

    def test_empty_row_yields_empty(self) -> None:
        assert dataset_lemma_text(self._row(title_fi="", notes_fi="")) == ""


class TestIndexLemmas:
    def _dataset(self, ds_id: str, title: str) -> Dataset:
        return Dataset(
            id=ds_id,
            name=ds_id,
            title=title,
            title_fi=title,
            organization_id="org-1",
            organization_name="org",
            organization_title="Testivirasto",
        )

    def test_populates_lemmas_column(self) -> None:
        conn = _memory_db()
        upsert_dataset(conn, self._dataset("ds-1", "Pyörätiet"))
        conn.commit()

        assert index_lemmas(conn) == 1
        stored = conn.execute("SELECT lemmas FROM datasets WHERE id = 'ds-1'").fetchone()
        assert stored["lemmas"]

    def test_returns_row_count(self) -> None:
        conn = _memory_db()
        for index in range(5):
            upsert_dataset(conn, self._dataset(f"ds-{index}", f"Aineisto {index}"))
        conn.commit()
        assert index_lemmas(conn) == 5

    def test_batching_covers_all_rows(self) -> None:
        """Eräkoko ei saa jättää rivejä indeksoimatta."""
        conn = _memory_db()
        for index in range(7):
            upsert_dataset(conn, self._dataset(f"ds-{index}", f"Metsävarat {index}"))
        conn.commit()

        assert index_lemmas(conn, batch_size=2) == 7
        empty = conn.execute(
            "SELECT count(*) FROM datasets WHERE lemmas IS NULL OR lemmas = ''"
        ).fetchone()[0]
        assert empty == 0

    def test_empty_corpus(self) -> None:
        assert index_lemmas(_memory_db()) == 0

    @pytest.mark.skipif(not LEMMATIZER_AVAILABLE, reason="simplemma puuttuu")
    def test_indexed_lemmas_are_searchable(self) -> None:
        """Päätepistetesti: indeksoinnin jälkeen taivutettu haku osuu.

        Tämä on koko moduulin olemassaolon syy — ilman lemmoja
        ``pyörätiet``-hakusana ei löydä aineistoa ``Pyörätie``.
        """
        from aura.database import search_datasets

        conn = _memory_db()
        upsert_dataset(conn, self._dataset("ds-1", "Pyörätie"))
        conn.commit()
        index_lemmas(conn)

        results = search_datasets(conn, "pyörätiet")
        assert [row["id"] for row in results] == ["ds-1"]
