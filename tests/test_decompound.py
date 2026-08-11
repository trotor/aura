"""Testit yhdyssanojen pilkkomiselle.

Evaluaatio osoitti tämän suurimmaksi yksittäiseksi hakupuutteeksi:
lemmatisointi tuottaa koko yhdyssanan perusmuodon (``satotilastot`` →
``satotilasto``), mutta korpuksessa on osat (``sato``, ``tilasto``). Kysely
``maatalouden satotilastot`` sai recall 0,00 vaikka Lukella on kuusi
satoaineistoa.

Jako on **additiivinen**: alkuperäinen sana säilyy aina ja osat lisätään sen
rinnalle. Näin jako voi vain lisätä osumia, ei kadottaa niitä.
"""

from __future__ import annotations

from aura.decompound import (
    MIN_PART_LENGTH,
    MIN_WORD_LENGTH,
    Lexicon,
    expand,
    split_compound,
)

# Pieni sanasto testeihin — oikea rakennetaan korpuksesta.
# Sanasto on sana → monessako datasetissä se esiintyy. Yleisyys ratkaisee
# jakokohdan valinnan.
# 10 000 datasettiä, joten 10 %:n katto on 1 000 esiintymää.
LEX = Lexicon(
    {
        "sato": 40, "tilasto": 120, "lento": 30, "liikenne": 200,
        "matkustaja": 25, "määrä": 300, "joukko": 40, "metsä": 150,
        "vara": 60, "puolue": 20, "ohjelma": 80, "vaali": 30,
        "rahoitus": 45, "asema": 90, "kunta": 400, "havainto": 70,
        # Yleissana: 30 % korpuksesta, ei erottele mitään.
        "alue": 3000, "tulvariski": 11,
    },
    total=10_000,
)


class TestSplitCompound:
    def test_jakaa_tutun_yhdyssanan(self) -> None:
        assert split_compound("satotilasto", LEX) == ["sato", "tilasto"]

    def test_jakaa_kolmiosaisen_kahtia(self) -> None:
        """Kaksiosainen jako riittää: osat menevät sanastoon ja löytyvät silti."""
        parts = split_compound("lentoliikenne", LEX)
        assert parts == ["lento", "liikenne"]

    def test_ei_jaa_tuntematonta(self) -> None:
        assert split_compound("kaupunkirakenne", LEX) is None

    def test_ei_jaa_lyhytta_sanaa(self) -> None:
        """Lyhyt sana on harvoin yhdyssana ja jako tuottaisi kohinaa."""
        assert len("satotil") < MIN_WORD_LENGTH
        assert split_compound("satotil", LEX) is None

    def test_ei_tuota_liian_lyhyita_osia(self) -> None:
        for word in ("maakunta", "sääasema"):
            parts = split_compound(word, LEX)
            if parts is not None:
                assert all(len(p) >= MIN_PART_LENGTH for p in parts), (word, parts)

    def test_suosii_yleisia_osia(self) -> None:
        """Keksitty jako voi olla tasapainoisempi kuin oikea.

        ``satoti`` + ``lasto`` on 6+5, oikea ``sato`` + ``tilasto`` on 4+7.
        Pituus valitsisi väärin; yleisyys valitsee oikein.
        """
        lex = Lexicon({**LEX.counts, "satoti": 2, "lasto": 2}, LEX.total)
        assert split_compound("satotilasto", lex) == ["sato", "tilasto"]

    def test_tyhja_ja_roska_eivat_kaada(self) -> None:
        for junk in ("", "a", "123456789", "----------"):
            assert split_compound(junk, LEX) is None


class TestExpand:
    """``expand`` on se mitä indeksointi ja kysely käyttävät."""

    def test_sailyttaa_alkuperaisen(self) -> None:
        """Additiivisuus on koko turvallisuuden perusta."""
        assert "satotilasto" in expand("satotilasto", LEX)

    def test_lisaa_osat(self) -> None:
        result = expand("satotilasto", LEX)
        assert "sato" in result and "tilasto" in result

    def test_jakamaton_palautuu_sellaisenaan(self) -> None:
        assert expand("kaupunkirakenne", LEX) == ["kaupunkirakenne"]

    def test_ei_duplikaatteja(self) -> None:
        result = expand("satotilasto", LEX)
        assert len(result) == len(set(result))

    def test_jarjestys_on_vakaa(self) -> None:
        """Sama syöte tuottaa saman tuloksen — muuten indeksi heiluu turhaan."""
        assert expand("satotilasto", LEX) == expand("satotilasto", LEX)


class TestKorpussanasto:
    def test_lexicon_rakentuu_kannasta(self, tmp_path: object) -> None:
        import sqlite3

        from aura.database import init_db
        from aura.decompound import build_lexicon

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        init_db(conn)
        conn.execute(
            "INSERT INTO datasets (id, name, lemmas) VALUES (?,?,?)",
            ("a", "a", "sato tilasto metsä"),
        )
        conn.execute(
            "INSERT INTO datasets (id, name, lemmas) VALUES (?,?,?)",
            ("b", "b", "sato metsä vara"),
        )
        conn.commit()

        # Kynnys 2: mukaan vain sanat jotka esiintyvät useammassa datasetissä.
        lex = build_lexicon(conn, min_datasets=2)
        assert lex.knows("sato") and lex.knows("metsä")
        assert not lex.knows("tilasto"), "yhden datasetin sana ei kuulu sanastoon"
        assert lex.total == 2


class TestErottelukyky:
    """Yleinen osa pudotetaan, erotteleva säilyy.

    Ilman tätä ``tulvariskialue`` → ``tulvariski`` + ``alue`` laajensi
    löysän haun 50 tulokseen; laatuportti sallii alle 20. Pelkkä
    frekvenssikatto ei olisi riittänyt valintaperusteeksi, koska haluttu
    ``tilasto`` on korpuksessa yleisempi kuin ongelmallinen ``alue``.
    """

    def test_yleinen_osa_pudotetaan(self) -> None:
        result = expand("tulvariskialue", LEX)
        assert "tulvariski" in result
        assert "alue" not in result

    def test_erotteleva_osa_sailyy(self) -> None:
        assert "sato" in expand("satotilasto", LEX)

    def test_alkuperainen_sailyy_vaikka_kaikki_osat_pudotettaisiin(self) -> None:
        lex = Lexicon({"alue": 3000, "kunta": 4000}, total=10_000)
        assert expand("aluekunta", lex) == ["aluekunta"]
