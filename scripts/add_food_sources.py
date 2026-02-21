#!/usr/bin/env python3
"""Lisää tutkimuksessa löydetyt ruokaan liittyvät tietolähteet Auran tietokantaan.

Kaksi strategiaa:
1. Uudet datasetit (joita ei löydy Aurasta) → upsert_dataset()
2. Rikastukset olemassa oleviin → add_enrichment()

Aja: source .venv/bin/activate && python scripts/add_food_sources.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, UTC
from pathlib import Path

# Lisää src/ polkuun
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from aura.database import add_enrichment, get_connection, init_db, upsert_dataset
from aura.models import Dataset, Resource


def make_dataset(
    id: str,
    name: str,
    title_fi: str,
    notes_fi: str,
    organization_title: str,
    keywords_fi: list[str],
    resources: list[dict],
    *,
    license_id: str = "cc-by-4.0",
    license_title: str = "CC BY 4.0",
    source: str = "manual",
    update_frequency: str = "",
    title_en: str = "",
    notes_en: str = "",
    access_level: str = "open",
    geographical_coverage: list[str] | None = None,
) -> Dataset:
    """Apufunktio datasetin luontiin."""
    res_objects = []
    for i, r in enumerate(resources):
        res_objects.append(
            Resource(
                id=f"{id}-res-{i}",
                name=r.get("name", ""),
                name_fi=r.get("name", ""),
                format=r.get("format", ""),
                url=r.get("url", ""),
                description_fi=r.get("description", ""),
            )
        )
    now = datetime.now(UTC).isoformat()
    return Dataset(
        id=id,
        name=name,
        title=title_fi,
        title_fi=title_fi,
        title_en=title_en,
        notes=notes_fi,
        notes_fi=notes_fi,
        notes_en=notes_en,
        license_id=license_id,
        license_title=license_title,
        organization_title=organization_title,
        metadata_modified=now,
        keywords_fi=keywords_fi,
        geographical_coverage=geographical_coverage or ["Suomi"],
        update_frequency=update_frequency,
        collection_type="Open Data",
        num_resources=len(res_objects),
        resources=res_objects,
        source=source,
        access_level=access_level,
    )


# ─── Uudet datasetit (ei vielä Aurassa) ───────────────────────────────────

NEW_DATASETS = [
    # ── Fineli ──
    make_dataset(
        id="fineli-ravintotietokanta",
        name="fineli-ravintotietokanta",
        title_fi="Fineli — Elintarvikkeiden koostumustietokanta",
        title_en="Fineli — Finnish Food Composition Database",
        notes_fi=(
            "Kansallinen elintarvikkeiden koostumustietokanta. Sisältää 4 232 elintarviketta "
            "ja 55–74 ravintoainetta per tuote: energia, makroravinteet, vitamiinit, "
            "kivennäisaineet, rasvahapot. REST API ja CSV-lataus saatavilla."
        ),
        notes_en=(
            "National food composition database. Contains 4,232 food items with 55-74 "
            "nutrient factors per item: energy, macronutrients, vitamins, minerals, fatty acids."
        ),
        organization_title="Terveyden ja hyvinvoinnin laitos (THL)",
        keywords_fi=[
            "ravitsemus", "elintarvike", "ruoka", "ravintoaine", "vitamiini",
            "koostumus", "Fineli", "ravintosisältö",
        ],
        update_frequency="jatkuva",
        resources=[
            {"name": "REST API", "format": "JSON", "url": "https://fineli.fi/fineli/api/v1/foods", "description": "Haku: ?q=hakusana"},
            {"name": "CSV-peruspaketti 1 (55 ravintoainetta)", "format": "CSV", "url": "https://fineli.fi/fineli/fi/avoin-data", "description": "1.5 MB, 4232 elintarviketta"},
            {"name": "CSV-peruspaketti 2 (74 ravintoainetta)", "format": "CSV", "url": "https://fineli.fi/fineli/fi/avoin-data", "description": "1.9 MB, 4232 elintarviketta"},
            {"name": "CSV-ainesosapaketti (40 ravintoainetta)", "format": "CSV", "url": "https://fineli.fi/fineli/fi/avoin-data", "description": "0.5 MB, 1370 perusainesosaa"},
        ],
    ),
    # ── Oiva ──
    make_dataset(
        id="oiva-elintarvikevalvonta",
        name="oiva-elintarvikevalvonta",
        title_fi="Oiva — Elintarvikevalvonnan tarkastustulokset",
        title_en="Oiva — Food Safety Inspection Results",
        notes_fi=(
            "Elintarvikevalvonnan julkaisujärjestelmä. Sisältää kaikkien Suomen "
            "elintarvikeyritysten (ravintolat, kaupat, tuotantolaitokset) "
            "tarkastustulokset Oiva-hymynaama-asteikolla (A–D). "
            "Julkaistaan 10 päivän sisällä tarkastuksesta. "
            "Ei julkista API:a — data haettavissa verkkosivulta yrityksen nimellä, "
            "postinumerolla tai kunnalla."
        ),
        organization_title="Ruokavirasto",
        keywords_fi=[
            "elintarvikevalvonta", "ruokaturvallisuus", "tarkastus", "Oiva",
            "ravintola", "hygienia", "elintarvikeyritys",
        ],
        update_frequency="jatkuva",
        access_level="open",
        resources=[
            {"name": "Oivahymy.fi hakupalvelu", "format": "HTML", "url": "https://www.oivahymy.fi/", "description": "Ei API:a, verkkohaku"},
        ],
    ),
    # ── Ruokaviraston avoin tieto -portaali ──
    make_dataset(
        id="ruokavirasto-avointieto-elintarvike",
        name="ruokavirasto-avointieto-elintarvike",
        title_fi="Ruokavirasto avointieto — Elintarvikedata",
        notes_fi=(
            "Ruokaviraston avoimen tiedon portaali. Elintarvikeosiossa: "
            "ruokamyrkytysepidemiat (2 505 epidemiaa vuodesta 1975), "
            "luomutoimijat. Eläinosiossa: antibioottiresistenssi (FINRES-Vet), "
            "eläintaudit, luonnonvaraiset eläimet, rehuvalvonta, rehutoimijat. "
            "Kasviosiossa: tuholaisseuranta, siemenpakkaamot, "
            "viljan sadon laatu (päivittyy yöllä satokauden aikana), "
            "lannoitevalvonta."
        ),
        organization_title="Ruokavirasto",
        keywords_fi=[
            "elintarvike", "ruokamyrkytys", "luomu", "antibioottiresistenssi",
            "eläintauti", "rehu", "siemen", "viljan laatu", "lannoite",
            "ruokavirasto", "elintarviketurvallisuus",
        ],
        update_frequency="jatkuva",
        resources=[
            {"name": "Avointieto-portaali", "format": "HTML", "url": "https://avointieto.ruokavirasto.fi/", "description": "SPA-sovellus, interaktiivinen analytiikka"},
        ],
    ),
    # ── Ruokaviraston INSPIRE-rajapinnat ──
    make_dataset(
        id="ruokavirasto-inspire-wfs",
        name="ruokavirasto-inspire-wfs",
        title_fi="Ruokavirasto — INSPIRE-paikkatietopalvelut (WMS/WFS)",
        notes_fi=(
            "Ruokaviraston INSPIRE-yhteensopivat paikkatietorajapinnat. "
            "Sisältää peltolohkorekisterin, kasvulohkot, maatalousmaan ja "
            "maisemapiirteet WMS/WFS-palveluina. Kasvulohkodatassa mm. "
            "kasvilaji, pinta-ala, luomutuotantostatus, rinteen kaltevuus, "
            "pohjavesialue, Natura-alue."
        ),
        organization_title="Ruokavirasto",
        keywords_fi=[
            "INSPIRE", "paikkatietoaineisto", "WFS", "WMS",
            "peltolohko", "kasvulohko", "maatalousmaa",
        ],
        resources=[
            {"name": "WFS", "format": "WFS", "url": "https://inspire.ruokavirasto-awsa.com/geoserver/wfs?request=getcapabilities", "description": "INSPIRE WFS ladattava"},
            {"name": "WMS", "format": "WMS", "url": "https://inspire.ruokavirasto-awsa.com/geoserver/wms?request=getcapabilities", "description": "INSPIRE WMS katselua varten"},
        ],
    ),
    # ── Open Food Facts Suomi ──
    make_dataset(
        id="open-food-facts-finland",
        name="open-food-facts-finland",
        title_fi="Open Food Facts — Suomen elintarviketuotteet",
        title_en="Open Food Facts — Finnish Products",
        notes_fi=(
            "Yhteisöpohjainen elintarviketuotetietokanta. Suomesta ~18 000 tuotetta. "
            "Sisältää viivakoodin, tuotenimen, ainesosat, ravintoarvot, Nutri-Score, "
            "NOVA-ryhmän, allergeenit, tuotemerkin. Tuotteita mm. S-ryhmältä, "
            "Keskolta, Valiolta, Fazerilta."
        ),
        organization_title="Open Food Facts (yhteisö)",
        keywords_fi=[
            "elintarvike", "tuotetieto", "ravintosisältö", "Nutri-Score",
            "ainesosat", "viivakoodi", "NOVA", "allergeeni", "ruoka",
        ],
        license_id="ODbL-1.0",
        license_title="Open Database License (ODbL)",
        update_frequency="jatkuva",
        resources=[
            {"name": "REST API v2", "format": "JSON", "url": "https://world.openfoodfacts.org/api/v2/search?countries_tags=en:finland", "description": "Haku Suomen tuotteista"},
            {"name": "CSV-lataus (koko maailma)", "format": "CSV", "url": "https://world.openfoodfacts.org/data/en.openfoodfacts.org.products.csv.gz", "description": "Massiivinen CSV, suodatettava maittain"},
            {"name": "Suomi-portaali", "format": "HTML", "url": "https://fi.openfoodfacts.org/", "description": "Selattava suomenkielinen käyttöliittymä"},
        ],
    ),
    # ── Ilmastodieetti API ──
    make_dataset(
        id="syke-ilmastodieetti-api",
        name="syke-ilmastodieetti-api",
        title_fi="Ilmastodieetti.fi — Ruoan ilmastovaikutuslaskuri (API)",
        notes_fi=(
            "SYKE:n REST API ruoan kasvihuonekaasupäästöjen laskentaan. "
            "Kattaa eri ruokakategorioiden (liha, maitotuotteet, kasvikset jne.) "
            "päästökertoimet suomalaisilla arvoilla. Swagger/OpenAPI-dokumentaatio."
        ),
        organization_title="Suomen ympäristökeskus (SYKE)",
        keywords_fi=[
            "ilmasto", "hiilijalanjälki", "ruoka", "kasvihuonekaasu",
            "päästökerroin", "ilmastodieetti",
        ],
        resources=[
            {"name": "REST API (Swagger)", "format": "JSON", "url": "https://rajapinnat.ymparisto.fi/api/ilmastodieetti/swagger/index.html", "description": "OpenAPI-dokumentoitu laskentarajapinta"},
        ],
    ),
    # ── EFSA Food Consumption Database ──
    make_dataset(
        id="efsa-food-consumption-eu",
        name="efsa-food-consumption-eu",
        title_fi="EFSA — Euroopan elintarvikkeiden kulutustietokanta",
        title_en="EFSA Comprehensive European Food Consumption Database",
        notes_fi=(
            "EU:n elintarviketurvallisuusviraston (EFSA) kattava ruoankulutustietokanta. "
            "Sisältää kulutusdata 21+ EU-maasta, myös Suomesta (FinRavinto-tutkimuksen data). "
            "FoodEx2-luokitusjärjestelmä. Interaktiiviset dashboardit ja API."
        ),
        organization_title="European Food Safety Authority (EFSA)",
        keywords_fi=[
            "ruoankulutus", "ravitsemus", "EU", "EFSA", "FoodEx2",
            "FinRavinto", "elintarvike",
        ],
        license_id="open",
        license_title="EFSA Open Data",
        geographical_coverage=["EU", "Suomi"],
        resources=[
            {"name": "EFSA Data Dashboard", "format": "HTML", "url": "https://www.efsa.europa.eu/en/data-report/food-consumption", "description": "Interaktiivinen MicroStrategy-dashboard"},
            {"name": "EU Open Data Portal", "format": "CSV", "url": "https://data.europa.eu/data/datasets/the-efsa-comprehensive-european-food-consumption-database", "description": "Ladattava data"},
        ],
    ),
    # ── RASFF ──
    make_dataset(
        id="rasff-food-feed-alerts",
        name="rasff-food-feed-alerts",
        title_fi="RASFF — Elintarvike- ja rehuhälytykset (EU)",
        title_en="RASFF — Rapid Alert System for Food and Feed",
        notes_fi=(
            "EU:n nopea hälytysjärjestelmä elintarvikkeille ja rehuille. "
            "Yli 3 500 ilmoitusta + 10 000 seurantatoimea vuosittain. "
            "Suodatettavissa ilmoittajamaan (Suomi), tuotekategorian ja "
            "vaaran tyypin mukaan. Data vuodesta 2020."
        ),
        organization_title="European Commission (DG SANTE)",
        keywords_fi=[
            "elintarviketurvallisuus", "RASFF", "hälytys", "rehu",
            "EU", "vaaratilanne", "takaisinveto",
        ],
        license_id="open",
        license_title="EU Open Data",
        geographical_coverage=["EU", "Suomi"],
        resources=[
            {"name": "RASFF Window -portaali", "format": "HTML", "url": "https://webgate.ec.europa.eu/rasff-window/portal/", "description": "Hakuportaali, suodatus Suomen ilmoituksiin"},
        ],
    ),
    # ── THL Sotkanet (ravitsemus) ──
    make_dataset(
        id="thl-sotkanet-ravitsemus",
        name="thl-sotkanet-ravitsemus",
        title_fi="Sotkanet — Ravitsemus- ja terveysindikaattorit",
        notes_fi=(
            "THL:n Sotkanet-indikaattoripankki. ~3 500 indikaattoria väestön "
            "hyvinvoinnista ja terveydestä. Ravitsemukseen liittyviä: "
            "kouluruokailu, ylipaino/lihavuus, ruokailutottumukset "
            "(FinSote, Kouluterveyskysely). REST API palauttaa JSON/CSV."
        ),
        organization_title="Terveyden ja hyvinvoinnin laitos (THL)",
        keywords_fi=[
            "ravitsemus", "terveys", "indikaattori", "ylipaino",
            "kouluruokailu", "ruokailutottumus", "kuntadata",
        ],
        resources=[
            {"name": "REST API (JSON)", "format": "JSON", "url": "https://sotkanet.fi/rest/1.1/indicators", "description": "~3500 indikaattoria, 3 kieltä"},
            {"name": "Sotkanet-portaali", "format": "HTML", "url": "https://sotkanet.fi/sotkanet/fi/", "description": "Interaktiivinen hakuportaali"},
        ],
    ),
    # ── Kasvinsuojeluainerekisteri ──
    make_dataset(
        id="tukes-kasvinsuojeluaineet",
        name="tukes-kasvinsuojeluaineet",
        title_fi="Kasvinsuojeluainerekisteri",
        notes_fi=(
            "Tukesin ylläpitämä rekisteri kaikista Suomessa hyväksytyistä "
            "kasvinsuojeluaineista. Sisältää hyväksytyt käyttökohteet "
            "(kasvit, tuholaiset, käyttöpaikat). Satoja hyväksyttyjä valmisteita."
        ),
        organization_title="Turvallisuus- ja kemikaalivirasto (Tukes)",
        keywords_fi=[
            "kasvinsuojeluaine", "torjunta-aine", "pestisidi",
            "maatalous", "viljely", "Tukes",
        ],
        resources=[
            {"name": "KemiDigi-haku", "format": "HTML", "url": "https://www.kemidigi.fi/kasvinsuojeluainerekisteri/haku", "description": "Hakupalvelu, ladattavissa CSV/Excel"},
            {"name": "Avoindata.fi", "format": "CSV", "url": "https://www.avoindata.fi/data/fi/dataset/kasvinsuojeluaineet", "description": "CSV-lataus"},
        ],
    ),
    # ── LUKE Biomassa-atlas ──
    make_dataset(
        id="luke-biomassa-atlas",
        name="luke-biomassa-atlas",
        title_fi="Biomassa-atlas — Ruokahävikki ja biomassat",
        notes_fi=(
            "Luken Biomassa-atlas kattaa metsätalouden, maatalouden ja "
            "biohajoavan jätteen paikkatiedot. Ruokahävikkidata: "
            "alkutuotanto 9 kg/hlö, teollisuus 29 kg/hlö, vähittäiskauppa 10 kg/hlö, "
            "ravintolat 14 kg/hlö, kotitaloudet 25 kg/hlö. "
            "Yhteensä 116 kg/hlö/v, 641 milj. kg kansallisesti."
        ),
        organization_title="Luonnonvarakeskus (LUKE)",
        keywords_fi=[
            "biomassa", "ruokahävikki", "ruokajäte", "maatalous",
            "paikkatietoaineisto", "kiertotalous",
        ],
        resources=[
            {"name": "Biomassa-atlas karttasovellus", "format": "HTML", "url": "https://biomassa-atlas.luke.fi/?lang=fi", "description": "Interaktiivinen karttasovellus analytiikalla"},
        ],
    ),
    # ── LUKE Ruokafakta ──
    make_dataset(
        id="luke-ruokafakta",
        name="luke-ruokafakta",
        title_fi="Ruokafakta — Suomalaisen ruoantuotannon tilastot",
        title_en="Food Facts Finland",
        notes_fi=(
            "Luken ja Ruokaviraston yhteinen tilastopalvelu suomalaisen "
            "ruoantuotannon laadusta. Lihantuotanto, maidontuotanto, "
            "luomuviljely, eläinten hyvinvointi, kasvinsuojeluaineiden käyttö, "
            "antibioottien käyttö. Kansainvälinen vertailudata."
        ),
        organization_title="Luonnonvarakeskus (LUKE)",
        keywords_fi=[
            "ruoka", "ruoantuotanto", "liha", "maito", "luomu",
            "eläinten hyvinvointi", "antibiootti", "tilasto",
        ],
        resources=[
            {"name": "Ruokafakta-portaali", "format": "HTML", "url": "https://projects.luke.fi/ruokafakta/fi/etusivu/", "description": "Tilastokaaviot ja vertailudata"},
        ],
    ),
    # ── LUKE FoodGWP ──
    make_dataset(
        id="luke-foodgwp",
        name="luke-foodgwp",
        title_fi="FoodGWP — Ruoan ilmastovaikutusaineisto",
        title_en="FoodGWP — Climate Impact Dataset for Food Service Sector",
        notes_fi=(
            "Luken tuotekohteinen hiilijalanjälkidata ruokapalvelualalle. "
            "Elinkaariarviointi (LCA) suomalaisten elintarvikkeiden "
            "ilmastovaikutuksista."
        ),
        organization_title="Luonnonvarakeskus (LUKE)",
        keywords_fi=[
            "hiilijalanjälki", "ilmastovaikutus", "ruoka", "LCA",
            "elinkaariarviointi", "ruokapalvelu",
        ],
        resources=[
            {"name": "FoodGWP-projekti", "format": "HTML", "url": "https://www.luke.fi/en/projects/foodgwp", "description": "Projektin kuvaus ja ladattava aineisto"},
        ],
    ),
    # ── Eurostat ruokahinnat ──
    make_dataset(
        id="eurostat-food-price-monitoring",
        name="eurostat-food-price-monitoring",
        title_fi="Eurostat — Ruoan hintaseuranta (Food Price Monitoring Tool)",
        notes_fi=(
            "Eurostatin elintarvikkeiden hintakehityksen seuranta kaikissa "
            "EU-maissa, Suomi mukana. HICP-elintarvikeindeksi, "
            "tuottajahinnat, kuluttajahinnat. Kuukausittainen aikasarja."
        ),
        organization_title="Eurostat",
        keywords_fi=[
            "ruoan hinta", "hintaindeksi", "HICP", "EU",
            "kuluttajahinta", "tuottajahinta", "elintarvike",
        ],
        license_id="eurostat",
        license_title="Eurostat Copyright",
        geographical_coverage=["EU", "Suomi"],
        resources=[
            {"name": "Food Price Monitoring Tool", "format": "HTML", "url": "https://ec.europa.eu/eurostat/cache/website/economy/food-price-monitoring/", "description": "Interaktiivinen työkalu"},
            {"name": "prc_fsc_idx tietokanta", "format": "JSON", "url": "https://ec.europa.eu/eurostat/databrowser/product/page/prc_fsc_idx", "description": "Eurostat JSON API / bulk download"},
        ],
    ),
    # ── Kesko Developer API ──
    make_dataset(
        id="kesko-developer-api",
        name="kesko-developer-api",
        title_fi="Kesko Developer API — Päivittäistavaratuotteet",
        notes_fi=(
            "Keskon kehittäjäportaali. Päivittäistavarakaupan API:t sisältäen "
            "tuotetiedot (100 000+ tuotetta), myymälätiedot. "
            "Vaatii rekisteröitymisen ja API-avaimen."
        ),
        organization_title="Kesko Oyj",
        keywords_fi=[
            "päivittäistavara", "ruokakauppa", "tuotetieto", "K-ruoka",
            "API", "kauppa",
        ],
        license_id="proprietary",
        license_title="Kesko API Terms",
        access_level="registration",
        resources=[
            {"name": "Developer Portal", "format": "JSON", "url": "https://developer.kesko.fi/", "description": "REST API:t, vaatii rekisteröitymisen"},
        ],
    ),
    # ── LUKE opendata.luke.fi ──
    make_dataset(
        id="luke-opendata-portal",
        name="luke-opendata-portal",
        title_fi="LUKE Open Data — Tutkimusaineistot (CKAN)",
        notes_fi=(
            "Luonnonvarakeskuksen avoin tutkimusdataportaali. 124 datasettiä "
            "sisältäen: peltobiomassat, peltokasvien sivuvirrat, "
            "yhdyskuntien biojätteet, kalankasvatusalueet, "
            "peltokasvien pinta-alat. Formaatit: WMS, PDF, CSV, JSON."
        ),
        organization_title="Luonnonvarakeskus (LUKE)",
        keywords_fi=[
            "tutkimusdata", "biomassa", "peltokasvit", "biojäte",
            "kalankasvatus", "LUKE", "avoin data",
        ],
        resources=[
            {"name": "CKAN-portaali", "format": "HTML", "url": "https://opendata.luke.fi/dataset", "description": "124 datasettiä, useita formaatteja"},
        ],
    ),
]


# ─── Rikastukset olemassa oleviin datasetteihin ──────────────────────────

ENRICHMENTS = [
    # LUKE PxWeb -taulut: elintarvikkeiden kulutus
    {
        "dataset_id": "luke-01_Elintarvikkeiden_kulutus",
        "field": "description_extended",
        "value": "Elintarvikkeiden kulutus henkeä kohti Suomessa (kg/vuosi). Kattaa kaikki elintarvikekategoriat: liha, maito, vilja, hedelmät, kasvikset, kala jne.",
        "confidence": "high",
        "source_type": "web_research",
        "source_detail": "https://statdb.luke.fi/",
    },
    {
        "dataset_id": "luke-01_Elintarvikkeiden_kulutus",
        "field": "keywords",
        "value": json.dumps(["ruoankulutus", "elintarvike", "ravinto", "ruoka", "kulutustilasto"], ensure_ascii=False),
        "confidence": "high",
        "source_type": "web_research",
        "source_detail": "https://statdb.luke.fi/",
    },
    # Ravintotase
    {
        "dataset_id": "luke-02_Ravintotase",
        "field": "description_extended",
        "value": "Suomen ravintotase (milj. kg). Kattava tilasto ruoan tuotannosta, tuonnista, viennistä, varastoista ja kulutuksesta elintarvikeryhmittäin.",
        "confidence": "high",
        "source_type": "web_research",
        "source_detail": "https://statdb.luke.fi/",
    },
    {
        "dataset_id": "luke-02_Ravintotase",
        "field": "keywords",
        "value": json.dumps(["ravintotase", "ruoka", "elintarvike", "tuotanto", "kulutus", "vienti", "tuonti"], ensure_ascii=False),
        "confidence": "high",
        "source_type": "web_research",
        "source_detail": "https://statdb.luke.fi/",
    },
    # Lihantuotanto
    {
        "dataset_id": "luke-0100_lihtuo",
        "field": "keywords",
        "value": json.dumps(["liha", "teurastus", "lihantuotanto", "nauta", "sika", "siipikarja", "broileri", "lammas", "ruoka"], ensure_ascii=False),
        "confidence": "high",
        "source_type": "web_research",
        "source_detail": "https://statdb.luke.fi/",
    },
    {
        "dataset_id": "luke-0400_lihtuo",
        "field": "keywords",
        "value": json.dumps(["liha", "lihantuotanto", "kokonaistuotanto", "ruoka"], ensure_ascii=False),
        "confidence": "high",
        "source_type": "web_research",
        "source_detail": "https://statdb.luke.fi/",
    },
    # Maidontuotanto
    {
        "dataset_id": "luke-0100_maitot",
        "field": "keywords",
        "value": json.dumps(["maito", "meijerimaito", "maidontuotanto", "ruoka", "maitotuote"], ensure_ascii=False),
        "confidence": "high",
        "source_type": "web_research",
        "source_detail": "https://statdb.luke.fi/",
    },
    {
        "dataset_id": "luke-0700_maitot",
        "field": "keywords",
        "value": json.dumps(["maito", "maidontuotanto", "kokonaistuotanto", "ruoka"], ensure_ascii=False),
        "confidence": "high",
        "source_type": "web_research",
        "source_detail": "https://statdb.luke.fi/",
    },
    # Kananmunat
    {
        "dataset_id": "luke-0100_kanmun",
        "field": "keywords",
        "value": json.dumps(["kananmuna", "munantuotanto", "ruoka", "siipikarja"], ensure_ascii=False),
        "confidence": "high",
        "source_type": "web_research",
        "source_detail": "https://statdb.luke.fi/",
    },
    # Kalatalous
    {
        "dataset_id": "luke-01_koko_kalantuotanto",
        "field": "keywords",
        "value": json.dumps(["kala", "kalantuotanto", "kalatalous", "kalastus", "vesiviljely", "ruoka"], ensure_ascii=False),
        "confidence": "high",
        "source_type": "web_research",
        "source_detail": "https://statdb.luke.fi/",
    },
    {
        "dataset_id": "luke-2_Kalankulutus",
        "field": "keywords",
        "value": json.dumps(["kala", "kalankulutus", "elintarvike", "ruoka"], ensure_ascii=False),
        "confidence": "high",
        "source_type": "web_research",
        "source_detail": "https://statdb.luke.fi/",
    },
    {
        "dataset_id": "luke-0100_kaltuo",
        "field": "keywords",
        "value": json.dumps(["kala", "tuottajahinta", "kalatalous", "ruoka"], ensure_ascii=False),
        "confidence": "high",
        "source_type": "web_research",
        "source_detail": "https://statdb.luke.fi/",
    },
    # Satotilastot
    {
        "dataset_id": "luke-0100_sattil",
        "field": "keywords",
        "value": json.dumps(["sato", "vilja", "viljelykasvit", "maatalous", "ruoka", "satotilasto"], ensure_ascii=False),
        "confidence": "high",
        "source_type": "web_research",
        "source_detail": "https://statdb.luke.fi/",
    },
    {
        "dataset_id": "luke-0400_sattil",
        "field": "keywords",
        "value": json.dumps(["sato", "vilja", "satotilasto", "ruoka", "maatalous", "aikasarja"], ensure_ascii=False),
        "confidence": "high",
        "source_type": "web_research",
        "source_detail": "https://statdb.luke.fi/",
    },
    # Viljavarasto
    {
        "dataset_id": "luke-0100_vilvar",
        "field": "keywords",
        "value": json.dumps(["vilja", "viljavarasto", "valkuaiskasvi", "öljykasvi", "ruoka", "maatalous"], ensure_ascii=False),
        "confidence": "high",
        "source_type": "web_research",
        "source_detail": "https://statdb.luke.fi/",
    },
    # Viljatase
    {
        "dataset_id": "luke-0100_viltas",
        "field": "keywords",
        "value": json.dumps(["vilja", "viljatase", "tuotanto", "kulutus", "vienti", "tuonti", "ruoka"], ensure_ascii=False),
        "confidence": "high",
        "source_type": "web_research",
        "source_detail": "https://statdb.luke.fi/",
    },
    # Puutarhatuotanto
    {
        "dataset_id": "luke-0400_puutar",
        "field": "keywords",
        "value": json.dumps(["puutarha", "vihannes", "avomaa", "ruoka", "kasvituotanto"], ensure_ascii=False),
        "confidence": "high",
        "source_type": "web_research",
        "source_detail": "https://statdb.luke.fi/",
    },
    {
        "dataset_id": "luke-0500_puutar",
        "field": "keywords",
        "value": json.dumps(["kasvihuone", "vihannes", "tomaatti", "kurkku", "ruoka", "kasvituotanto"], ensure_ascii=False),
        "confidence": "high",
        "source_type": "web_research",
        "source_detail": "https://statdb.luke.fi/",
    },
    # Tuottajahinnat (ruoka)
    {
        "dataset_id": "luke-0100_tuohin",
        "field": "keywords",
        "value": json.dumps(["maito", "tuottajahinta", "hinta", "ruoka"], ensure_ascii=False),
        "confidence": "high",
        "source_type": "web_research",
        "source_detail": "https://statdb.luke.fi/",
    },
    {
        "dataset_id": "luke-0200_tuohin",
        "field": "keywords",
        "value": json.dumps(["liha", "tuottajahinta", "hinta", "ruoka", "nauta", "sika"], ensure_ascii=False),
        "confidence": "high",
        "source_type": "web_research",
        "source_detail": "https://statdb.luke.fi/",
    },
    {
        "dataset_id": "luke-0300_tuohin",
        "field": "keywords",
        "value": json.dumps(["kananmuna", "tuottajahinta", "hinta", "ruoka"], ensure_ascii=False),
        "confidence": "high",
        "source_type": "web_research",
        "source_detail": "https://statdb.luke.fi/",
    },
    {
        "dataset_id": "luke-0400_tuohin",
        "field": "keywords",
        "value": json.dumps(["vilja", "rypsi", "rapsi", "tuottajahinta", "hinta", "ruoka"], ensure_ascii=False),
        "confidence": "high",
        "source_type": "web_research",
        "source_detail": "https://statdb.luke.fi/",
    },
    {
        "dataset_id": "luke-0500_tuohin",
        "field": "keywords",
        "value": json.dumps(["peruna", "ruokaperuna", "tuottajahinta", "hinta", "ruoka"], ensure_ascii=False),
        "confidence": "high",
        "source_type": "web_research",
        "source_detail": "https://statdb.luke.fi/",
    },
    {
        "dataset_id": "luke-0550_tuohin",
        "field": "keywords",
        "value": json.dumps(["puutarha", "vihannes", "hedelmä", "tuottajahinta", "hinta", "ruoka"], ensure_ascii=False),
        "confidence": "high",
        "source_type": "web_research",
        "source_detail": "https://statdb.luke.fi/",
    },
    # Ulkomaankauppa
    {
        "dataset_id": "luke-Luke_maa_Ukaup_v",
        "field": "keywords",
        "value": json.dumps(["ulkomaankauppa", "elintarvike", "vienti", "tuonti", "ruoka", "maataloustuote"], ensure_ascii=False),
        "confidence": "high",
        "source_type": "web_research",
        "source_detail": "https://statdb.luke.fi/",
    },
    # Luomuliha
    {
        "dataset_id": "luke-0500_lihtuo",
        "field": "keywords",
        "value": json.dumps(["luomu", "luomuliha", "lihantuotanto", "ruoka", "ekologinen"], ensure_ascii=False),
        "confidence": "high",
        "source_type": "web_research",
        "source_detail": "https://statdb.luke.fi/",
    },
    # EU-hinnat
    {
        "dataset_id": "luke-0100_euhint",
        "field": "keywords",
        "value": json.dumps(["vilja", "hinta", "EU", "hintanoteeraus", "ruoka"], ensure_ascii=False),
        "confidence": "high",
        "source_type": "web_research",
        "source_detail": "https://statdb.luke.fi/",
    },
]


def main() -> None:
    conn = get_connection()
    init_db(conn)

    # 1. Lisää uudet datasetit
    print("═══ Lisätään uudet datasetit ═══")
    ds_count = 0
    for ds in NEW_DATASETS:
        upsert_dataset(conn, ds)
        print(f"  ✓ {ds.id}: {ds.title_fi}")
        ds_count += 1
    print(f"\nLisätty {ds_count} uutta datasettiä.")

    # 2. Lisää rikastukset
    print("\n═══ Lisätään rikastukset olemassa oleviin datasetteihin ═══")
    en_count = 0
    skipped = 0
    for e in ENRICHMENTS:
        # Tarkista onko datasetti olemassa
        exists = conn.execute(
            "SELECT 1 FROM datasets WHERE id = ? OR name = ?",
            (e["dataset_id"], e["dataset_id"]),
        ).fetchone()
        if not exists:
            print(f"  ⚠ Ohitetaan: {e['dataset_id']} (ei löydy kannasta)")
            skipped += 1
            continue
        try:
            add_enrichment(
                conn,
                dataset_id=e["dataset_id"],
                field=e["field"],
                value=e["value"],
                confidence=e.get("confidence", "high"),
                source_type=e.get("source_type", "web_research"),
                source_detail=e.get("source_detail", ""),
            )
            print(f"  ✓ {e['dataset_id']}.{e['field']}")
            en_count += 1
        except Exception as exc:
            print(f"  ✗ {e['dataset_id']}.{e['field']}: {exc}")

    print(f"\nLisätty {en_count} rikastusta, ohitettu {skipped}.")

    # 3. Tilastot
    total = conn.execute("SELECT COUNT(*) FROM datasets").fetchone()[0]
    enrichments_total = conn.execute("SELECT COUNT(*) FROM enrichments").fetchone()[0]
    print(f"\n═══ Yhteenveto ═══")
    print(f"Datasettejä yhteensä: {total}")
    print(f"Rikastuksia yhteensä: {enrichments_total}")

    conn.close()


if __name__ == "__main__":
    main()
