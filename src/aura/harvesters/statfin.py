"""Harvester Tilastokeskuksen PxWeb API:lle."""

from __future__ import annotations

import logging

from aura.harvesters.pxweb import PxWebDatabase, PxWebHarvester

logger = logging.getLogger(__name__)


class StatfinHarvester(PxWebHarvester):
    """Kerää tilastotaulut Tilastokeskuksen PxWeb API:sta.

    PxWeb-rajapinta on puumainen: juuritaso → aihealueet → alataso → taulut.
    Jokainen taulu on yksi datasetti.

    StatFinin lisäksi samalla palvelimella on muita tietokantoja
    (``extra_databases``). Niiden taulut saavat tunnisteen
    ``statfin-<slug>-<taulu>``, jotta ne eivät törmää StatFinin tauluihin;
    StatFinin omat tunnisteet pysyvät ennallaan (``statfin-<taulu>``), koska
    rikastukset ja tunnusluvut viittaavat niihin.
    """

    name = "statfin"
    description = "Tilastokeskus (Statistics Finland) — PxWeb-tilastot"
    url = "https://stat.fi"
    pxweb_base_url = "https://statfin.stat.fi/PxWeb/api/v1"
    root_path = "StatFin"
    web_base_url = "https://statfin.stat.fi/PxWeb/pxweb/fi"
    org_id = "tilastokeskus"
    org_name = "tilastokeskus"
    org_title = "Tilastokeskus"
    dataset_id_prefix = "statfin"
    notes_template = "Tilastokeskuksen tilastotaulu"
    #: Tilastokeskuksen raja on 30 pyyntöä 10 sekunnissa. Oletusviive 0,2 s
    #: ylittää sen varmasti, ja jokainen 429 maksaa minuutin odotuksen
    #: (Retry-After: 60). 0,4 s pysyy rajan alla.
    request_delay = 0.4

    #: Tilastokeskuksen muut tietokannat (tarkistettu 8.10.2026).
    #:
    #: Pois jätetyt: ``StatFin_Passiivi`` (3 615 lakkautettua taulua),
    #: ``Muuttaneiden_taustatiedot`` (vuodet 2000–2001) ja ``Check``
    #: (tekninen). Paavosta ja kuntien avainluvuista vain ``uusin``: muut
    #: kansiot ovat saman taulun vanhoja vuosiversioita.
    extra_databases: tuple[PxWebDatabase, ...] = (
        PxWebDatabase(
            dbid="Postinumeroalueittainen_avoin_tieto",
            slug="paavo",
            keywords_fi=("Paavo", "postinumeroalue", "postinumeroalueittain", "postinumero"),
            keywords_en=("Paavo", "postal code area", "postcode"),
            folders=("uusin",),
            notes=(
                "Paavo – postinumeroalueittainen avoin tieto: väestörakenne, "
                "koulutus, tulot, talouksien koko ja elämänvaihe, asuminen, "
                "työpaikat ja pääasiallinen toiminta postinumeroalueittain"
            ),
        ),
        PxWebDatabase(
            dbid="Kuntien_avainluvut",
            slug="avainluvut",
            keywords_fi=("kuntien avainluvut", "kunta", "avainluku"),
            keywords_en=("municipal key figures", "municipality"),
            folders=("uusin",),
            notes=(
                "Kuntien avainluvut: väestö, työllisyys, talous, koulutus ja "
                "asuminen kunnittain yhdessä taulussa"
            ),
        ),
        PxWebDatabase(
            dbid="Kuntien_talous_ja_toiminta",
            slug="kuntatalous",
            keywords_fi=("kuntatalous", "kunta", "kuntayhtymä", "tilinpäätös"),
            keywords_en=("municipal finances", "municipality", "financial statements"),
            notes=(
                "Kuntien ja kuntayhtymien talous ja toiminta: tilinpäätökset, "
                "käyttötalous ja investoinnit tehtävittäin, tunnusluvut ja "
                "toimintatiedot kunnittain (1975–2020)"
            ),
        ),
        PxWebDatabase(
            dbid="Kokeelliset_tilastot",
            slug="kokeelliset",
            keywords_fi=("kokeellinen tilasto",),
            keywords_en=("experimental statistics",),
            notes="Tilastokeskuksen kokeellinen tilasto",
        ),
        PxWebDatabase(
            dbid="Maahanmuuttajat_ja_kotoutuminen",
            slug="maahanmuuttajat",
            keywords_fi=("maahanmuuttaja", "kotoutuminen", "ulkomaalaistaustainen"),
            keywords_en=("immigrants", "integration", "foreign background"),
            notes=(
                "Maahanmuuttajat ja kotoutuminen: ulkomaalaistaustaisen "
                "väestön koulutus, työllisyys, tulot ja asuminen"
            ),
        ),
        PxWebDatabase(
            dbid="Toimipaikkalaskuri",
            slug="toimipaikat",
            keywords_fi=("toimipaikka", "yritys", "henkilöstö"),
            keywords_en=("establishments", "enterprises", "personnel"),
            notes="Toimipaikkalaskuri: yritysten toimipaikat ja henkilöstö alueittain",
        ),
        PxWebDatabase(
            dbid="Hyvinvointialueet",
            slug="hyvinvointialueet",
            keywords_fi=("hyvinvointialue",),
            keywords_en=("wellbeing services county",),
            notes="Hyvinvointialueiden tilastotaulu",
        ),
        PxWebDatabase(
            dbid="SDG",
            slug="sdg",
            keywords_fi=("kestävä kehitys", "SDG", "Agenda 2030"),
            keywords_en=("sustainable development goals", "SDG"),
            notes="Kestävän kehityksen tavoitteiden (SDG) indikaattorit Suomelle",
        ),
    )

    async def harvest(self) -> int:
        total = await super().harvest()
        for db in self.extra_databases:
            total += await self._harvest_database(db)
        return total

    async def _harvest_database(self, db: PxWebDatabase) -> int:
        """Kerää yhden lisätietokannan vaihtamalla juuren hetkeksi.

        Kantaluokan metodit lukevat juuren, etuliitteen ja kuvauspohjan
        instanssin attribuuteista, joten vaihto riittää. Arvot palautetaan
        aina, ettei seuraava ajo kerää StatFiniä väärällä etuliitteellä.
        """
        saved = (
            self.root_path,
            self.root_folders,
            self.dataset_id_prefix,
            self.notes_template,
            self.database_keywords_fi,
            self.database_keywords_en,
        )
        self.root_path = db.dbid
        self.root_folders = db.folders
        self.dataset_id_prefix = f"{saved[2]}-{db.slug}"
        self.notes_template = db.notes or saved[3]
        self.database_keywords_fi = db.keywords_fi
        self.database_keywords_en = db.keywords_en
        try:
            count = await super().harvest()
        finally:
            (
                self.root_path,
                self.root_folders,
                self.dataset_id_prefix,
                self.notes_template,
                self.database_keywords_fi,
                self.database_keywords_en,
            ) = saved
        logger.info("[%s] %s: %d taulua", self.name, db.dbid, count)
        return count
