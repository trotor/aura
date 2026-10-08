"""Etusivun tekstit kolmella kielellä.

Etusivu on palvelun näyteikkuna, ja se tarjoillaan suomeksi (``/``),
englanniksi (``/en``) ja ruotsiksi (``/sv``). Haku- ja karttasivut ovat
toistaiseksi vain suomeksi, joten käännökset koskevat vain etusivua ja
navigaation otsikoita.

**Esimerkkien luvut ovat oikeita.** Ne on haettu julkisesta instanssista
8.10.2026 (``get_facts``, ``time_series``, ``find_data``). Jos esimerkki
vaihdetaan, luku haetaan palvelusta eikä keksitä — sivu lupaa vastauksen
lähteineen, ja keksitty luku rikkoisi juuri sen lupauksen.

Esimerkki jonka merkintä on ``pro`` toimii vain laajennetussa
instanssissa (haku aineistojen sisältä). Sivu merkitsee sen näkyvästi,
jotta avoimen version ajaja ei odota tulosta jota hänen instanssinsa ei
anna.
"""

from __future__ import annotations

from typing import Any

#: Tuetut kielet järjestyksessä: ensimmäinen on oletus (polku ``/``).
LANGUAGES: tuple[str, ...] = ("fi", "en", "sv")

#: Julkisen, laajennetun instanssin osoite. Avoin sivu kertoo siitä.
PRO_URL = "https://aura.futuai.fi"

#: Projektin lähdekoodi ja tekijän yhteystieto.
GITHUB_URL = "https://github.com/trotor/aura"
AUTHOR_NAME = "Tero Rönkkö"
AUTHOR_EMAIL = "tero@futuai.fi"


def landing_path(lang: str) -> str:
    """Kielen etusivun polku: ``/`` suomelle, muuten ``/<kieli>``."""
    return "/" if lang == LANGUAGES[0] else f"/{lang}"


TEXTS: dict[str, dict[str, Any]] = {
    "fi": {
        "lang_name": "Suomi",
        "html_lang": "fi",
        "title": "Aura – kysy Suomen avoimelta datalta",
        "description": (
            "Aura kokoaa Suomen avoimen datan yhteen hakemistoon ja vastaa "
            "kysymyksiin lähteineen. Käytä selaimella tai liitä "
            "tekoälyavustajaasi MCP:llä."
        ),
        "nav_home": "Etusivu",
        "nav_search": "Haku",
        "nav_map": "Kartta",
        "hero_title": "Kysy Suomen avoimelta datalta.",
        "hero_lede": (
            "Aura tuntee {datasets} aineistoa {sources} lähteestä ja "
            "{orgs} julkaisijalta – Tilastokeskuksesta ja THL:stä kuntien "
            "karttapalveluihin. Kysy suomeksi, ruotsiksi tai englanniksi: "
            "saat luvun, aineiston ja lähteen, josta se on haettu."
        ),
        "cta_connect": "Liitä tekoälyavustajaan",
        "cta_browse": "Selaa aineistoja",
        "ledger_title": "Kysymyksiä ja vastauksia",
        "ledger_note": "Vastaukset on haettu Aurasta 8.10.2026.",
        "pro_tag": "Aura Pro",
        "examples": [
            {
                "q": "Mikä on Kuopion työttömyysaste?",
                "a": "12,4 % vuonna 2024.",
                "more": (
                    "Vastaus kertoo myös, että TEM:n työnvälitystilasto antaa "
                    "11,1 % – eri tilasto, eri luku."
                ),
                "src": "Tilastokeskus, taulu 115x, CC BY 4.0",
            },
            {
                "q": "Paljonko Kuopio on kasvanut kymmenessä vuodessa?",
                "a": "116 921 asukkaasta 126 572:een, kasvua 8,3 %.",
                "more": "Aikasarja vuosilta 2015–2025.",
                "src": "Tilastokeskus, taulu 11ra, CC BY 4.0",
            },
            {
                "q": "Hur hög är arbetslösheten i Vasa?",
                "a": "8,8 % vuonna 2024.",
                "more": "Ruotsinkielinen kysymys, Vasa tunnistetaan Vaasaksi.",
                "src": "Tilastokeskus, taulu 115x, CC BY 4.0",
            },
            {
                "q": "Missä tilastossa ovat eläinsuojelurikoksista tuomitut?",
                "a": "Tilastokeskuksen taulussa 126q, eläintenpitokiellot.",
                "more": (
                    "Sana ei esiinny taulun otsikossa. Haku löytää sen taulun luokitusarvoista."
                ),
                "src": "Tilastokeskus, syyttäjä- ja tuomioistuintilasto",
                "pro": True,
            },
        ],
        "how_title": "Kolme askelta kysymyksestä riveihin",
        "how_intro": (
            "Tekoälyavustaja käyttää Auraa kuten tietopalvelun ammattilainen: "
            "ensin etsitään oikea aineisto, sitten selvitetään mitä siinä on, "
            "ja lopuksi haetaan rivit suoraan julkaisijan rajapinnasta."
        ),
        "how_steps": [
            (
                "find_data",
                "Etsi",
                "Hakee aineistot kaikista lähteistä. Aluerajaus ymmärtää kunnan, "
                "maakunnan, hyvinvointialueen ja postinumeron, myös taivutettuna.",
            ),
            (
                "inspect_dataset",
                "Ymmärrä",
                "Kertoo kuvauksen, kentät, lisenssin, laadun, linkkien "
                "saatavuuden ja sen, miten aineistoa kysellään.",
            ),
            (
                "query_source",
                "Hae",
                "Hakee rivit lähteestä: PxWeb, WFS, Ilmatieteen laitoksen "
                "kyselyt, OData, CSV ja JSON. Mukana kyselyn URL ja lisenssi.",
            ),
        ],
        "connect_title": "Liitä tekoälyavustajaan",
        "connect_intro": (
            "Aura puhuu Model Context Protocolia (MCP). Claude, ChatGPT, "
            "Cursor ja muut MCP-asiakkaat saavat sen käyttöön yhdellä "
            "asetuksella."
        ),
        "connect_cli": "Claude Code",
        "connect_json": "Claude Desktop, Cursor ja muut",
        "connect_note": (
            "Ei vaadi tunnuksia. Palvelu on vain luku: hakutyökalut ovat "
            "käytössä, kantaa muokkaavat eivät."
        ),
        "connect_quality": (
            "Julkaisijalle ja ylläpitäjälle: {url} – metatiedon laatu, "
            "puuttuvat kentät ja resurssien saatavuus julkaisijan omista "
            "aineistoista."
        ),
        "ai_title": "Tehty tekoälyagentin käyttöön",
        "ai_points": [
            "Jokainen vastaus on strukturoitu ja noudattaa julkaistua "
            "skeemaa (outputSchema). Agentin ei tarvitse jäsentää vapaata "
            "tekstiä.",
            "Lukujen mukana tulevat lähde, kyselyn täsmällinen URL, lisenssi "
            "ja hakuaika, joten vastauksen voi tarkistaa.",
            "Vastaus kertoo seuraavat järkevät kutsut (next_actions). "
            "Virheessä on koodi, vihje ja korjattu kutsu.",
            "Julkinen työkalupinta on pieni: viisi työkalua ja alle 1 500 "
            "merkin ohje, joten Aura ei syö agentin kontekstia.",
            "Koneluettava kuvaus palvelusta: {llms}.",
        ],
        "who_title": "Kenelle",
        "who": [
            ("Kuntalainen", "Mikä on asuntojen neliöhinta postinumeroalueellani?"),
            ("Toimittaja", "Missä kunnissa työttömyys kasvoi eniten viime vuonna?"),
            ("Tutkija", "Missä aineistossa on puuston pohjapinta-ala karttaruuduittain?"),
            ("Kunnan asiantuntija", "Miten väestörakenteemme vertautuu naapurikuntiin?"),
            ("Kehittäjä", "Mistä rajapinnasta saan junien reaaliaikaiset sijainnit?"),
            ("Datan julkaisija", "Mistä aineistoistamme puuttuu kuvaus tai lisenssi?"),
        ],
        "pro_title": "Aura Pro",
        "pro_intro_here": (
            "Tämä palvelin ajaa Auran jatkokehitettyä versiota. Avoimen "
            "version lisäksi käytössä ovat:"
        ),
        "pro_intro_elsewhere": (
            "Aurasta on jatkokehitetty versio osoitteessa {url}. Se on "
            "liitettävissä samalla tavalla, ja avoimen version lisäksi siinä "
            "ovat:"
        ),
        "pro_features": [
            (
                "Valmiit tunnusluvut",
                "Yli 200 tunnuslukua kunnille, maakunnille ja "
                "hyvinvointialueille yhdellä kutsulla: väkiluku, "
                "työttömyysaste, asuntojen hinnat, sairastavuusindeksi. "
                "Työkalut get_facts, time_series ja compare_areas.",
            ),
            (
                "Haku aineistojen sisältä",
                "Indeksissä ovat tilastotaulujen luokitusarvot, "
                "paikkatietoaineistojen sarakenimet ja koodistojen käsitteet. "
                "Siksi luomutuottajat, maalajieroosio ja kulotus löytyvät, "
                "vaikka sana ei ole yhdessäkään otsikossa.",
            ),
            (
                "Kysy millä kielellä tahansa",
                "Vektorihaku yhdistää englannin- ja ruotsinkieliset kysymykset "
                "suomenkieliseen katalogiin.",
            ),
            (
                "Rehelliset luvut",
                "Kun kaksi tilastoa mittaa samaa eri tavalla, vastaus kertoo "
                "molemmat ja eron syyn.",
            ),
        ],
        "open_title": "Avointa lähdekoodia – aja itse",
        "open_same": (
            "Aura on MIT-lisensoitu ja koodi on kokonaan julkista. Voit ajaa "
            "oman instanssin omalla koneellasi tai palvelimellasi – myös tämä "
            "sivu ja MCP-endpoint tulevat samasta repositoriosta."
        ),
        "open_extended": (
            "Aura on MIT-lisensoitu ja koodi on kokonaan julkista. Tämä "
            "palvelin on hieman erillinen kokonaisuus siitä mitä GitHubista "
            "saa{name}. Oma instanssi ajaa avointa versiota."
        ),
        "note_prefix": "Tämän palvelimen haku ulottuu myös aineistojen sisälle.",
        "open_db": (
            "Tietokanta on osa repositoriota, joten aineistot ovat mukana heti "
            "kloonauksen jälkeen – harvestointia ei tarvitse ajaa itse."
        ),
        "operator": "Tämän palvelun hostauksesta vastaa {operator}.",
        "telemetry": (
            "Palvelu tallentaa palvelun kehittämiseksi hakusanat, kysytyt "
            "alueet, aineistot ja tunnusluvut sekä työkalujen käyttömäärät "
            "päivittäin. Käyttäjää, istuntoa tai IP-osoitetta ei tallenneta."
        ),
        "own_title": "Sama tekniikka omalle datalle",
        "own_body": [
            "Aura ei ole sidottu avoimeen dataan. Sama rakenne toimii myös "
            "organisaation omille tietokannoille, rajapinnoille ja "
            "paikkatietopalveluille: keräin lähdettä kohden, yksi "
            "metatietohakemisto, suomea ymmärtävä haku ja MCP-työkalut, jotka "
            "kertovat jokaisen luvun lähteen. Silloin tekoälyavustaja löytää "
            "organisaation oman datan samalla tavalla kuin se nyt löytää "
            "Tilastokeskuksen taulun.",
            "Valmiita keräimiä on CKAN-, PxWeb-, WFS-, WMS-, ArcGIS-, OData-, "
            "OpenAPI- ja GTFS-lähteille, ja uusi lähde on yleensä yksi "
            "tiedosto. Laatuprofiili kertoo samalla, mistä aineistoista "
            "puuttuu kuvaus, lisenssi tai toimiva linkki.",
        ],
        "own_cta": (
            "Koodi, ohjeet uuden keräimen tekemiseen ja keskustelu ovat GitHubissa: {github}."
        ),
        "author_title": "Tekijä",
        "author_body": (
            "Auran on rakentanut Tero Rönkkö. Projektin on mahdollistanut "
            "Futuai Oy, joka tarjoaa julkisen palvelun ja sen ylläpidon, jotta "
            "kuka tahansa voi liittää Auran avustajaansa ilman omaa asennusta."
        ),
        "author_contact": "Yhteys: {email}. Lähdekoodi: {github}.",
        "numbers_title": "Hakemisto lukuina",
        "n_datasets": "aineistoa",
        "n_resources": "resurssia",
        "n_orgs": "julkaisijaa",
        "n_sources": "lähdettä",
        "top_orgs": "Suurimmat julkaisijat",
        "top_formats": "Yleisimmät formaatit",
        "sources_title": "Lähteet",
        "th_source": "Lähde",
        "th_count": "Aineistoja",
        "th_updated": "Päivitetty",
        "browse_all": "Selaa kaikkia aineistoja",
        "footer": "Aura – Suomen avoimen datan hakemisto",
        "report": "Raportoi ongelma",
    },
    "en": {
        "lang_name": "English",
        "html_lang": "en",
        "title": "Aura – ask Finland’s open data",
        "description": (
            "Aura indexes Finland’s open data in one catalogue and answers "
            "questions with sources. Use it in the browser or connect it to "
            "your AI assistant over MCP."
        ),
        "nav_home": "Home",
        "nav_search": "Search",
        "nav_map": "Map",
        "hero_title": "Ask Finland’s open data.",
        "hero_lede": (
            "Aura knows {datasets} datasets from {sources} sources and "
            "{orgs} publishers – from Statistics Finland and THL to "
            "municipal map services. Ask in English, Finnish or Swedish: you "
            "get the number, the dataset and the source it came from."
        ),
        "cta_connect": "Connect your AI assistant",
        "cta_browse": "Browse datasets",
        "ledger_title": "Questions and answers",
        "ledger_note": "Answers retrieved from Aura on 8 October 2026.",
        "pro_tag": "Aura Pro",
        "examples": [
            {
                "q": "What is the unemployment rate in Kuopio?",
                "a": "12.4% in 2024.",
                "more": (
                    "The answer also points out that the Ministry of Economic "
                    "Affairs’ jobseeker register gives 11.1% – a different "
                    "statistic, a different number."
                ),
                "src": "Statistics Finland, table 115x, CC BY 4.0",
            },
            {
                "q": "How much has Kuopio grown in ten years?",
                "a": "From 116,921 to 126,572 residents, up 8.3%.",
                "more": "Time series for 2015–2025.",
                "src": "Statistics Finland, table 11ra, CC BY 4.0",
            },
            {
                "q": "Hur hög är arbetslösheten i Vasa?",
                "a": "8.8% in 2024.",
                "more": "Asked in Swedish; Vasa is recognised as Vaasa.",
                "src": "Statistics Finland, table 115x, CC BY 4.0",
            },
            {
                "q": "Which statistic covers animal welfare offences?",
                "a": "Statistics Finland table 126q, animal-keeping bans.",
                "more": (
                    "The term is not in the table title. Search finds it in "
                    "the table’s classification values."
                ),
                "src": "Statistics Finland, prosecutions and sentences",
                "pro": True,
            },
        ],
        "how_title": "Three steps from question to rows",
        "how_intro": (
            "An AI assistant uses Aura the way a research librarian would: "
            "find the right dataset, learn what is in it, then fetch the rows "
            "straight from the publisher’s API."
        ),
        "how_steps": [
            (
                "find_data",
                "Find",
                "Searches every source. Region filters understand "
                "municipalities, regions, wellbeing services counties and "
                "postcodes, in Finnish and Swedish.",
            ),
            (
                "inspect_dataset",
                "Understand",
                "Returns the description, fields, licence, quality, link "
                "availability and how to query the data.",
            ),
            (
                "query_source",
                "Fetch",
                "Fetches rows from the source: PxWeb, WFS, Finnish "
                "Meteorological Institute queries, OData, CSV and JSON. The "
                "exact query URL and licence come with every answer.",
            ),
        ],
        "connect_title": "Connect your AI assistant",
        "connect_intro": (
            "Aura speaks the Model Context Protocol (MCP). Claude, ChatGPT, "
            "Cursor and other MCP clients can use it with one setting."
        ),
        "connect_cli": "Claude Code",
        "connect_json": "Claude Desktop, Cursor and others",
        "connect_note": (
            "No account needed. The service is read-only: search tools are "
            "available, tools that modify the database are not."
        ),
        "connect_quality": (
            "For publishers and maintainers: {url} – metadata quality, "
            "missing fields and resource availability for your own datasets."
        ),
        "ai_title": "Built for AI agents",
        "ai_points": [
            "Every response is structured and follows a published schema "
            "(outputSchema). The agent never has to parse free text.",
            "Numbers come with the source, the exact query URL, the licence "
            "and the retrieval time, so every answer can be checked.",
            "Responses suggest sensible next calls (next_actions). Errors "
            "carry a code, a hint and a corrected call.",
            "The public tool surface is small: five tools and instructions "
            "under 1,500 characters, so Aura does not eat the agent’s "
            "context.",
            "Machine-readable service description: {llms}.",
        ],
        "who_title": "Who uses it",
        "who": [
            ("Residents", "What do apartments cost per square metre in my postcode area?"),
            ("Journalists", "Where did unemployment rise most last year?"),
            ("Researchers", "Which dataset has forest basal area on a map grid?"),
            ("Municipal staff", "How does our population structure compare with our neighbours?"),
            ("Developers", "Which API gives live train positions?"),
            ("Data publishers", "Which of our datasets lack a description or a licence?"),
        ],
        "pro_title": "Aura Pro",
        "pro_intro_here": (
            "This server runs the extended version of Aura. On top of the open version it offers:"
        ),
        "pro_intro_elsewhere": (
            "An extended version of Aura runs at {url}. You connect it the "
            "same way, and on top of the open version it offers:"
        ),
        "pro_features": [
            (
                "Ready-made indicators",
                "More than 200 indicators for municipalities, regions and "
                "wellbeing services counties in a single call: population, "
                "unemployment rate, housing prices, morbidity index. Tools "
                "get_facts, time_series and compare_areas.",
            ),
            (
                "Search inside the data",
                "The index includes statistical classification values, "
                "column names of spatial datasets and code list concepts, so "
                "a term is found even when no title contains it.",
            ),
            (
                "Ask in any language",
                "Vector search connects English and Swedish questions to the "
                "Finnish-language catalogue.",
            ),
            (
                "Honest numbers",
                "When two statistics measure the same thing differently, the "
                "answer gives both and explains the difference.",
            ),
        ],
        "open_title": "Open source – run it yourself",
        "open_same": (
            "Aura is MIT licensed and all of its code is public. You can run "
            "your own instance on your laptop or server – this page and the "
            "MCP endpoint come from the same repository."
        ),
        "open_extended": (
            "Aura is MIT licensed and all of its code is public. This server "
            "differs somewhat from what you get on GitHub{name}. Your own "
            "instance runs the open version."
        ),
        "note_prefix": "Search on this server also reaches inside the datasets.",
        "open_db": (
            "The database is part of the repository, so the datasets are "
            "there right after cloning – no harvesting needed."
        ),
        "operator": "This service is hosted by {operator}.",
        "telemetry": (
            "To improve the service, it records search terms, requested "
            "areas, datasets and indicators, and daily tool usage counts. "
            "No user, session or IP address is stored."
        ),
        "own_title": "The same approach for your own data",
        "own_body": [
            "Aura is not tied to open data. The same structure works for an "
            "organisation’s own databases, APIs and spatial data services: a "
            "harvester per source, one metadata catalogue, search that "
            "understands Finnish, and MCP tools that cite the source of every "
            "number. An AI assistant can then find the organisation’s own "
            "data the way it now finds a Statistics Finland table.",
            "Harvesters exist for CKAN, PxWeb, WFS, WMS, ArcGIS, OData, "
            "OpenAPI and GTFS sources, and a new source is usually one file. "
            "The quality profile shows which datasets lack a description, a "
            "licence or a working link.",
        ],
        "own_cta": (
            "The code, instructions for writing a new harvester and the "
            "discussion are on GitHub: {github}."
        ),
        "author_title": "Author",
        "author_body": (
            "Aura is built by Tero Rönkkö. The project is made possible by "
            "Futuai Oy, which provides and maintains the public service so "
            "that anyone can connect Aura to their assistant without "
            "installing anything."
        ),
        "author_contact": "Contact: {email}. Source code: {github}.",
        "numbers_title": "The catalogue in numbers",
        "n_datasets": "datasets",
        "n_resources": "resources",
        "n_orgs": "publishers",
        "n_sources": "sources",
        "top_orgs": "Largest publishers",
        "top_formats": "Most common formats",
        "sources_title": "Sources",
        "th_source": "Source",
        "th_count": "Datasets",
        "th_updated": "Updated",
        "browse_all": "Browse all datasets (in Finnish)",
        "footer": "Aura – a catalogue of Finland’s open data",
        "report": "Report a problem",
    },
    "sv": {
        "lang_name": "Svenska",
        "html_lang": "sv",
        "title": "Aura – fråga Finlands öppna data",
        "description": (
            "Aura samlar Finlands öppna data i en katalog och besvarar frågor "
            "med källor. Använd den i webbläsaren eller koppla den till din "
            "AI-assistent via MCP."
        ),
        "nav_home": "Startsida",
        "nav_search": "Sök",
        "nav_map": "Karta",
        "hero_title": "Fråga Finlands öppna data.",
        "hero_lede": (
            "Aura känner till {datasets} datamängder från {sources} källor "
            "och {orgs} utgivare – från Statistikcentralen och THL till "
            "kommunernas karttjänster. Fråga på svenska, finska eller "
            "engelska: du får siffran, datamängden och källan den kommer från."
        ),
        "cta_connect": "Koppla till din AI-assistent",
        "cta_browse": "Bläddra bland datamängder",
        "ledger_title": "Frågor och svar",
        "ledger_note": "Svaren hämtades från Aura den 8 oktober 2026.",
        "pro_tag": "Aura Pro",
        "examples": [
            {
                "q": "Hur hög är arbetslösheten i Vasa?",
                "a": "8,8 % år 2024.",
                "more": "Vasa känns igen även om katalogen är på finska.",
                "src": "Statistikcentralen, tabell 115x, CC BY 4.0",
            },
            {
                "q": "Hur hög är arbetslösheten i Kuopio?",
                "a": "12,4 % år 2024.",
                "more": (
                    "Svaret påpekar också att arbets- och "
                    "näringsministeriets statistik ger 11,1 % – en annan "
                    "statistik, en annan siffra."
                ),
                "src": "Statistikcentralen, tabell 115x, CC BY 4.0",
            },
            {
                "q": "Hur mycket har Kuopio vuxit på tio år?",
                "a": "Från 116 921 till 126 572 invånare, en ökning på 8,3 %.",
                "more": "Tidsserie för 2015–2025.",
                "src": "Statistikcentralen, tabell 11ra, CC BY 4.0",
            },
            {
                "q": "Var finns statistik om djurskyddsbrott?",
                "a": "I Statistikcentralens tabell 126q om djurhållningsförbud.",
                "more": (
                    "Ordet finns inte i tabellens rubrik. Sökningen hittar det "
                    "i tabellens klassificeringsvärden."
                ),
                "src": "Statistikcentralen, åtal och domar",
                "pro": True,
            },
        ],
        "how_title": "Tre steg från fråga till rader",
        "how_intro": (
            "En AI-assistent använder Aura som en informationsspecialist: "
            "först hittas rätt datamängd, sedan reds ut vad den innehåller, "
            "och till sist hämtas raderna direkt från utgivarens gränssnitt."
        ),
        "how_steps": [
            (
                "find_data",
                "Hitta",
                "Söker i alla källor. Områdesfiltret förstår kommuner, "
                "landskap, välfärdsområden och postnummer, på finska och "
                "svenska.",
            ),
            (
                "inspect_dataset",
                "Förstå",
                "Ger beskrivning, fält, licens, kvalitet, länkarnas "
                "tillgänglighet och hur datamängden frågas.",
            ),
            (
                "query_source",
                "Hämta",
                "Hämtar rader från källan: PxWeb, WFS, Meteorologiska "
                "institutets frågor, OData, CSV och JSON. Frågans exakta URL "
                "och licens följer med.",
            ),
        ],
        "connect_title": "Koppla till din AI-assistent",
        "connect_intro": (
            "Aura talar Model Context Protocol (MCP). Claude, ChatGPT, Cursor "
            "och andra MCP-klienter kan använda den med en inställning."
        ),
        "connect_cli": "Claude Code",
        "connect_json": "Claude Desktop, Cursor och andra",
        "connect_note": (
            "Inget konto behövs. Tjänsten är skrivskyddad: sökverktygen är "
            "tillgängliga, verktyg som ändrar databasen är det inte."
        ),
        "connect_quality": (
            "För utgivare och förvaltare: {url} – metadatakvalitet, saknade "
            "fält och resursernas tillgänglighet för era egna datamängder."
        ),
        "ai_title": "Byggd för AI-agenter",
        "ai_points": [
            "Varje svar är strukturerat och följer ett publicerat schema "
            "(outputSchema). Agenten behöver aldrig tolka fritext.",
            "Siffrorna kommer med källa, frågans exakta URL, licens och "
            "hämtningstid, så att varje svar kan kontrolleras.",
            "Svaren föreslår lämpliga nästa anrop (next_actions). Fel har en "
            "kod, en ledtråd och ett korrigerat anrop.",
            "Den publika verktygsytan är liten: fem verktyg och instruktioner "
            "under 1 500 tecken, så Aura tar inte upp agentens kontext.",
            "Maskinläsbar beskrivning av tjänsten: {llms}.",
        ],
        "who_title": "Vem använder den",
        "who": [
            ("Invånare", "Vad kostar bostäder per kvadratmeter i mitt postnummerområde?"),
            ("Journalister", "Var ökade arbetslösheten mest i fjol?"),
            ("Forskare", "Vilken datamängd har skogens grundyta i rutnät?"),
            ("Kommunanställda", "Hur ser vår befolkningsstruktur ut jämfört med grannkommunerna?"),
            ("Utvecklare", "Vilket gränssnitt ger tågens positioner i realtid?"),
            ("Datautgivare", "Vilka av våra datamängder saknar beskrivning eller licens?"),
        ],
        "pro_title": "Aura Pro",
        "pro_intro_here": (
            "Den här servern kör den vidareutvecklade versionen av Aura. "
            "Utöver den öppna versionen finns:"
        ),
        "pro_intro_elsewhere": (
            "En vidareutvecklad version av Aura finns på {url}. Den kopplas "
            "på samma sätt, och utöver den öppna versionen finns:"
        ),
        "pro_features": [
            (
                "Färdiga nyckeltal",
                "Över 200 nyckeltal för kommuner, landskap och "
                "välfärdsområden med ett anrop: folkmängd, arbetslöshetsgrad, "
                "bostadspriser, sjuklighetsindex. Verktygen get_facts, "
                "time_series och compare_areas.",
            ),
            (
                "Sökning inne i datamängderna",
                "Indexet omfattar statistiktabellernas klassificeringsvärden, "
                "kolumnnamn i geodata och begrepp i kodlistor, så ett ord "
                "hittas även när ingen rubrik innehåller det.",
            ),
            (
                "Fråga på vilket språk som helst",
                "Vektorsökning kopplar engelska och svenska frågor till den "
                "finskspråkiga katalogen.",
            ),
            (
                "Ärliga siffror",
                "När två statistiker mäter samma sak på olika sätt anger "
                "svaret båda och förklarar skillnaden.",
            ),
        ],
        "open_title": "Öppen källkod – kör den själv",
        "open_same": (
            "Aura är MIT-licensierad och all kod är öppen. Du kan köra en "
            "egen instans på din dator eller server – även den här sidan och "
            "MCP-gränssnittet kommer från samma repository."
        ),
        "open_extended": (
            "Aura är MIT-licensierad och all kod är öppen. Den här servern "
            "skiljer sig något från det du får från GitHub{name}. En egen "
            "instans kör den öppna versionen."
        ),
        "note_prefix": "Sökningen på den här servern når även in i datamängderna.",
        "open_db": (
            "Databasen ingår i repositoryt, så datamängderna finns direkt "
            "efter kloning – ingen insamling behövs."
        ),
        "operator": "Tjänsten drivs av {operator}.",
        "telemetry": (
            "För att utveckla tjänsten sparas sökord, efterfrågade områden, "
            "datamängder och nyckeltal samt verktygens användning per dag. "
            "Användare, session eller IP-adress sparas inte."
        ),
        "own_title": "Samma teknik för egen data",
        "own_body": [
            "Aura är inte bunden till öppna data. Samma struktur fungerar för "
            "en organisations egna databaser, gränssnitt och geodatatjänster: "
            "en insamlare per källa, en metadatakatalog, sökning som förstår "
            "finska och MCP-verktyg som anger källan till varje siffra. Då "
            "hittar AI-assistenten organisationens egna data på samma sätt som "
            "den nu hittar en tabell från Statistikcentralen.",
            "Det finns insamlare för CKAN, PxWeb, WFS, WMS, ArcGIS, OData, "
            "OpenAPI och GTFS, och en ny källa är oftast en fil. "
            "Kvalitetsprofilen visar vilka datamängder som saknar beskrivning, "
            "licens eller fungerande länk.",
        ],
        "own_cta": (
            "Koden, instruktioner för att skriva en ny insamlare och "
            "diskussionen finns på GitHub: {github}."
        ),
        "author_title": "Upphovsperson",
        "author_body": (
            "Aura är byggd av Tero Rönkkö. Projektet möjliggörs av Futuai Oy, "
            "som tillhandahåller och underhåller den offentliga tjänsten så "
            "att vem som helst kan koppla Aura till sin assistent utan egen "
            "installation."
        ),
        "author_contact": "Kontakt: {email}. Källkod: {github}.",
        "numbers_title": "Katalogen i siffror",
        "n_datasets": "datamängder",
        "n_resources": "resurser",
        "n_orgs": "utgivare",
        "n_sources": "källor",
        "top_orgs": "Största utgivare",
        "top_formats": "Vanligaste format",
        "sources_title": "Källor",
        "th_source": "Källa",
        "th_count": "Datamängder",
        "th_updated": "Uppdaterad",
        "browse_all": "Bläddra bland alla datamängder (på finska)",
        "footer": "Aura – en katalog över Finlands öppna data",
        "report": "Rapportera ett problem",
    },
}


def format_number(value: int, lang: str) -> str:
    """Tuhaterotin kielen tavalla: fi/sv välilyönti, en pilkku."""
    text = f"{value:,}"
    return text if lang == "en" else text.replace(",", " ")
