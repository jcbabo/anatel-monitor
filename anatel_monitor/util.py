"""Utilitarios de data/hora e log usados em todo o monitor."""

from __future__ import annotations

from datetime import datetime

def agora() -> str:
    return datetime.now().strftime("%d/%m %H:%M:%S")

def log(msg: str) -> None:
    print(f"[{agora()}] {msg}", flush=True)
