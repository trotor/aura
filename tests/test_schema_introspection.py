"""Testit schema introspection -toiminnallisuudelle (#115)."""

import sqlite3

from aura.database import (
    get_resource_schema,
    init_db,
    upsert_dataset,
    upsert_resource_schema,
)
from aura.models import Dataset, Resource

# Import server first to avoid circular import when importing from tools
import aura.server  # noqa: F401
from aura.tools.schema import infer_type, parse_md_table, save_schema_from_markdown


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _seed(conn: sqlite3.Connection) -> None:
    ds = Dataset(
        id="ds-1",
        name="test-dataset",
        title_fi="Testi",
        resources=[
            Resource(id="res-1", name="CSV data", format="CSV", url="https://example.com/data.csv"),
        ],
    )
    upsert_dataset(conn, ds)
    conn.commit()


class TestResourceSchema:
    """resource_schema taulun CRUD-operaatiot."""

    def test_upsert_and_get(self) -> None:
        conn = _memory_db()
        _seed(conn)
        fields = [("kunta", "string"), ("vuosi", "integer"), ("vakiluku", "integer")]
        upsert_resource_schema(conn, "res-1", "ds-1", fields)
        conn.commit()

        schema = get_resource_schema(conn, "ds-1")
        assert len(schema) == 3
        assert schema[0]["field_name"] == "kunta"
        assert schema[0]["field_type"] == "string"
        assert schema[1]["field_name"] == "vuosi"
        assert schema[2]["field_name"] == "vakiluku"

    def test_upsert_replaces_old_fields(self) -> None:
        conn = _memory_db()
        _seed(conn)
        upsert_resource_schema(conn, "res-1", "ds-1", [("a", "string")])
        conn.commit()

        upsert_resource_schema(conn, "res-1", "ds-1", [("b", "integer"), ("c", "float")])
        conn.commit()

        schema = get_resource_schema(conn, "ds-1")
        assert len(schema) == 2
        names = [s["field_name"] for s in schema]
        assert "b" in names
        assert "c" in names
        assert "a" not in names

    def test_empty_fields_no_op(self) -> None:
        conn = _memory_db()
        _seed(conn)
        upsert_resource_schema(conn, "res-1", "ds-1", [])
        schema = get_resource_schema(conn, "ds-1")
        assert schema == []

    def test_no_schema_returns_empty(self) -> None:
        conn = _memory_db()
        _seed(conn)
        schema = get_resource_schema(conn, "ds-1")
        assert schema == []


class TestInferType:
    """Tyyppipäättely esimerkkiarvoista."""

    def test_integer(self) -> None:
        assert infer_type(["1", "42", "-7"]) == "integer"

    def test_float(self) -> None:
        assert infer_type(["1.5", "3,14", "-0.7"]) == "float"

    def test_date(self) -> None:
        assert infer_type(["2024-01-15", "2023-12-31"]) == "date"

    def test_datetime(self) -> None:
        assert infer_type(["2024-01-15T12:00:00"]) == "date"

    def test_string(self) -> None:
        assert infer_type(["Helsinki", "Espoo"]) == "string"

    def test_mixed_types_fall_to_string(self) -> None:
        assert infer_type(["42", "Helsinki"]) == "string"

    def test_empty_values(self) -> None:
        assert infer_type(["", "  "]) == "string"


class TestParseMdTable:
    """Markdown-taulukon parsinta."""

    def test_basic_table(self) -> None:
        md = "| a | b |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |"
        headers, rows = parse_md_table(md)
        assert headers == ["a", "b"]
        assert len(rows) == 2
        assert rows[0] == ["1", "2"]

    def test_no_table(self) -> None:
        headers, rows = parse_md_table("No table here")
        assert headers == []
        assert rows == []

    def test_table_with_prefix_text(self) -> None:
        md = "**CSV** data\n\n| x | y |\n| --- | --- |\n| 10 | 20 |"
        headers, rows = parse_md_table(md)
        assert headers == ["x", "y"]
        assert len(rows) == 1


class TestSaveSchemaFromMarkdown:
    """Markdown-taulukosta skeeman tallennus."""

    def test_saves_from_csv_preview(self) -> None:
        conn = _memory_db()
        _seed(conn)
        body = "| kunta | vuosi | vakiluku |\n| --- | --- | --- |\n| Helsinki | 2024 | 679000 |"
        save_schema_from_markdown(conn, "res-1", "ds-1", body)

        schema = get_resource_schema(conn, "ds-1")
        assert len(schema) == 3
        names = [s["field_name"] for s in schema]
        assert "kunta" in names
        assert "vuosi" in names
        assert "vakiluku" in names
        # Type inference
        types = {s["field_name"]: s["field_type"] for s in schema}
        assert types["kunta"] == "string"
        assert types["vuosi"] == "integer"
        assert types["vakiluku"] == "integer"

    def test_no_table_no_save(self) -> None:
        conn = _memory_db()
        _seed(conn)
        save_schema_from_markdown(conn, "res-1", "ds-1", "No data available.")
        assert get_resource_schema(conn, "ds-1") == []

    def test_empty_resource_id_skipped(self) -> None:
        conn = _memory_db()
        _seed(conn)
        save_schema_from_markdown(conn, "", "ds-1", "| a |\n| --- |\n| 1 |")
        assert get_resource_schema(conn, "ds-1") == []
