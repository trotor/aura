"""Mittaa paikkatietoaineistojen koot otoskyselyillä.

Käyttö:
    python scripts/probe_spatial_sizes.py [--source metsakeskus|gtk|all]
                                          [--update-db] [--timeout 180]
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aura.spatial_probe import (
    DEFAULT_TIMEOUT,
    format_probe_report,
    probe_all,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mittaa paikkatietoaineistojen koot otoskyselyillä",
    )
    parser.add_argument(
        "--source",
        choices=["metsakeskus", "gtk", "all"],
        default="all",
        help="Mittauskohde (oletus: all)",
    )
    parser.add_argument(
        "--update-db",
        action="store_true",
        help="Päivitä estimated_size_bytes tietokantaan",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"HTTP-timeout sekunteina (oletus: {DEFAULT_TIMEOUT})",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    results = asyncio.run(probe_all(source=args.source, timeout=args.timeout))

    print()
    print(format_probe_report(results))
    print()

    if args.update_db:
        from aura.database import get_connection, init_db

        conn = get_connection()
        init_db(conn)
        updated = 0
        for r in results:
            if r.extrapolated_size_bytes > 0:
                conn.execute(
                    "UPDATE datasets SET estimated_size_bytes = ? WHERE id = ?",
                    (r.extrapolated_size_bytes, r.dataset_id),
                )
                updated += 1
        conn.commit()
        print(f"Päivitetty {updated} datasetin kokoarvio tietokantaan.")


if __name__ == "__main__":
    main()
