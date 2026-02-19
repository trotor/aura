"""Auran komentorivityökalu."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from aura import __version__


def main() -> None:
    """Auran CLI-päätoiminto."""
    parser = argparse.ArgumentParser(
        prog="aura",
        description="Aura — Suomalaisen avoimen datan discovery-palvelu",
    )
    parser.add_argument("--version", action="version", version=f"aura {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    # harvest
    harvest_parser = subparsers.add_parser("harvest", help="Hae datasettien metatiedot")

    # serve
    serve_parser = subparsers.add_parser("serve", help="Käynnistä MCP-server")

    # search
    search_parser = subparsers.add_parser("search", help="Hae datasettejä")
    search_parser.add_argument("query", help="Hakusanat")
    search_parser.add_argument("--limit", type=int, default=10)

    # stats
    subparsers.add_parser("stats", help="Näytä tilastot")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    if args.command == "harvest":
        from aura.harvester import harvest_all

        count = asyncio.run(harvest_all())
        print(f"Haettu {count} datasettiä.")

    elif args.command == "serve":
        from aura.server import mcp

        mcp.run()

    elif args.command == "search":
        from aura.database import get_connection, init_db, search_datasets
        from aura.search import format_dataset_summary

        conn = get_connection()
        init_db(conn)
        results = search_datasets(conn, args.query, limit=args.limit)
        if not results:
            print(f"Ei tuloksia haulle '{args.query}'.")
            sys.exit(0)
        for dataset in results:
            print(format_dataset_summary(dataset))
            print("---")

    elif args.command == "stats":
        from aura.database import get_connection, get_stats, init_db
        from aura.search import format_stats

        conn = get_connection()
        init_db(conn)
        print(format_stats(get_stats(conn)))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
