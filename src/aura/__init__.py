"""Aura — Suomalaisen avoimen datan discovery- ja ymmärryspalvelu."""

try:
    from importlib.metadata import version

    __version__ = version("aura")
except Exception:
    __version__ = "0.1.0"
