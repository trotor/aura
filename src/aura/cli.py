"""Auran komentorivityökalu."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import UTC

from aura import __version__
from aura.constants import format_date
from aura.prune import STALE_AFTER_DAYS


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
    serve_parser = subparsers.add_parser("serve", help="Käynnistä MCP-server")
    serve_parser.add_argument(
        "--http", action="store_true",
        help="Aja streamable HTTP -transportilla (remote MCP) stdion sijaan",
    )
    serve_parser.add_argument(
        "--host", default=None,
        help="HTTP-host (oletus: AURA_HTTP_HOST tai 127.0.0.1)",
    )
    serve_parser.add_argument(
        "--port", type=int, default=None,
        help="HTTP-portti (oletus: AURA_HTTP_PORT tai 8000)",
    )

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

    # web
    web_parser = subparsers.add_parser("web", help="Käynnistä paikallinen web-palvelin")
    web_parser.add_argument(
        "--port", type=int, default=8080,
        help="Portti (oletus: 8080)",
    )
    web_parser.add_argument(
        "--host", default="127.0.0.1",
        help="Osoite (oletus: 127.0.0.1)",
    )

    # build-site
    build_site_parser = subparsers.add_parser(
        "build-site", help="Generoi staattinen GitHub Pages -sivu"
    )
    build_site_parser.add_argument(
        "--output", "-o", default="docs/site",
        help="Tuloshakemisto (oletus: docs/site)",
    )

    # auto-tag
    auto_tag_parser = subparsers.add_parser(
        "auto-tag", help="Tagita datasetit automaattisesti YSO-käsitteillä"
    )
    auto_tag_parser.add_argument(
        "--source", default="",
        help="Rajaa lähteeseen (esim. avoindata.fi)",
    )
    auto_tag_parser.add_argument(
        "--limit", type=int, default=100,
        help="Käsiteltävien datasettien enimmäismäärä (oletus: 100)",
    )
    auto_tag_parser.add_argument(
        "--dry-run", action="store_true",
        help="Näytä mitä tagitettaisiin, mutta älä tallenna",
    )
    auto_tag_parser.add_argument(
        "--delay", type=float, default=0.2,
        help="Viive sekunteina datasettien välissä (oletus: 0.2)",
    )

    # enrich-pxweb
    enrich_pxweb_parser = subparsers.add_parser(
        "enrich-pxweb",
        help="Rikasta PxWeb-taulut dimensiotiedoilla (muuttujat, aikasarjat)",
    )
    enrich_pxweb_parser.add_argument(
        "source",
        nargs="?",
        default="all",
        help="PxWeb-lähde (statfin, luke) tai 'all' (oletus: all)",
    )
    enrich_pxweb_parser.add_argument(
        "--limit", type=int, default=0,
        help="Enimmäismäärä tauluja per lähde (0 = kaikki)",
    )

    # infer-schemas
    infer_schema_parser = subparsers.add_parser(
        "infer-schemas",
        help="Päättele datasettien kenttätiedot (schema introspection)",
    )
    infer_schema_parser.add_argument(
        "--source", default="",
        help="Rajaa lähteeseen (esim. avoindata.fi)",
    )
    infer_schema_parser.add_argument(
        "--limit", type=int, default=50,
        help="Käsiteltävien datasettien enimmäismäärä (oletus: 50)",
    )
    infer_schema_parser.add_argument(
        "--delay", type=float, default=0.3,
        help="Viive sekunteina pyyntöjen välissä (oletus: 0.3)",
    )

    # refresh
    refresh_parser = subparsers.add_parser(
        "refresh",
        help="Kokonaisvirkistys: harvest + laatu + health (valinnainen)",
    )
    refresh_parser.add_argument(
        "--source", default="all",
        help="Lähde tai 'all' (oletus: all)",
    )
    refresh_parser.add_argument(
        "--include-static", action="store_true",
        help="Sisällytä staattiset harvesterit",
    )
    refresh_parser.add_argument(
        "--health", action="store_true",
        help="Suorita myös health check",
    )
    refresh_parser.add_argument(
        "--health-limit", type=int, default=200,
        help="Health checkin resurssiraja (oletus: 200)",
    )
    refresh_parser.add_argument(
        "--schemas", action="store_true",
        help="Päättele myös skeematiedot",
    )

    # migrate
    subparsers.add_parser("migrate", help="Aja tietokantamigraatiot")

    # lemmatize
    subparsers.add_parser(
        "lemmatize",
        help="Indeksoi suomen perusmuodot hakua varten (datasets.lemmas)",
    )

    # prune
    prune_ds = subparsers.add_parser(
        "prune", help="Poista lähteestä kadonneet datasetit (oletuksena kuiva-ajo)"
    )
    prune_ds.add_argument("--source", default="", help="Rajaa yhteen lähteeseen")
    prune_ds.add_argument(
        "--days",
        type=int,
        default=STALE_AFTER_DAYS,
        help=f"Päiviä lähteen viimeisimmästä ajosta (oletus: {STALE_AFTER_DAYS})",
    )
    prune_ds.add_argument(
        "--apply", action="store_true", help="Poista oikeasti (ilman tätä kuiva-ajo)"
    )
    prune_ds.add_argument(
        "--force", action="store_true", help="Salli kuratoitujen rikastusten poisto"
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    if args.command == "harvest":
        from datetime import datetime

        from aura.database import upsert_source
        from aura.harvesters import get_all_harvesters, get_harvester
        from aura.harvesters.static import StaticHarvester

        if args.list_sources:
            for name, cls in get_all_harvesters().items():
                tag = " (staattinen)" if issubclass(cls, StaticHarvester) else ""
                print(f"  {name:25s} {cls.description}{tag}")
            return

        now = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%S")

        if args.source == "all":
            from aura.prune import check_count_regression

            total = 0
            skipped = []
            warnings: list[str] = []
            for name, cls in get_all_harvesters().items():
                if issubclass(cls, StaticHarvester) and not args.include_static:
                    skipped.append(name)
                    continue
                print(f"Harvestoidaan: {name}...")
                harvester = cls()
                count = asyncio.run(harvester.harvest())
                print(f"  {name}: {count} datasettiä")
                total += count
                # Vertaa edelliseen ajoon ENNEN kuin sources-rivi ylikirjoitetaan
                warning = check_count_regression(harvester.conn, name, count)
                if warning:
                    warnings.append(warning)
                    print(f"  VAROITUS  {warning}")
                # Päivitä sources-taulu (#125)
                src_cfg = cls.source_config()
                src_cfg["dataset_count"] = count
                src_cfg["last_harvested_at"] = now
                upsert_source(harvester.conn, src_cfg)
                harvester.conn.commit()
            if warnings:
                print(f"\n{len(warnings)} lähdettä tuotti odotettua vähemmän:")
                for warning in warnings:
                    print(f"  - {warning}")
            if skipped:
                print(f"\nOhitettu staattiset: {', '.join(skipped)}")
                print("  (käytä --include-static sisällyttääksesi)")
            print(f"\nYhteensä: {total} datasettiä")
            # Laske laatupisteet harvestoinnin jälkeen (#127)
            from aura.quality import score_all_datasets

            qcount = score_all_datasets(harvester.conn)
            print(f"Laatupisteet laskettu {qcount} datasetille.")
        else:
            cls = get_harvester(args.source)
            harvester = cls()
            count = asyncio.run(harvester.harvest())
            # Päivitä sources-taulu (#125)
            src_cfg = cls.source_config()
            src_cfg["dataset_count"] = count
            src_cfg["last_harvested_at"] = now
            upsert_source(harvester.conn, src_cfg)
            harvester.conn.commit()
            print(f"Haettu {count} datasettiä lähteestä {args.source}.")
            # Laske laatupisteet harvestoinnin jälkeen (#127)
            from aura.quality import score_all_datasets

            qcount = score_all_datasets(harvester.conn, source=args.source)
            print(f"Laatupisteet laskettu {qcount} datasetille.")

    elif args.command == "serve":
        from aura.serve import resolve_serve_config
        from aura.server import apply_readonly_gating, mcp

        apply_readonly_gating(mcp)
        cfg = resolve_serve_config(http=args.http, host=args.host, port=args.port)
        mcp.run(**cfg.run_args())

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

    elif args.command == "prune":
        from aura.database import get_connection, init_db
        from aura.prune import find_stale, prune_datasets

        conn = get_connection()
        init_db(conn)

        reports = find_stale(conn, days=args.days, source=args.source)
        if not reports:
            print(f"Ei vanhentuneita datasettejä (ikäraja {args.days} päivää).")
            return

        print(f"{'LÄHDE':<20} {'VIIMEISIN AJO':<21} {'POISTUU':>8} {'JÄÄ':>8}")
        print("-" * 60)
        for report in reports:
            print(
                f"{report.source:<20} {report.latest_harvest[:19]:<21} "
                f"{report.stale:>8} {report.remaining:>8}"
            )
        print("-" * 60)

        try:
            stats = prune_datasets(
                conn,
                days=args.days,
                source=args.source,
                apply=args.apply,
                force=args.force,
            )
        except ValueError as exc:
            print(f"\nKESKEYTETTY: {exc}")
            raise SystemExit(1) from exc

        if stats["curated_enrichments"]:
            print(
                f"\nHUOM: mukana {stats['curated_enrichments']} kuratoitua "
                "rikastusta (ei harvesterin tuottamaa)."
            )
        if args.apply:
            print(f"\nPoistettu {stats['datasets']} datasettiä.")
            for table, count in stats.items():
                if table not in ("datasets", "curated_enrichments") and count:
                    print(f"  {table}: {count} riviä")
        else:
            print(
                f"\nKuiva-ajo: {stats['datasets']} datasettiä poistuisi. "
                "Toteuta lisäämällä --apply."
            )

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

    elif args.command == "web":
        import uvicorn

        from aura.web.app import create_app

        app = create_app()
        print(f"Aura web: http://{args.host}:{args.port}")
        uvicorn.run(app, host=args.host, port=args.port)

    elif args.command == "build-site":
        from aura.web.build import build_static_site

        build_static_site(output_dir=args.output)

    elif args.command == "auto-tag":
        asyncio.run(_auto_tag(
            source=args.source,
            limit=args.limit,
            dry_run=args.dry_run,
            delay=args.delay,
        ))

    elif args.command == "enrich-pxweb":
        from aura.harvesters import HARVESTERS
        from aura.harvesters.pxweb import PxWebHarvester

        pxweb_sources = {
            name: cls for name, cls in HARVESTERS.items()
            if issubclass(cls, PxWebHarvester)
        }

        if args.source == "all":
            targets = list(pxweb_sources.items())
        elif args.source in pxweb_sources:
            targets = [(args.source, pxweb_sources[args.source])]
        else:
            available = ", ".join(pxweb_sources.keys())
            print(f"Tuntematon PxWeb-lähde: {args.source}. Saatavilla: {available}")
            sys.exit(1)

        total = 0
        for name, cls in targets:
            harvester = cls()
            count = asyncio.run(harvester.harvest_dimensions(limit=args.limit))
            print(f"  {name}: {count} taulua rikastettu")
            total += count
        print(f"\nYhteensä: {total} taulua rikastettu dimensiotiedoilla.")

    elif args.command == "infer-schemas":
        asyncio.run(_infer_schemas(
            source=args.source,
            limit=args.limit,
            delay=args.delay,
        ))

    elif args.command == "refresh":
        asyncio.run(_refresh(
            source=args.source,
            include_static=args.include_static,
            run_health=args.health,
            health_limit=args.health_limit,
            run_schemas=args.schemas,
        ))

    elif args.command == "migrate":
        from aura.database import get_connection, run_migrations

        conn = get_connection()
        count = run_migrations(conn)
        if count > 0:
            print(f"Ajettu {count} migraatiota.")
        else:
            print("Ei uusia migraatioita.")

    elif args.command == "lemmatize":
        from aura.database import get_connection, run_migrations
        from aura.lemmatize import LEMMATIZER_AVAILABLE, index_lemmas

        if not LEMMATIZER_AVAILABLE:
            print("simplemma puuttuu. Asenna: pip install simplemma")
            return

        conn = get_connection()
        run_migrations(conn)
        count = index_lemmas(conn)
        print(f"Lemmat indeksoitu {count} datasetille.")

    else:
        parser.print_help()


async def _auto_tag(
    source: str = "",
    limit: int = 100,
    dry_run: bool = False,
    delay: float = 0.2,
) -> None:
    """Tagita datasetit automaattisesti YSO-käsitteillä."""
    from aura.database import (
        add_enrichment,
        get_connection,
        get_datasets_without_enrichment,
        init_db,
    )
    from aura.tagger import suggest_tags
    from aura.yso import YsoClient

    conn = get_connection()
    init_db(conn)

    datasets = get_datasets_without_enrichment(
        conn, field="yso_concepts", source=source, limit=limit,
    )

    if not datasets:
        print("Kaikki datasetit on jo tagitettu.")
        return

    print(f"Tagitettavia datasettejä: {len(datasets)}")
    if dry_run:
        print("(dry-run: ei tallenneta)\n")

    yso = YsoClient()
    tagged = 0
    skipped = 0
    errors = 0

    try:
        for i, ds in enumerate(datasets, 1):
            title = ds.get("title_fi") or ds.get("title") or ds.get("name", "")
            ds_id = ds["id"]

            try:
                suggestions = await suggest_tags(ds, yso, max_tags=10)
            except Exception as e:
                errors += 1
                print(f"  VIRHE: {title[:60]} — {e}")
                continue

            if not suggestions:
                skipped += 1
                if i % 10 == 0 or i == len(datasets):
                    print(f"  [{i}/{len(datasets)}] Edistyminen...")
                continue

            labels = [s.label for s in suggestions]

            tagged += 1
            if dry_run:
                print(f"  {title[:60]}")
                print(f"    → {', '.join(labels)}")
            else:
                import json

                concepts_json = json.dumps(
                    [s.to_dict() for s in suggestions], ensure_ascii=False,
                )
                add_enrichment(
                    conn,
                    dataset_id=ds_id,
                    field="yso_concepts",
                    value=concepts_json,
                    confidence="high",
                    source_type="ai_analysis",
                    source_detail="YSO auto-tagger (CLI)",
                )

            if i % 10 == 0 or i == len(datasets):
                print(f"  [{i}/{len(datasets)}] Edistyminen...")

            if delay > 0 and i < len(datasets):
                await asyncio.sleep(delay)

    finally:
        await yso.close()

    if dry_run:
        print(f"\nDry-run valmis. Tagitettaisiin {tagged} datasettiä ({skipped} ohitettu).")
    else:
        print(f"\nTagitettu {tagged} datasettiä, virheitä {errors}.")


async def _infer_schemas(
    source: str = "",
    limit: int = 50,
    delay: float = 0.3,
) -> None:
    """Päättele datasettien kenttätiedot esikatselun perusteella (#124)."""
    import aura.server  # noqa: F401 — resolve circular import before tools
    from aura.database import get_connection, init_db
    from aura.tools.preview import _pick_resource, _preview_csv, _preview_json
    from aura.tools.schema import save_schema_from_markdown

    conn = get_connection()
    init_db(conn)

    # Hae datasetit joilla on CSV/JSON-resursseja mutta ei vielä skeemaa
    query = """
        SELECT d.id, d.name, COALESCE(d.title_fi, d.title) as title
        FROM datasets d
        JOIN resources r ON r.dataset_id = d.id
        LEFT JOIN resource_schema rs ON rs.dataset_id = d.id
        WHERE UPPER(r.format) IN ('CSV', 'JSON', 'GEOJSON')
          AND rs.dataset_id IS NULL
    """
    params: list[str] = []
    if source:
        query += " AND d.source = ?"
        params.append(source)
    query += " GROUP BY d.id ORDER BY d.name LIMIT ?"
    params.append(str(limit))

    datasets = conn.execute(query, params).fetchall()

    if not datasets:
        print("Kaikilla dataseteilla on jo skeematiedot (tai ei CSV/JSON-resursseja).")
        return

    print(f"Päätellään skeemoja {len(datasets)} datasetille...\n")

    inferred = 0
    errors = 0

    for i, ds in enumerate(datasets, 1):
        ds_id = ds["id"]
        title = ds["title"] or ds["name"]

        resources = conn.execute(
            "SELECT * FROM resources WHERE dataset_id = ?", (ds_id,),
        ).fetchall()
        resources = [dict(r) for r in resources]

        resource = _pick_resource(resources, None, "CSV")
        if resource is None:
            resource = _pick_resource(resources, None, "JSON")
        if resource is None:
            continue

        fmt = (resource.get("format") or "").upper()
        url = resource.get("url", "")
        res_id = resource.get("id", "")

        if not url:
            continue

        try:
            if fmt == "CSV":
                body = await _preview_csv(url, 10)
            else:
                body = await _preview_json(url, 10)

            save_schema_from_markdown(conn, res_id, ds_id, body)
            inferred += 1
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  VIRHE: {title[:50]} — {e}")

        if i % 10 == 0 or i == len(datasets):
            print(f"  [{i}/{len(datasets)}] {inferred} skeemaa pääteltynä...")

        if delay > 0 and i < len(datasets):
            await asyncio.sleep(delay)

    print(f"\nValmis: {inferred} skeemaa pääteltynä, {errors} virhettä.")


async def _refresh(
    source: str = "all",
    include_static: bool = False,
    run_health: bool = False,
    health_limit: int = 200,
    run_schemas: bool = False,
) -> None:
    """Kokonaisvirkistys: harvest + quality + health + schemas (#123)."""
    from datetime import datetime

    from aura.database import get_connection, init_db, upsert_source
    from aura.harvesters import get_all_harvesters, get_harvester
    from aura.harvesters.static import StaticHarvester
    from aura.quality import score_all_datasets

    conn = get_connection()
    init_db(conn)
    now = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%S")

    # 1. Harvest
    print("=" * 50)
    print("VAIHE 1: Harvestointi")
    print("=" * 50)

    if source == "all":
        total = 0
        skipped = []
        for name, cls in get_all_harvesters().items():
            if issubclass(cls, StaticHarvester) and not include_static:
                skipped.append(name)
                continue
            print(f"  Harvestoidaan: {name}...")
            harvester = cls(conn=conn)
            count = await harvester.harvest()
            print(f"    {count} datasettiä")
            total += count
            src_cfg = cls.source_config()
            src_cfg["dataset_count"] = count
            src_cfg["last_harvested_at"] = now
            upsert_source(conn, src_cfg)
        conn.commit()
        if skipped:
            print(f"  Ohitettu staattiset: {', '.join(skipped)}")
        print(f"  Yhteensä: {total} datasettiä\n")
    else:
        cls = get_harvester(source)
        harvester = cls(conn=conn)
        count = await harvester.harvest()
        src_cfg = cls.source_config()
        src_cfg["dataset_count"] = count
        src_cfg["last_harvested_at"] = now
        upsert_source(conn, src_cfg)
        conn.commit()
        print(f"  {count} datasettiä lähteestä {source}\n")

    # 2. Laatupisteet
    print("=" * 50)
    print("VAIHE 2: Laatupisteytys")
    print("=" * 50)

    src_filter = "" if source == "all" else source
    qcount = score_all_datasets(conn, source=src_filter)
    print(f"  Laatupisteet laskettu {qcount} datasetille.\n")

    # 3. Health check (valinnainen)
    if run_health:
        print("=" * 50)
        print("VAIHE 3: Health check")
        print("=" * 50)

        from aura.health import check_all_resources

        summary = await check_all_resources(
            conn,
            source=src_filter,
            limit=health_limit,
        )
        print(f"  Tarkistettu: {summary.total}")
        print(f"  Saatavilla:  {summary.available}")
        print(f"  Virheitä:    {summary.errors}\n")

    # 4. Schema introspection (valinnainen)
    if run_schemas:
        print("=" * 50)
        print(f"VAIHE {'4' if run_health else '3'}: Schema introspection")
        print("=" * 50)

        await _infer_schemas(source=src_filter, limit=100)

    print("\nRefresh valmis!")


def _gap_pct(n: int, total: int) -> str:
    """Formatoi puuteprosentti sulkuihin."""
    if total == 0:
        return " (0%)"
    return f" ({100 * n // total}%)"


if __name__ == "__main__":
    main()
