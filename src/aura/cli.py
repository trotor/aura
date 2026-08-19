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


def build_parser() -> argparse.ArgumentParser:
    """Rakenna Auran CLI-parseri.

    Eriytetty ``main()``:stä, jotta alikomentojen argumentit ovat
    testattavissa ilman että komentoa oikeasti ajetaan.
    """
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
        "--list",
        action="store_true",
        dest="list_sources",
        help="Listaa saatavilla olevat lähteet",
    )
    harvest_parser.add_argument(
        "--include-static",
        action="store_true",
        help="Sisällytä staattiset harvesterit (oletuksena ohitetaan)",
    )

    # serve
    serve_parser = subparsers.add_parser("serve", help="Käynnistä MCP-server")
    serve_parser.add_argument(
        "--http",
        action="store_true",
        help="Aja streamable HTTP -transportilla (remote MCP) stdion sijaan",
    )
    serve_parser.add_argument(
        "--host",
        default=None,
        help="HTTP-host (oletus: AURA_HTTP_HOST tai 127.0.0.1)",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=None,
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

    # probe (+ infer-schemas alias)
    for nimi, ohje in (
        ("probe", "Johda skeema rajapinnoista (WFS, WMS, PxWeb, CSV, JSON)"),
        ("infer-schemas", "Vanha nimi komennolle 'probe'"),
    ):
        p = subparsers.add_parser(nimi, help=ohje)
        p.add_argument("--source", default="", help="Rajaa lähteeseen")
        p.add_argument("--format", default="", help="Rajaa formaattiin (esim. WFS)")
        p.add_argument("--limit", type=int, default=50, help="Kohteiden määrä (oletus 50)")
        p.add_argument(
            "--max-age-days",
            type=int,
            default=0,
            help="Ohita TTL ja probaa kaikki tätä vanhemmat",
        )
        p.add_argument("--dry-run", action="store_true", help="Näytä kohteet, älä aja")

    # export-enrichments
    export_parser = subparsers.add_parser(
        "export-enrichments", help="Vie rikastukset JSON-tiedostoon"
    )
    export_parser.add_argument(
        "--output",
        "-o",
        default="enrichments.json",
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
    import_parser.add_argument("files", nargs="+", help="JSON-tiedostot")

    # prune-enrichments
    prune_parser = subparsers.add_parser("prune-enrichments", help="Poista vanhat rikastukset")
    prune_parser.add_argument(
        "--older-than",
        type=int,
        default=365,
        help="Poista rikastukset vanhempia kuin N päivää (oletus: 365)",
    )

    # health
    health_parser = subparsers.add_parser("health", help="Tarkista resurssien saatavuus")
    health_parser.add_argument(
        "--source",
        default="",
        help="Rajaa lähteeseen (esim. avoindata.fi)",
    )
    health_parser.add_argument(
        "--stale-days",
        type=int,
        default=7,
        help="Tarkista uudelleen N päivän jälkeen (oletus: 7)",
    )
    health_parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Tarkistettavien resurssien enimmäismäärä (oletus: 100)",
    )

    # quality
    quality_parser = subparsers.add_parser("quality", help="Laske datasettien laatupisteet")
    quality_parser.add_argument(
        "--source",
        default="",
        help="Rajaa lähteeseen (esim. avoindata.fi)",
    )
    quality_parser.add_argument(
        "--gaps",
        action="store_true",
        help="Näytä metatiedon puuteanalyysi",
    )

    # populate
    populate_parser = subparsers.add_parser(
        "populate", help="Lataa viiteaineistot (kunnat, postinumerot ym.)"
    )
    populate_parser.add_argument(
        "name",
        nargs="?",
        default="all",
        help="Populaattorin nimi tai 'all' kaikille (oletus: all)",
    )
    populate_parser.add_argument(
        "--list",
        action="store_true",
        dest="list_populators",
        help="Listaa saatavilla olevat populaattorit",
    )
    populate_parser.add_argument(
        "--status",
        action="store_true",
        help="Näytä populaattoreiden tila",
    )
    populate_parser.add_argument(
        "--force",
        action="store_true",
        help="Pakota uudelleenlataus vaikka data on tuore",
    )

    # web
    web_parser = subparsers.add_parser("web", help="Käynnistä paikallinen web-palvelin")
    web_parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Portti (oletus: 8080)",
    )
    web_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Osoite (oletus: 127.0.0.1)",
    )

    # build-site
    build_site_parser = subparsers.add_parser(
        "build-site", help="Generoi staattinen GitHub Pages -sivu"
    )
    build_site_parser.add_argument(
        "--output",
        "-o",
        default="docs/site",
        help="Tuloshakemisto (oletus: docs/site)",
    )

    # auto-tag
    auto_tag_parser = subparsers.add_parser(
        "auto-tag", help="Tagita datasetit automaattisesti YSO-käsitteillä"
    )
    auto_tag_parser.add_argument(
        "--source",
        default="",
        help="Rajaa lähteeseen (esim. avoindata.fi)",
    )
    auto_tag_parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Käsiteltävien datasettien enimmäismäärä (oletus: 100)",
    )
    auto_tag_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Näytä mitä tagitettaisiin, mutta älä tallenna",
    )
    auto_tag_parser.add_argument(
        "--delay",
        type=float,
        default=0.2,
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
        "--limit",
        type=int,
        default=0,
        help="Enimmäismäärä tauluja per lähde (0 = kaikki)",
    )

    # refresh
    refresh_parser = subparsers.add_parser(
        "refresh",
        help="Kokonaisvirkistys: harvest + laatu + health (valinnainen)",
    )
    refresh_parser.add_argument(
        "--source",
        default="all",
        help="Lähde tai 'all' (oletus: all)",
    )
    refresh_parser.add_argument(
        "--include-static",
        action="store_true",
        help="Sisällytä staattiset harvesterit",
    )
    refresh_parser.add_argument(
        "--health",
        action="store_true",
        help="Suorita myös health check",
    )
    refresh_parser.add_argument(
        "--health-limit",
        type=int,
        default=200,
        help="Health checkin resurssiraja (oletus: 200)",
    )
    refresh_parser.add_argument(
        "--schemas",
        action="store_true",
        help="Päättele myös skeematiedot",
    )

    # migrate
    subparsers.add_parser("migrate", help="Aja tietokantamigraatiot")

    # lemmatize
    subparsers.add_parser(
        "lemmatize",
        help="Indeksoi suomen perusmuodot hakua varten (datasets.lemmas)",
    )

    # region-levels
    subparsers.add_parser(
        "region-levels",
        help="Merkitse aineistot joissa kunta on dimensioarvo (aluehaku)",
    )

    # gaps
    gaps_p = subparsers.add_parser(
        "gaps", help="Näytä nollatulokselliset haut (mitä etsittiin turhaan)"
    )
    gaps_p.add_argument("--limit", type=int, default=50, help="Rivien määrä")
    gaps_p.add_argument("--clear", action="store_true", help="Tyhjennä kertymä (säilytysaika)")

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

    return parser


def main() -> None:
    """Auran CLI-päätoiminto."""
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    if args.command == "harvest":
        from aura.harvesters import get_all_harvesters
        from aura.harvesters.static import StaticHarvester

        if args.list_sources:
            for name, cls in get_all_harvesters().items():
                tag = " (staattinen)" if issubclass(cls, StaticHarvester) else ""
                print(f"  {name:25s} {cls.description}{tag}")
            return

        # `harvest` on `refresh`in lyhyt muoto: sama putki ilman valinnaisia
        # vaiheita. Yksi toteutus, jotta reitit eivät enää eriydy.
        asyncio.run(_refresh(source=args.source, include_static=args.include_static))

    elif args.command == "serve":
        from aura.serve import resolve_serve_config
        from aura.server import apply_readonly_gating, mcp

        cfg = resolve_serve_config(http=args.http, host=args.host, port=args.port)

        if cfg.transport == "stdio":
            apply_readonly_gating(mcp)
            mcp.run(**cfg.run_args())
        else:
            # HTTP-moodissa tarjoillaan web-UI ja MCP samasta prosessista:
            # juuri on ländärisivu, /mcp on endpoint. create_asgi_app()
            # hoitaa gateyksen ja lifespanien ketjutuksen.
            import uvicorn

            from aura.asgi import create_asgi_app

            uvicorn.run(
                create_asgi_app(stateless_http=cfg.stateless_http),
                host=cfg.host or "127.0.0.1",
                port=cfg.port or 8000,
            )

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

        probe_results = asyncio.run(probe_all(source=args.source, timeout=args.timeout))
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
        enrichments = export_enrichments(conn, source_type=args.source_type)
        if not enrichments:
            print("Ei rikastuksia vietäväksi.")
            sys.exit(0)

        output = {
            "version": "1.0",
            "enrichments": enrichments,
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"Viety {len(enrichments)} rikastusta tiedostoon {args.output}.")

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

    elif args.command == "gaps":
        from aura.telemetry import (
            TELEMETRY_DB_ENV,
            clear_zero_results,
            telemetry_path,
            zero_result_gaps,
        )

        if telemetry_path() is None:
            print(
                "Nollatuloskirjaus ei ole käytössä.\n"
                f"Kytke päälle asettamalla {TELEMETRY_DB_ENV}, esim.\n"
                f"  export {TELEMETRY_DB_ENV}=data/telemetry.db\n\n"
                "Huom: kirjaus tallentaa hakusanat. Se on tietosuojapäätös, "
                "siksi oletus on pois päältä."
            )
            return

        if args.clear:
            removed = clear_zero_results()
            print(f"Poistettu {removed} riviä.")
            return

        rows = zero_result_gaps(limit=args.limit)
        if not rows:
            print("Ei nollatuloksellisia hakuja kirjattuna.")
            return

        print(f"\n{'kpl':>5}  {'viimeksi':<21} kysely")
        print("-" * 72)
        for row in rows:
            print(f"{row['count']:>5}  {str(row['last_seen'])[:19]:<21} {row['query']}")
        print(
            f"\n{len(rows)} eri kyselyä, yhteensä "
            f"{sum(int(str(r['count'])) for r in rows)} nollatulosta."
        )

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
        for stale_report in reports:
            print(
                f"{stale_report.source:<20} {stale_report.latest_harvest[:19]:<21} "
                f"{stale_report.stale:>8} {stale_report.remaining:>8}"
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
        summary = asyncio.run(
            check_all_resources(
                conn,
                source=args.source,
                stale_days=args.stale_days,
                limit=args.limit,
            )
        )

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
            print(
                f"  {'Lähde':25s} {'Yht':>5s} {'Kuvaus':>8s} "
                f"{'Avains':>8s} {'Päiv.':>8s} {'Lis.':>8s} {'Täyd.':>6s}"
            )
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
            print(f"\n  Kokonaismetatiedon täydellisyys: {totals.get('completeness_pct', 0):.0f}%")

            suggestions = suggest_improvements(
                conn,
                source=args.source,
                limit=10,
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
        asyncio.run(
            _auto_tag(
                source=args.source,
                limit=args.limit,
                dry_run=args.dry_run,
                delay=args.delay,
            )
        )

    elif args.command == "enrich-pxweb":
        from aura.harvesters import HARVESTERS
        from aura.harvesters.pxweb import PxWebHarvester

        pxweb_sources = {
            name: cls for name, cls in HARVESTERS.items() if issubclass(cls, PxWebHarvester)
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

    elif args.command in ("probe", "infer-schemas"):
        if args.command == "infer-schemas":
            print("Huom: 'infer-schemas' on nyt 'probe'. Vanha nimi toimii yhä.")
        asyncio.run(
            _probe(
                source=args.source,
                fmt=args.format,
                limit=args.limit,
                dry_run=args.dry_run,
            )
        )

    elif args.command == "refresh":
        asyncio.run(
            _refresh(
                source=args.source,
                include_static=args.include_static,
                run_health=args.health,
                health_limit=args.health_limit,
                run_schemas=args.schemas,
            )
        )

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

    elif args.command == "region-levels":
        import httpx

        from aura.constants import user_agent
        from aura.database import get_connection, run_migrations
        from aura.populators.municipalities import SOTKANET_REGIONS_URL
        from aura.region_levels import refresh

        conn = get_connection()
        run_migrations(conn)

        # Sotkanetin aluetasot yhdellä kutsulla. Jos se ei vastaa,
        # PxWeb-puoli merkitään silti — puolikas kate on parempi kuin
        # ei mitään, ja epäonnistuminen on sanottava ääneen.
        indicators = None
        try:
            resp = httpx.get(
                SOTKANET_REGIONS_URL.replace("/regions", "/indicators"),
                timeout=120,
                headers={"User-Agent": user_agent("region-levels")},
                follow_redirects=True,
            )
            resp.raise_for_status()
            indicators = resp.json()
        except Exception as exc:  # noqa: BLE001
            print(f"VAROITUS: Sotkanetin indikaattoreita ei saatu ({exc}).")
            print("Merkitään vain PxWeb-taulut.")

        count = refresh(conn, indicators)
        print(f"Kuntatasoisiksi merkitty {count} datasettiä.")
        print("Aluehaku palauttaa ne omana ryhmänään valtakunnallisina aineistoina.")

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
        conn,
        field="yso_concepts",
        source=source,
        limit=limit,
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
                    [s.to_dict() for s in suggestions],
                    ensure_ascii=False,
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


async def _probe(
    source: str = "", fmt: str = "", limit: int = 50, dry_run: bool = False
) -> None:
    """Aja probe-vaihe."""
    from datetime import UTC, datetime

    import aura.server  # noqa: F401 — ratkaise kiertoimport ennen tools-tuonteja
    from aura.database import get_connection, run_migrations
    from aura.probe import format_probe_summary, run_probe, select_targets

    conn = get_connection()
    run_migrations(conn)
    now = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%S")

    if dry_run:
        targets = select_targets(conn, now=now, source=source, fmt=fmt, limit=limit)
        print(f"{len(targets)} kohdetta:")
        for t in targets[:20]:
            print(f"  {t['format']:8} {t['url'][:90]}")
        return

    summary = await run_probe(conn, source=source, fmt=fmt, limit=limit, now=now)
    print(format_probe_summary(summary))


async def _refresh(
    source: str = "all",
    include_static: bool = False,
    run_health: bool = False,
    health_limit: int = 200,
    run_schemas: bool = False,
) -> None:
    """Kokonaisvirkistys: harvest + vanhentuneet + laatu + lemmat (+ health, schemas).

    Vaiheiden järjestys ei ole mielivaltainen:

    - **Vanhentuneiden raportti heti harvestoinnin jälkeen**, koska vasta silloin
      tiedetään mitä lähde tällä kertaa palautti. Raportti on kuiva-ajo; poisto
      vaatii aina erillisen komennon.
    - **Lemmaindeksointi viimeisenä pakollisena vaiheena**, koska se lukee
      harvestoinnin tuottamat rivit. Ilman sitä uudet aineistot ovat
      näkymättömiä perusmuotohaulle — juuri tämä unohtui aiemmin, koska
      lemmatize oli vain oma erillinen komentonsa.
    """
    from aura.database import get_connection, init_db
    from aura.lemmatize import index_lemmas
    from aura.pipeline import harvest_sources
    from aura.prune import find_stale
    from aura.quality import score_all_datasets

    conn = get_connection()
    init_db(conn)

    steps = ["Harvestointi", "Vanhentuneet rivit", "Laatupisteytys", "Lemmaindeksointi"]
    if run_health:
        steps.append("Health check")
    if run_schemas:
        steps.append("Schema introspection")

    def otsikko(nimi: str) -> None:
        print("=" * 50)
        print(f"VAIHE {steps.index(nimi) + 1}/{len(steps)}: {nimi}")
        print("=" * 50)

    src_filter = "" if source == "all" else source

    # 1. Harvest
    otsikko("Harvestointi")
    outcome = await harvest_sources(
        conn,
        source=source,
        include_static=include_static,
        on_progress=lambda name, count: print(
            f"  Harvestoidaan: {name}..." if count is None else f"    {count} datasettiä"
        ),
    )
    if outcome.skipped:
        print(f"  Ohitettu staattiset: {', '.join(outcome.skipped)}")
        print("    (käytä --include-static sisällyttääksesi)")
    print(f"  Yhteensä: {outcome.total} datasettiä\n")

    # 2. Vanhentuneet rivit — vain raportti, ei poistoa
    otsikko("Vanhentuneet rivit")
    stale = find_stale(conn, source=src_filter)
    if stale:
        for report in stale:
            print(f"  {report.source:<20} {report.stale:>6} vanhentunutta riviä")
        print(
            f"\n  Yhteensä {sum(r.stale for r in stale)} riviä ei ole nähty lähteessä 30 päivään."
        )
        print("  Poista komennolla: aura prune --apply\n")
    else:
        print("  Ei vanhentuneita rivejä.\n")

    # 3. Laatupisteet
    otsikko("Laatupisteytys")
    qcount = score_all_datasets(conn, source=src_filter)
    print(f"  Laatupisteet laskettu {qcount} datasetille.\n")

    # 4. Lemmat — pakollinen, ei valinnainen
    otsikko("Lemmaindeksointi")
    lcount = index_lemmas(conn)
    print(f"  Perusmuodot indeksoitu {lcount} datasetille.\n")

    # 5. Health check (valinnainen)
    if run_health:
        otsikko("Health check")
        from aura.health import check_all_resources

        summary = await check_all_resources(
            conn,
            source=src_filter,
            limit=health_limit,
        )
        print(f"  Tarkistettu: {summary.total}")
        print(f"  Saatavilla:  {summary.available}")
        print(f"  Virheitä:    {summary.errors}\n")

    # 6. Schema introspection (valinnainen)
    if run_schemas:
        otsikko("Schema introspection")
        await _probe(source=src_filter, limit=100)

    # Varoitukset viimeisenä: pitkän ajon alussa tulostettu häviää vieritykseen.
    if outcome.warnings:
        print("=" * 50)
        print(f"VAROITUKSET ({len(outcome.warnings)})")
        print("=" * 50)
        for warning in outcome.warnings:
            print(f"  - {warning}")
        print()

    print("Refresh valmis!")


def _gap_pct(n: int, total: int) -> str:
    """Formatoi puuteprosentti sulkuihin."""
    if total == 0:
        return " (0%)"
    return f" ({100 * n // total}%)"


if __name__ == "__main__":
    main()
