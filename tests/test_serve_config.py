"""Testit serve-komennon transport-konfiguraation resoluutiolle (#134)."""

from aura.serve import resolve_serve_config


def test_default_is_stdio() -> None:
    cfg = resolve_serve_config(http=False, host=None, port=None, env={})
    assert cfg.transport == "stdio"
    assert cfg.run_args() == {"transport": "stdio"}


def test_http_defaults() -> None:
    cfg = resolve_serve_config(http=True, host=None, port=None, env={})
    assert cfg.transport == "http"
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 8000
    assert cfg.path == "/mcp"
    assert cfg.stateless_http is True
    assert cfg.run_args() == {
        "transport": "http",
        "host": "127.0.0.1",
        "port": 8000,
        "path": "/mcp",
        "stateless_http": True,
    }


def test_http_reads_host_and_port_from_env() -> None:
    cfg = resolve_serve_config(
        http=True,
        host=None,
        port=None,
        env={"AURA_HTTP_HOST": "0.0.0.0", "AURA_HTTP_PORT": "9001"},
    )
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 9001


def test_explicit_args_override_env() -> None:
    cfg = resolve_serve_config(
        http=True,
        host="0.0.0.0",
        port=8080,
        env={"AURA_HTTP_HOST": "127.0.0.1", "AURA_HTTP_PORT": "9001"},
    )
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 8080


def test_stdio_ignores_http_settings() -> None:
    cfg = resolve_serve_config(
        http=False,
        host="0.0.0.0",
        port=8080,
        env={"AURA_HTTP_PORT": "9001"},
    )
    assert cfg.transport == "stdio"
    assert cfg.run_args() == {"transport": "stdio"}
