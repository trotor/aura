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

# 4) Read-only remote on oletus tälle imagelle.
ENV AURA_READONLY=1

USER app

EXPOSE 8000
CMD ["aura", "serve", "--http", "--host", "0.0.0.0", "--port", "8000"]
