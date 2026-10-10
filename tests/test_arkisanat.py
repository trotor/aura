"""Arkisanaston muunnelmat (ulkoinen arvio 27.9.2026)."""

from __future__ import annotations

import sqlite3

from aura.decompound import load_lexicon
from aura.vocabularies import reset_cache, synonym_variants, synonym_variants_ranked


def test_yhdyssanan_osa_perusmuotona() -> None:
    reset_cache()
    lexicon = load_lexicon(sqlite3.connect("data/aura.db"))
    assert "varhaiskasvatus" in synonym_variants("päiväkotipaikat", lexicon)


def test_taivutettu_sana_korvataan_kyselyssa() -> None:
    variants = synonym_variants("kirjastojen lainaukset kunnittain")
    assert "kirjastotilasto lainaukset kunnittain" in variants


def test_monisanainen_avain_on_vahva() -> None:
    ranked = dict(synonym_variants_ranked("uudet yritykset"))
    assert ranked == {"aloittaneet yritykset": True}


def test_vain_arkisanasto_ei_aihesanastoja() -> None:
    # "koulu" on aihesanastossa (→ kouluverkko), ei arkisanastossa.
    assert synonym_variants("koulu") == []


def test_puun_ja_metsan_hinta_arkisanoina() -> None:
    """"kantohinta" ja "metsän hinta" ohjaavat tilastojen omiin nimiin (10.10.2026)."""
    reset_cache()
    assert "teollisuuspuun kauppa" in synonym_variants("kantohinta")
    assert dict(synonym_variants_ranked("puun hinta")) == {"teollisuuspuun kauppa": True}
    assert "metsätilojen hinnat" in dict(synonym_variants_ranked("metsän hinta"))
