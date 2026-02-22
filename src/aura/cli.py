"""Auran komentorivityökalu."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import UTC

from aura import __version__
from aura.constants import format_date


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
    harvest_parser.add_argument(
        "source",
        nargs="?",
        default="all",
        help="Lähde tai 'all' kaikille (oletus: all)",
    )
    harvest_parser.add_argument(
        "--list", action="store_true", dest="list_sources",
        help="Listaa saatavilla olevat lähteet",
    )
    harvest_parser.add_argument(
        "--include-static", action="store_true",
        help="Sisällytä staattiset harvesterit (oletuksena ohitetaan)",
    )

    # serve
    subparsers.add_parser("serve", help="Käynnistä MCP-server")

    # search
    search_parser = subparsers.add_parser("search", help="Hae datasettejä")
    search_parser.add_argument("query", help="Hakusanat")
    search_parser.add_argument("--limit", type=int, default=10)

    # stats
    subparsers.add_parser("stats", help="Näytä tilastot")

    # sources
    subparsers.add_parser("sources", help="Listaa datalähteet ja niiden tila")

    # probe-sizes
    probe_parser = subparsers.add_parser(
        "probe-sizes", help="Mittaa paikkatietoaineistojen koot otoskyselyillä"
    )
    probe_parser.add_argument(
        "--source",
        choices=["metsakeskus", "gtk", "all"],
        default="all",
        help="Mittauskohde (oletus: all)",
    )
    probe_parser.add_argument(
        "--update-db",
        action="store_true",
        help="Päivitä estimated_size_bytes tietokantaan",
    )
    probe_parser.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="HTTP-timeout sekunteina (oletus: 180)",
    )

    # export-enrichments
    export_parser = subparsers.add_parser(
        "export-enrichments", help="Vie rikastukset JSON-tiedostoon"
    )
    export_parser.add_argument(
        "--output", "-o", default="enrichments.json",
        help="Tulostiedoston polku (oletus: enrichments.json)",
    )
    export_parser.add_argument(
        "--source-type",
        default="",
        help="Suodata lähdetyypin mukaan (esim. mcp_session)",
    )

    # import-enrichments
    import_parser = subparsers.add_parser(
        "import-enrichments", help="Tuo rikastukset JSON-tiedostosta"
    )
    import_parser.add_argument(
        "files", nargs="+", help="JSON-tiedostot"
    )

    # prune-enrichments
    prune_parser = subparsers.add_parser(
        "prune-enrichments", help="Poista vanhat rikastukset"
    )
    prune_parser.add_argument(
        "--older-than",
        type=int,
        default=365,
        help="Poista rikastukset vanhempia kuin N päivää (oletus: 365)",
    )

    # health
    health_parser = subparsers.add_parser(
        "health", help="Tarkista resurssien saatavuus"
    )
    health_parser.add_argument(
        "--source", default="",
        help="Rajaa lähteeseen (esim. avoindata.fi)",
    )
    health_parser.add_argument(
        "--stale-days", type=int, default=7,
        help="Tarkista uudelleen N päivän jälkeen (oletus: 7)",
    )
    health_parser.add_argument(
        "--limit", type=int, default=100,
        help="Tarkistettavien resurssien enimmäismäärä (oletus: 100)",
    )

    # quality
    quality_parser = subparsers.add_parser("quality", help="Laske datasettien laatupisteet")
    quality_parser.add_argument(
        "--source", default="",
        help="Rajaa lähteeseen (esim. avoindata.fi)",
    )
    quality_parser.add_argument(
        "--gaps", action="store_true",
        help="Näytä metatiedon puuteanalyysi",
    )

    # populate
    populate_parser = subparsers.add_parser(
        "populate", help="Lataa viiteaineistot (kunnat, postinumerot ym.)"
    )
    populate_parser.add_argument(
        "name", nargs="?", default="all",
        help="Populaattorin nimi tai 'all' kaikille (oletus: all)",
    )
    populate_parser.add_argument(
        "--list", action="store_true", dest="list_populators",
        help="Listaa saatavilla olevat populaattorit",
    )
    populate_parser.add_argument(
        "--status", action="store_true",
        help="Näytä populaattoreiden tila",
    )
    populate_parser.add_argument(
        "--force", action="store_true",
        help="Pakota uudelleenlataus vaikka data on tuore",
    )

    # migrate
    subparsers.add_parser("migrate", help="Aja tietokantamigraatiot")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    if args.command == "harvest":
        from aura.harvesters import get_all_harvesters, get_harvester
        from aura.harvesters.static import StaticHarvester

        if args.list_sources:
            for name, cls in get_all_harvesters().items():
                tag = " (staattinen)" if issubclass(cls, StaticHarvester) else ""
                print(f"  {name:25s} {cls.description}{tag}")
            return

        if args.source == "all":
            total = 0
            skipped = []
            for name, cls in get_all_harvesters().items():
                if issubclass(cls, StaticHarvester) and not args.include_static:
                    skipped.append(name)
                    continue
                print(f"Harvestoidaan: {name}...")
                harvester = cls()
                count = asyncio.run(harvester.harvest())
                print(f"  {name}: {count} datasettiä")
                total += count
            if skipped:
                print(f"\nOhitettu staattiset: {', '.join(skipped)}")
                print("  (käytä --include-static sisällyttääksesi)")
            print(f"\nYhteensä: {total} datasettiä")
        else:
            cls = get_harvester(args.source)
            harvester = cls()
            count = asyncio.run(harvester.harvest())
            print(f"Haettu {count} datasettiä lähteestä {args.source}.")

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

    elif args.command == "sources":
        from aura.database import get_connection, init_db
        from aura.harvesters import get_all_harvesters

        conn = get_connection()
        init_db(conn)

        from datetime import datetime

        print("Datalähteet:\n")
        now = datetime.now(tz=UTC)
        for name, cls in get_all_harvesters().items():
            row = conn.execute(
                """
                SELECT COUNT(*) as count, MAX(harvested_at) as last_harvest
                FROM datasets WHERE source = ?
                """,
                (name,),
            ).fetchone()
            count = row["count"] if row else 0
            last_harvest = row["last_harvest"] if row else None

            status = f"{count} datasettiä"
            warning = ""
            if last_harvest:
                harvest_dt = datetime.fromisoformat(last_harvest)
                days_old = (now - harvest_dt.replace(tzinfo=UTC)).days
                status += f" (viimeksi: {format_date(last_harvest, include_time=True)})"
                if days_old > 7:
                    warning = f" ⚠ {days_old} pv vanha"
            elif count == 0:
                status = "ei harvestoitu"

            print(f"  {name:25s} [{status}]{warning}")

    elif args.command == "probe-sizes":
        from aura.spatial_probe import format_probe_report, probe_all

        probe_results = asyncio.run(
            probe_all(source=args.source, timeout=args.timeout)
        )
        print()
        print(format_probe_report(probe_results))
        print()

        if args.update_db:
            from aura.database import get_connection, init_db

            conn = get_connection()
            init_db(conn)
            updated = 0
            for pr in probe_results:
                if pr.extrapolated_size_bytes > 0:
                    conn.execute(
                        "UPDATE datasets SET estimated_size_bytes = ? WHERE id = ?",
                        (pr.extrapolated_size_bytes, pr.dataset_id),
                    )
                    updated += 1
            conn.commit()
            print(f"Päivitetty {updated} datasetin kokoarvio tietokantaan.")

    elif args.command == "export-enrichments":
        import json

        from aura.database import (
            export_enrichments,
            get_connection,
            init_db,
        )

        conn = get_connection()
        init_db(conn)
        enrichments = export_enrichments(
            conn, source_type=args.source_type
        )
        if not enrichments:
            print("Ei rikastuksia vietäväksi.")
            sys.exit(0)

        output = {
            "version": "1.0",
            "enrichments": enrichments,
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(
            f"Viety {len(enrichments)} rikastusta "
            f"tiedostoon {args.output}."
        )

    elif args.command == "import-enrichments":
        import json

        from aura.database import (
            get_connection,
            import_enrichments,
            init_db,
        )

        conn = get_connection()
        init_db(conn)
        total_imported = 0
        for filepath in args.files:
            try:
                with open(filepath, encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                print(f"Virhe luettaessa {filepath}: {e}")
                continue

            enrichments = data.get("enrichments", [])
            count = import_enrichments(conn, enrichments)
            print(f"  {filepath}: {count} uutta rikastusta")
            total_imported += count

        print(f"\nTuotu yhteensä {total_imported} rikastusta.")

    elif args.command == "prune-enrichments":
        from aura.database import (
            get_connection,
            init_db,
            prune_enrichments,
        )

        conn = get_connection()
        init_db(conn)
        count = prune_enrichments(conn, older_than_days=args.older_than)
        if count > 0:
            print(f"Poistettu {count} rikastusta (vanhempia kuin {args.older_than} pv).")
        else:
            print("Ei poistettavia rikastuksia.")

    elif args.command == "health":
        from aura.database import get_connection, init_db
        from aura.health import check_all_resources

        conn = get_connection()
        init_db(conn)

        print(f"Tarkistetaan resurssien saatavuus (max {args.limit})...")
        summary = asyncio.run(check_all_resources(
            conn,
            source=args.source,
            stale_days=args.stale_days,
            limit=args.limit,
        ))

        print("\nTulokset:")
        print(f"  Tarkistettu:   {summary.total}")
        print(f"  Saatavilla:    {summary.available}")
        print(f"  Ei saatavilla: {summary.unavailable}")
        print(f"  Virheitä:      {summary.errors}")
        if summary.total > 0:
            print(f"  Saatavuus:     {summary.availability_pct:.1f}%")
        if summary.avg_response_ms > 0:
            print(f"  Vasteaika ka:  {summary.avg_response_ms:.0f} ms")

        # Näytä ei-saatavilla olevat
        broken = [r for r in summary.results if not r.is_available]
        if broken:
            print(f"\nEi saatavilla ({len(broken)}):")
            for r in broken[:20]:
                err = r.error_message or f"HTTP {r.status_code}"
                print(f"  {err:20s} {r.url[:80]}")

    elif args.command == "quality":
        from aura.database import get_connection, init_db

        conn = get_connection()
        init_db(conn)

        if args.gaps:
            from aura.quality import analyze_metadata_gaps, suggest_improvements

            report = analyze_metadata_gaps(conn, source=args.source)
            sources = report.get("sources", [])

            print("Metatiedon puutteet lähteittäin:\n")
            print(f"  {'Lähde':25s} {'Yht':>5s} {'Kuvaus':>8s} "
                  f"{'Avains':>8s} {'Päiv.':>8s} {'Lis.':>8s} {'Täyd.':>6s}")
            print("  " + "-" * 70)
            for s in sources:
                t = s["total"]
                print(
                    f"  {s['source']:25s} {t:5d} "
                    f"{s['missing_desc']:5d}{_gap_pct(s['missing_desc'], t)} "
                    f"{s['missing_keywords']:5d}{_gap_pct(s['missing_keywords'], t)} "
                    f"{s['missing_freq']:5d}{_gap_pct(s['missing_freq'], t)} "
                    f"{s['missing_license']:5d}{_gap_pct(s['missing_license'], t)} "
                    f"{s.get('completeness_pct', 0):5.0f}%"
                )

            totals = report.get("totals", {})
            print(f"\n  Kokonaismetatiedon täydellisyys: "
                  f"{totals.get('completeness_pct', 0):.0f}%")

            suggestions = suggest_improvements(
                conn, source=args.source, limit=10,
            )
            if suggestions:
                print(f"\nHelpoimmin parannettavat ({len(suggestions)} kpl):")
                for i, s in enumerate(suggestions, 1):
                    title = s["title"] or s["name"]
                    if len(title) > 50:
                        title = title[:47] + "..."
                    missing = ", ".join(s["missing_fields"])
                    print(f"  {i:2d}. {title}")
                    print(f"      Puuttuu: {missing}")

            return

        from aura.quality import score_all_datasets

        count = score_all_datasets(conn, source=args.source)
        print(f"Laatupisteet laskettu {count} datasetille.")

        # Yhteenveto
        rows = conn.execute(
            """
            SELECT
                ROUND(AVG(score), 1) as avg_score,
                ROUND(MIN(score), 1) as min_score,
                ROUND(MAX(score), 1) as max_score
            FROM quality_scores
            WHERE dimension = 'overall'
            """
        ).fetchone()
        if rows and rows["avg_score"] is not None:
            print(
                f"Kokonaislaatu: ka. {rows['avg_score']}, "
                f"min {rows['min_score']}, max {rows['max_score']}"
            )

        # Top ja bottom 5
        for label, order in [("Parhaat", "DESC"), ("Heikoimmat", "ASC")]:
            top = conn.execute(
                f"""
                SELECT q.dataset_id, q.score,
                       COALESCE(d.title_fi, d.title) as title
                FROM quality_scores q
                JOIN datasets d ON q.dataset_id = d.id
                WHERE q.dimension = 'overall'
                ORDER BY q.score {order}
                LIMIT 5
                """,
            ).fetchall()
            if top:
                print(f"\n{label}:")
                for r in top:
                    title = r["title"] or r["dataset_id"]
                    if len(title) > 60:
                        title = title[:57] + "..."
                    print(f"  {r['score']:5.1f}  {title}")

    elif args.command == "populate":
        from aura.populators import get_all_populators, get_populator

        if args.list_populators:
            for pname, pcls in get_all_populators().items():
                print(f"  {pname:25s} {pcls.description}")
            return

        if args.status:
            for pname, pcls in get_all_populators().items():
                p = pcls()
                if p.is_populated():
                    row = p.conn.execute(
                        "SELECT record_count, populated_at FROM ref_metadata WHERE name = ?",
                        (pname,),
                    ).fetchone()
                    print(
                        f"  {pname:25s} {row['record_count']} riviä "
                        f"(päivitetty: {format_date(row['populated_at'], include_time=True)})"
                    )
                else:
                    print(f"  {pname:25s} ei populoitu")
            return

        if args.name == "all":
            total = 0
            for pname, pcls in get_all_populators().items():
                p = pcls()
                if not args.force and p.is_populated() and not p.needs_update():
                    print(f"  {pname}: tuore, ohitetaan (käytä --force pakottaaksesi)")
                    continue
                print(f"Populoidaan: {pname}...")
                count = asyncio.run(p.populate())
                print(f"  {pname}: {count} riviä")
                total += count
            print(f"\nYhteensä: {total} riviä")
        else:
            pcls = get_populator(args.name)
            p = pcls()
            if not args.force and p.is_populated() and not p.needs_update():
                print(f"{args.name}: tuore, ohitetaan (käytä --force pakottaaksesi)")
                return
            count = asyncio.run(p.populate())
            print(f"Populoitu {count} riviä lähteestä {args.name}.")

    elif args.command == "migrate":
        from aura.database import get_connection, run_migrations

        conn = get_connection()
        count = run_migrations(conn)
        if count > 0:
            print(f"Ajettu {count} migraatiota.")
        else:
            print("Ei uusia migraatioita.")

    else:
        parser.print_help()


def _gap_pct(n: int, total: int) -> str:
    """Formatoi puuteprosentti sulkuihin."""
    if total == 0:
        return " (0%)"
    return f" ({100 * n // total}%)"


if __name__ == "__main__":
    main()
