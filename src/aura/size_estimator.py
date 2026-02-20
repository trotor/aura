"""Datakoon arviointi resursseista ja formaateista."""

from __future__ import annotations

# Keskimääräiset koot formaateittain (tavuina) perustuen avoindata.fi:n arkistoijatietoihin.
# Nämä ovat konservatiivisia arvioita tapauksille joissa tarkka koko ei ole tiedossa.
FORMAT_SIZE_ESTIMATES: dict[str, int] = {
    # Rajapinnat (streamaava data, arvioidaan pyynnön koko)
    "WMS": 50_000_000,       # 50 MB — karttapalvelu, paljon dataa taustalla
    "WFS": 100_000_000,      # 100 MB — vektoridata
    "WMTS": 500_000_000,     # 500 MB — karttatiilipalvelu
    "OGC API": 100_000_000,  # 100 MB
    "API": 10_000_000,       # 10 MB — REST-rajapinta
    "PXWEB": 5_000_000,      # 5 MB — tilastotaulu
    # Tiedostot
    "CSV": 5_000_000,        # 5 MB
    "XLSX": 2_000_000,       # 2 MB
    "XLS": 2_000_000,        # 2 MB
    "XLSM": 3_000_000,       # 3 MB
    "JSON": 3_000_000,       # 3 MB
    "XML": 5_000_000,        # 5 MB
    "PDF": 3_000_000,        # 3 MB
    "HTML": 500_000,         # 500 KB
    "ZIP": 50_000_000,       # 50 MB
    "SHP": 20_000_000,       # 20 MB
    "TIFF": 100_000_000,     # 100 MB — usein GeoTIFF
    "GeoTIFF": 200_000_000,  # 200 MB
    "KML": 5_000_000,        # 5 MB
    "GML": 10_000_000,       # 10 MB
    "KUNTAGML": 20_000_000,  # 20 MB
    "TAB": 5_000_000,        # 5 MB — MapInfo
    "GPKG": 50_000_000,      # 50 MB — GeoPackage
    "TMS": 5_000_000_000,    # 5 GB — karttatiilipalvelu (koko tileset)
    "GeoParquet": 500_000_000,  # 500 MB — GeoParquet-aineisto
    "PPTX": 5_000_000,       # 5 MB
    "DOC": 1_000_000,        # 1 MB
    "DOCX": 1_000_000,       # 1 MB
    "TXT": 500_000,          # 500 KB
    "VIDEO/QUICKTIME": 100_000_000,  # 100 MB
}

DEFAULT_SIZE_ESTIMATE = 1_000_000  # 1 MB oletus tuntemattomille


def parse_file_size(size_str: str) -> int:
    """Parsii tiedostokoon merkkijonosta tavuiksi.

    Tukee muotoja: "1024", "1024 bytes", "5 MB", "2.3 GB" jne.
    """
    if not size_str:
        return 0

    size_str = size_str.strip().upper()

    # Pelkkä numero = tavuja
    try:
        return int(float(size_str))
    except ValueError:
        pass

    multipliers = {
        "B": 1,
        "KB": 1024,
        "MB": 1024 * 1024,
        "GB": 1024 * 1024 * 1024,
        "TB": 1024 * 1024 * 1024 * 1024,
        "BYTES": 1,
    }

    for suffix, mult in multipliers.items():
        if size_str.endswith(suffix):
            num_str = size_str[: -len(suffix)].strip()
            try:
                return int(float(num_str) * mult)
            except ValueError:
                pass

    return 0


def estimate_dataset_size(resources: list[dict[str, str]]) -> int:
    """Arvioi datasetin kokonaiskoko resurssien perusteella.

    Käyttää ensisijaisesti resurssien ilmoitettua kokoa (file_size),
    toissijaisesti formaattipohjaista arviota.
    """
    total = 0
    for r in resources:
        # Yritä ensin tarkka koko
        size = parse_file_size(r.get("file_size", ""))
        if size > 0:
            total += size
            continue

        # Formaattipohjainen arvio
        fmt = (r.get("format", "") or "").upper()
        total += FORMAT_SIZE_ESTIMATES.get(fmt, DEFAULT_SIZE_ESTIMATE)

    return total


def format_size(size_bytes: int) -> str:
    """Muotoile tavut ihmisluettavaan muotoon."""
    if size_bytes == 0:
        return "–"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.0f} KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    if size_bytes < 1024 * 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
    return f"{size_bytes / (1024 * 1024 * 1024 * 1024):.1f} TB"
