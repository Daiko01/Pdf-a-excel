# -*- coding: utf-8 -*-
"""Constantes de esquema, mapeos y utilidades de casteo."""
from __future__ import annotations
from typing import Dict, Callable, Any, Tuple, Optional
import re

ROW_SCHEMA = [
    "Fecha",
    "Hora",
    "Máquina",
    "Patente",
    "Folio",
    "Variante",
    "Frecuencia",
    "Conductor",
    "AB",
    "SD",
    "CI",
    "%EV",
    "TE",
]

# Regex ajustadas (los PDFs separan la fecha y la hora en líneas distintas)
FECHA_RE = re.compile(r"\b(?P<Fecha>\d{2}-\d{2}-\d{4})\b")
HORA_RE = re.compile(r"\b(?P<Hora>\d{2}:\d{2}:\d{2})\b")
PATENTE_RE = re.compile(r"\b[A-Z0-9]{5,6}\b")
TRIPLE_PIPE_RE = re.compile(r"(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)")  # AB|SD|CI
PAIR_RE = re.compile(r"(\d+)\s*\|\s*(\d+)")  # EV|TE u otros pares
PCT_EV_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")

ENTERO_1_3 = re.compile(r"\b\d{1,3}\b")
ENTERO_3 = re.compile(r"\b\d{3}\b")

# Utilidades
def normalize_space(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

def try_parse_int(x: Any) -> Optional[int]:
    try:
        if x is None or x == "":
            return None
        return int(str(x).strip())
    except Exception:
        return None

def try_parse_float(x: Any) -> Optional[float]:
    try:
        if x is None or x == "":
            return None
        return float(str(x).replace(",", ".").strip())
    except Exception:
        return None

# Casters por columna (aplicados antes de exportar)
TYPE_CASTERS: Dict[str, Callable[[Any], Any]] = {
    "Máquina": try_parse_int,
    "Variante": try_parse_int,
    "Frecuencia": try_parse_int,
    "AB": try_parse_int,
    "SD": try_parse_int,
    "CI": try_parse_int,
    "%EV": try_parse_float,
    "TE": try_parse_int,
}

# Clave compuesta para deduplicado
DEDUP_KEY = ("Folio", "Fecha", "Máquina")

def make_key(row: Dict[str, Any]) -> Tuple[Any, Any, Any]:
    return (row.get("Folio"), row.get("Fecha"), row.get("Máquina"))
