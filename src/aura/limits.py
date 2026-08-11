"""Työkaluparametrien katot julkiselle rajapinnalle.

MCP-endpoint on autentikoimaton: kutsujaa ei voi tunnistaa, joten
väärinkäyttöä ei voi rajata tekijäkohtaisesti. Ainoa jäljellä oleva keino on
rajata jokainen määrää kasvattava parametri.

``query_data`` oli rajattu alusta asti (``_MAX_RESULT_ROWS``,
``_MAX_DOWNLOAD_BYTES``, aikakatko), mutta hakupinnalla ei ollut kattoa
lainkaan: ``search(limit=1000000)`` olisi rakentanut vastauksen kaikista
osumista.

**Katot on kirjattu myös työkalujen kuvauksiin**, jotta kutsuva agentti tietää
ne ennen kutsua eikä yritä ohittaa niitä. ``tests/test_limits.py`` varmistaa
ettei kuvaus ja toteutus pääse eriytymään.
"""

from __future__ import annotations

#: Suurin sallittu tulosmäärä hakutyökaluille.
#:
#: 100 riittää selaamiseen ja on turvallinen vastauksen kokona: yksi
#: hakutulos on muutama sata tavua, joten katto pitää vastauksen alle
#: satojen kilotavujen.
MAX_SEARCH_LIMIT = 100

#: Suurin sallittu tulosmäärä listaus- ja raporttityökaluille
#: (organisaatiot, formaatit, laatuvertailut, saatavuustarkistukset).
MAX_LIST_LIMIT = 200

#: Suurin sallittu määrä datasettejä yhteen vertailuun.
MAX_COMPARE_DATASETS = 5


def clamp(value: int, maximum: int, *, minimum: int = 1) -> int:
    """Rajaa arvo sallittuun väliin.

    Liian suuri arvo **leikataan** eikä nosteta virhettä: agentti saa silti
    hyödyllisen vastauksen, ja kuvauksessa kerrottu katto selittää tuloksen.
    Negatiivinen tai nolla nostetaan minimiin, koska SQLite tulkitsee
    negatiivisen LIMITin rajattomaksi.
    """
    if value < minimum:
        return minimum
    return min(value, maximum)
