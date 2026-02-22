"""Postinumerotiedot Postin PCF-tiedostosta."""

from __future__ import annotations

import logging
import re

import httpx

from aura.populators.base import BasePopulator

logger = logging.getLogger(__name__)

UNZIP_DIR_URL = "https://www.posti.fi/webpcode/unzip/"

# Postin PCF-tiedoston fixed-width -kenttien regex
# Lähde: https://github.com/theikkila/postinumerot
PCF_PATTERN = re.compile(
    r"^PONOT.{8}"  # tunnus + päivämäärä
    r"(?P<code>.{5})"
    r"(?P<name_fi>.{30})"
    r"(?P<name_sv>.{30})"
    r".{12}.{12}"  # lyhenteet fi/sv
    r".{8}"  # voimaantulopäivä
    r".{1}"  # tyyppikoodi
    r".{5}"  # hallinnollinen aluekoodi
    r".{30}.{30}"  # hallinnollinen alue fi/sv
    r"(?P<muni_code>.{3})"
)


class PostalCodePopulator(BasePopulator):
    """Populoi postinumerotiedot Postin PCF-tiedostosta."""

    name = "postal_codes"
    description = "Suomen postinumerot ja postitoimipaikat (Posti PCF)"
    source_url = "https://www.posti.fi/webpcode/"

    async def populate(self) -> int:
        """Hae PCF-tiedosto ja tallenna ref_postal_codes-tauluun."""
        async with self._make_client(timeout=30.0) as client:
            # 1. Etsi uusin PCF-tiedosto hakemistolistauksesta
            dat_url = await self._find_latest_pcf_url(client)
            logger.info("[%s] Ladataan %s", self.name, dat_url)

            # 2. Lataa tiedosto
            resp = await self._fetch(client, dat_url)
            content = resp.content.decode("latin-1")

        # 3. Parsii ja tallenna
        count = 0
        for line in content.splitlines():
            m = PCF_PATTERN.match(line)
            if not m:
                continue

            code = m.group("code").strip()
            name_fi = _titlecase(m.group("name_fi").strip())
            name_sv = _titlecase(m.group("name_sv").strip())
            muni_code = m.group("muni_code").strip()

            if not code:
                continue

            self.conn.execute(
                """
                INSERT INTO ref_postal_codes (code, name_fi, name_sv, municipality_code, updated_at)
                VALUES (?, ?, ?, ?, datetime('now'))
                ON CONFLICT(code) DO UPDATE SET
                    name_fi = excluded.name_fi,
                    name_sv = excluded.name_sv,
                    municipality_code = excluded.municipality_code,
                    updated_at = excluded.updated_at
                """,
                (code, name_fi, name_sv, muni_code or None),
            )
            count += 1

        self.conn.commit()

        # Hae versio tiedostonimestä
        version_match = re.search(r"PCF_(\d{8})", dat_url)
        version = version_match.group(1) if version_match else ""

        self._update_metadata(count, version=version)
        logger.info("[%s] Tallennettu %d postinumeroa", self.name, count)
        return count

    async def _find_latest_pcf_url(
        self, client: httpx.AsyncClient,
    ) -> str:
        """Hae uusin PCF .dat -tiedoston URL hakemistolistauksesta."""
        resp = await self._fetch(client, UNZIP_DIR_URL)
        html = resp.text

        files: list[str] = re.findall(r"PCF_\d{8}\.dat", html)
        if not files:
            msg = "PCF-tiedostoa ei löytynyt hakemistosta"
            raise RuntimeError(msg)

        files.sort()
        return UNZIP_DIR_URL + files[-1]


def _titlecase(name: str) -> str:
    """Muunna ISOLLA KIRJOITETTU nimi Title Case -muotoon.

    Postin tiedostossa nimet ovat ISOILLA KIRJAIMILLA (esim. "HELSINKI").
    Muunnetaan muotoon "Helsinki".

    Erikoistapaukset kuten yhdysmerkit käsitellään:
    "KAUNIAINEN" → "Kauniainen", "PEDERSÖRE" → "Pedersöre"
    """
    if not name:
        return name

    parts: list[str] = []
    for part in name.split("-"):
        parts.append(part.capitalize())

    return "-".join(parts)
