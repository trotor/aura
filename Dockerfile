# Aura remote MCP -server (read-only, streamable HTTP) — App Runner -kontti.
# Vain ajonaikaiset riippuvuudet + data/aura.db (ei boundaries-gpkg:itä).
FROM python:3.11-slim

# Ei .pyc-tiedostoja, stdout/err puskuroimatta (lokit CloudWatchiin reaaliajassa)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 1) Asenna riippuvuudet (cacheystävällinen: vain metadata ensin).
#    Editable-asennus pitää src/auran import-paikkana, jolloin
#    DEFAULT_DB_PATH (= __file__/../../../data/aura.db) osoittaa /app/data/aura.db.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install -e .

# 2) Kopioi tietokanta (ajonaikainen riippuvuus). Boundaries jätetään pois.
#    Tämä on oletus. Ohita AURA_DB-ympäristömuuttujalla kun kanta tulee
#    volumesta eikä imagesta — esim. johdettu pro-kanta:
#      docker run -v aura-data:/data -e AURA_DB=/data/aura-pro.db ...
COPY data/aura.db ./data/aura.db

# 3) Read-only remote on oletus tälle imagelle.
ENV AURA_READONLY=1

# 4) Aja non-root-käyttäjänä.
RUN useradd --create-home --uid 10001 app && chown -R app:app /app
USER app

EXPOSE 8000
CMD ["aura", "serve", "--http", "--host", "0.0.0.0", "--port", "8000"]
