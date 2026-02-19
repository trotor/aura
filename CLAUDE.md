# Aura — Kehitysohjeet

## Python ja virtuaaliympäristö

**Käytä AINA virtuaaliympäristöä (venv) kaikkiin Python-operaatioihin.**

```bash
# Aktivoi venv ennen mitä tahansa Python-komentoa
source .venv/bin/activate

# Asenna riippuvuudet venviin
pip install -e ".[dev]"

# Aja skriptit aina venvin kautta
python -m aura.cli harvest
pytest tests/
```

Älä koskaan asenna paketteja globaalisti. Venv-hakemisto `.venv/` on .gitignorettu.

## Projektikäytännöt

- Kieli: Python 3.11+
- Tietokanta: SQLite (data/aura.db) — osa git-repoa
- MCP-server: FastMCP
- Testit: pytest
- Lintteri: ruff
- Tyypintarkistus: mypy (strict)

## Harvesterit

Uudet harvesterit luodaan `src/aura/harvesters/`-kansioon ja rekisteröidään `__init__.py`:n `HARVESTERS`-dictiin. Jokainen harvester perii `BaseHarvester`-luokan.

## Commit-käytännöt

Conventional Commits: `feat:`, `fix:`, `data:`, `docs:`, `refactor:`, `test:`, `chore:`, `release:`
