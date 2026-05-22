"""FERC audit-analysis pipeline.

Modular, CLI-first stages: fetch -> extract -> structure -> patterns -> build.
Each stage is idempotent and cacheable; see config.py for the single source
of truth on paths and tunables.
"""
