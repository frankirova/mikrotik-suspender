"""Command-line interface for mikrotik-suspender.

The CLI talks directly to the use cases — it does NOT spin up the HTTP server.
This is the path for technicians who want to fire a suspension from a shell
without the overhead of running FastAPI.

Usage examples:
    python -m cli preview --mikrotik 192.168.88.1
    python -m cli run --mikrotik 192.168.88.1
    python -m cli run --mikrotik 192.168.88.1 --date 2025-06-01 --json
"""
