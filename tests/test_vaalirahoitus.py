"""Testit vaalirahoitus-harvesterille."""

from typing import Any

from aura.harvesters.vaalirahoitus import VaalirahoitusHarvester


def _dataset_config(ds_id: str) -> dict[str, Any]:
    """Hae yhden datasetin konfiguraatio id:n perusteella."""
    for cfg in VaalirahoitusHarvester.datasets_config:
        if cfg["id"] == ds_id:
            return cfg
    raise AssertionError(f"Datasettiä {ds_id} ei löydy")


class TestJalkiIlmoitukset:
    """E_JI lisätään vain niille vaaleille joilla se oikeasti on."""

    def test_election_with_ji_has_five_resources(self) -> None:
        cfg = _dataset_config("vaalirahoitus-eduskuntavaalit2023")
        assert len(cfg["resources"]) == 5

    def test_election_without_ji_has_four_resources(self) -> None:
        cfg = _dataset_config("vaalirahoitus-kuntavaalit2025")
        assert len(cfg["resources"]) == 4

    def test_ji_url_is_correct(self) -> None:
        cfg = _dataset_config("vaalirahoitus-aluevaalit2025")
        urls = [r["url"] for r in cfg["resources"]]
        assert (
            "https://www.vaalirahoitusvalvonta.fi/fi/index/vaalirahoitus/"
            "haetietoavaalirahoitusilmoituksista/tutkitietoaineistoja/"
            "aluevaalit2025/E_JI_aluevaalit2025.csv"
        ) in urls

    def test_only_four_elections_have_ji(self) -> None:
        """Tarkka lista — ei saa vuotaa muille vaaleille."""
        with_ji = [
            cfg["id"]
            for cfg in VaalirahoitusHarvester.datasets_config
            if any("E_JI" in r["url"] for r in cfg["resources"])
        ]
        assert sorted(with_ji) == [
            "vaalirahoitus-aluevaalit2022",
            "vaalirahoitus-aluevaalit2025",
            "vaalirahoitus-eduskuntavaalit2023",
            "vaalirahoitus-europarlamenttivaalit2024",
        ]


class TestExistingResourcesUnchanged:
    """Vanhat resurssit eivät saa muuttua."""

    def test_all_elections_still_have_evi(self) -> None:
        for cfg in VaalirahoitusHarvester.datasets_config:
            if not cfg["id"].startswith("vaalirahoitus-puoluerahoitus"):
                urls = " ".join(r["url"] for r in cfg["resources"])
                assert "E_VI_" in urls

    def test_party_year_datasets_untouched(self) -> None:
        cfg = _dataset_config("vaalirahoitus-puoluerahoitus-2024")
        assert len(cfg["resources"]) == 1
