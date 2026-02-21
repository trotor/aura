#!/usr/bin/env bash
# Lataa rajausaineistot MML:n Kapsi.fi-peililtä.
# Ei vaadi API-avainta. Ajetaan kerran projektin kloonauksen jälkeen.
#
# Käyttö:
#   bash scripts/download_boundaries.sh
#
# Lähde: https://kartat.kapsi.fi/files/ (MML:n avoin data, CC BY 4.0)

set -euo pipefail

DEST="$(cd "$(dirname "$0")/.." && pwd)/data/boundaries"
TMP="${TMPDIR:-/tmp}/aura_boundaries"

mkdir -p "$DEST" "$TMP"

echo "Rajausaineistojen lataus -> $DEST"
echo

# --- Karttalehtijako (TM35) ---
if [ -f "$DEST/karttalehtijako.gpkg" ]; then
    echo "[OK] karttalehtijako.gpkg löytyy jo"
else
    echo "[1/3] Ladataan karttalehtijako (17 MB)..."
    curl -fSL -o "$TMP/karttalehtijako.zip" \
        "https://kartat.kapsi.fi/files/karttalehtijako_ruudukko/kaikki/etrs89/gpkg/TM35_karttalehtijako_GeoPackage.zip"
    unzip -qo "$TMP/karttalehtijako.zip" -d "$TMP/"
    mv "$TMP/TM35_karttalehtijako.gpkg" "$DEST/karttalehtijako.gpkg"
    echo "     -> karttalehtijako.gpkg ($(du -h "$DEST/karttalehtijako.gpkg" | cut -f1))"
fi

# --- Kuntajako 1:1M (yleiskäyttö) ---
if [ -f "$DEST/kuntajako_1000k.gpkg" ]; then
    echo "[OK] kuntajako_1000k.gpkg löytyy jo"
else
    echo "[2/3] Ladataan kuntajako 1:1M (549 KB)..."
    curl -fSL -o "$TMP/kuntajako_1000k.zip" \
        "https://kartat.kapsi.fi/files/kuntajako/kuntajako_1000k/etrs89/gpkg/TietoaKuntajaosta_2026_1000k.zip"
    unzip -qo "$TMP/kuntajako_1000k.zip" -d "$TMP/"
    mv "$TMP"/SuomenHallinnollisetKuntajakopohjaisetAluejaot_*_1000k.gpkg "$DEST/kuntajako_1000k.gpkg"
    echo "     -> kuntajako_1000k.gpkg ($(du -h "$DEST/kuntajako_1000k.gpkg" | cut -f1))"
fi

# --- Kuntajako 1:10k (tarkka) ---
if [ -f "$DEST/kuntajako_10k.gpkg" ]; then
    echo "[OK] kuntajako_10k.gpkg löytyy jo"
else
    echo "[3/3] Ladataan kuntajako 1:10k (23 MB)..."
    curl -fSL -o "$TMP/kuntajako_10k.zip" \
        "https://kartat.kapsi.fi/files/kuntajako/kuntajako_10k/etrs89/gpkg/TietoaKuntajaosta_2026_10k.zip"
    unzip -qo "$TMP/kuntajako_10k.zip" -d "$TMP/"
    mv "$TMP"/SuomenHallinnollisetKuntajakopohjaisetAluejaot_*_10k.gpkg "$DEST/kuntajako_10k.gpkg"
    echo "     -> kuntajako_10k.gpkg ($(du -h "$DEST/kuntajako_10k.gpkg" | cut -f1))"
fi

# Siivoa
rm -rf "$TMP"

echo
echo "Valmis! Rajausaineistot:"
ls -lh "$DEST"/*.gpkg
