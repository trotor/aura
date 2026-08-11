# Aura remote MCP -server (read-only, streamable HTTP).
# Vain ajonaikaiset riippuvuudet + data/aura.db (ei boundaries-gpkg:itä).
FROM python:3.11-slim

# Ei .pyc-tiedostoja, stdout/err puskuroimatta (lokit reaaliajassa)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 1) Käyttäjä ENSIN, ja omistajuus asetetaan kopioitaessa.
#
#    Aiemmin tämä oli viimeisenä muodossa
#        RUN useradd ... && chown -R app:app /app
#    joka kirjoitti /app:n koko sisällön uudelleen omaan kerrokseensa:
#    mitattuna 149 MB per image, eli täysi duplikaatti kannasta ja
#    riippuvuuksista. COPY --chown tekee saman ilman lisäkerrosta.
RUN useradd --create-home --uid 10001 app
WORKDIR /app

# 2) Asenna riippuvuudet.
#    Editable-asennus pitää src/auran import-paikkana, jolloin
#    DEFAULT_DB_PATH (= __file__/../../../data/aura.db) osoittaa
#    /app/data/aura.db. Ohitettavissa AURA_DB-muuttujalla.
COPY --chown=app:app pyproject.toml README.md ./
COPY --chown=app:app src ./src
RUN pip install -e . && chown -R app:app /app/src.egg-info 2>/dev/null || true

# 3) Kopioi tietokanta viimeisenä: se on suurin ja useimmin muuttuva
#    kerros, joten sitä ennen olevat kerrokset pysyvät välimuistissa.
#      docker run -v aura-data:/data -e AURA_DB=/data/aura.db ...
COPY --chown=app:app data/aura.db ./data/aura.db

# 3b) Pois WAL-tilasta. Repon kanta on WAL, mikä on oikein kehityksessä missä
#     harvestointi kirjoittaa. Tarjoiltava kanta on eri tapaus:
#
#     - Kirjoittajaa ei ole (AURA_READONLY=1), joten WAL:sta ei ole hyötyä.
#     - WAL-kanta ei aukea edes lukutilassa tiedostojärjestelmästä johon ei
#       voi kirjoittaa, ellei -shm ole valmiina. Read-only-rootfs tai
#       :ro-mount kaataisi käynnistyksen virheeseen "unable to open
#       database file".
#     - WAL-tilassa SQLite luo -shm- ja -wal-tiedostot kontin
#       kirjoituskerrokseen. Mitattuna niitä syntyi kaksi.
RUN python -c "import sqlite3; c=sqlite3.connect('/app/data/aura.db', isolation_level=None); \
    c.execute('PRAGMA wal_checkpoint(TRUNCATE)'); \
    m=c.execute('PRAGMA journal_mode=DELETE').fetchone()[0]; \
    c.close(); \
    exit(0 if m=='delete' else 1)" \
    && rm -f /app/data/aura.db-wal /app/data/aura.db-shm

# 4) Read-only remote on oletus tälle imagelle.
ENV AURA_READONLY=1

USER app

EXPOSE 8000
CMD ["aura", "serve", "--http", "--host", "0.0.0.0", "--port", "8000"]
