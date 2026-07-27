"""Testit hakutulosten deduplikoinnille (aura.dedup).

Korpuksessa on 579 datasettiä, joiden otsikko on toisen kanssa identtinen kun
Tilastokeskuksen taulukoodiprefiksi normalisoidaan pois. Ne osuvat pahiten
yleisimpiin kyselyihin: haku ``väkiluku`` käytti 8 tulosta 12:sta samaan
tauluun neljällä eri tunnisteella.
"""

from aura.dedup import deduplicate, normalize_title


class TestNormalizeTitle:
    def test_strips_statfin_table_code(self) -> None:
        assert (
            normalize_title("12vm -- Sähkön kulutus sektoreittain, 1960-2024")
            == normalize_title("11ad -- Sähkön kulutus sektoreittain, 1960-2024")
        )

    def test_code_prefix_removed(self) -> None:
        assert normalize_title("138v -- Kasvihuonekaasupäästöt") == (
            "kasvihuonekaasupäästöt"
        )

    def test_lowercases(self) -> None:
        assert normalize_title("Tulvariskialueet") == normalize_title("TULVARISKIALUEET")

    def test_collapses_whitespace(self) -> None:
        assert normalize_title("Maaperä   1:200 000") == normalize_title(
            "Maaperä 1:200 000"
        )

    def test_strips_surrounding_whitespace(self) -> None:
        assert normalize_title(" Oppilaitokset ") == "oppilaitokset"

    def test_years_are_kept(self) -> None:
        """Eri vuoden aineistot ovat eri aineistoja, ei duplikaatteja."""
        assert normalize_title("Maatalousmaa 2023") != normalize_title(
            "Maatalousmaa 2024"
        )

    def test_does_not_strip_words_that_look_like_codes(self) -> None:
        """Vain '<koodi> -- ' -muotoinen prefiksi karsitaan."""
        assert normalize_title("GTK maaperäkartta") == "gtk maaperäkartta"

    def test_empty_title(self) -> None:
        assert normalize_title("") == ""


class TestDeduplicate:
    def _row(self, ds_id: str, title: str) -> dict[str, object]:
        return {"id": ds_id, "title_fi": title, "title": title, "rank": -1.0}

    def test_keeps_first_of_each_group(self) -> None:
        rows = [
            self._row("12at", "12at -- Väestönmuutokset ja väkiluku, 1749-2025"),
            self._row("11ad", "11ad -- Väestönmuutokset ja väkiluku, 1749-2025"),
            self._row("muu", "Sähkön kulutus"),
        ]
        result = deduplicate(rows)
        assert [r["id"] for r in result] == ["12at", "muu"]

    def test_reports_duplicate_count(self) -> None:
        rows = [
            self._row("a", "12at -- Väkiluku"),
            self._row("b", "11ad -- Väkiluku"),
            self._row("c", "121v -- Väkiluku"),
        ]
        result = deduplicate(rows)
        assert len(result) == 1
        assert result[0]["duplicate_count"] == 2
        assert result[0]["duplicate_ids"] == ["b", "c"]

    def test_unique_rows_get_zero_count(self) -> None:
        result = deduplicate([self._row("a", "Tulvariskialueet")])
        assert result[0]["duplicate_count"] == 0
        assert result[0]["duplicate_ids"] == []

    def test_order_is_preserved(self) -> None:
        rows = [
            self._row("eka", "Ensimmäinen"),
            self._row("toka", "Toinen"),
            self._row("kolmas", "Ensimmäinen"),
        ]
        assert [r["id"] for r in deduplicate(rows)] == ["eka", "toka"]

    def test_empty_input(self) -> None:
        assert deduplicate([]) == []

    def test_rows_without_title_are_not_merged(self) -> None:
        """Tyhjä otsikko ei saa niputtaa toisiinsa liittymättömiä aineistoja."""
        rows = [
            {"id": "a", "title_fi": "", "title": "", "rank": -1.0},
            {"id": "b", "title_fi": "", "title": "", "rank": -1.0},
        ]
        assert [r["id"] for r in deduplicate(rows)] == ["a", "b"]

    def test_falls_back_to_title_when_title_fi_missing(self) -> None:
        rows = [
            {"id": "a", "title_fi": "", "title": "Tulvariskialueet", "rank": -1.0},
            {"id": "b", "title_fi": "Tulvariskialueet", "title": "", "rank": -1.0},
        ]
        result = deduplicate(rows)
        assert len(result) == 1
        assert result[0]["duplicate_count"] == 1

    def test_original_rows_are_not_mutated(self) -> None:
        rows = [self._row("a", "Sama"), self._row("b", "Sama")]
        deduplicate(rows)
        assert "duplicate_count" not in rows[0]


class TestSummaryFormatting:
    """Duplikaattitieto kuuluu näkyviin — niputus ei saa piilottaa mitään."""

    def test_duplicate_count_shown(self) -> None:
        from aura.search import format_dataset_summary

        summary = format_dataset_summary(
            {"title_fi": "Väkiluku", "duplicate_count": 3, "name": "x"}
        )
        assert "3 versiota" in summary

    def test_singular_form(self) -> None:
        from aura.search import format_dataset_summary

        summary = format_dataset_summary(
            {"title_fi": "Väkiluku", "duplicate_count": 1, "name": "x"}
        )
        assert "1 versio " in summary or "1 versio\n" in summary

    def test_not_shown_when_unique(self) -> None:
        from aura.search import format_dataset_summary

        summary = format_dataset_summary(
            {"title_fi": "Väkiluku", "duplicate_count": 0, "name": "x"}
        )
        assert "versio" not in summary

    def test_missing_field_does_not_crash(self) -> None:
        from aura.search import format_dataset_summary

        assert format_dataset_summary({"title_fi": "Väkiluku", "name": "x"})
