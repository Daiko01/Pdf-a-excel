# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, Callable, Any, Tuple, Optional
import re

ROW_SCHEMA = ["Fecha","Hora","Máquina","Patente","Folio","Variante","Frecuencia","Conductor","AB","SD","CI","%","EV","TE"]

FECHA_RE = re.compile(r"\b(?P<Fecha>\d{2}-\d{2}-\d{4})\b")
HORA_RE = re.compile(r"\b(?P<Hora>\d{2}:\d{2}:\d{2})\b")
PATENTE_RE = re.compile(r"\b[A-Z0-9]{5,7}\b")
PAT_COMBINED_RE = re.compile(r"\b([A-Z0-9]{2,4})[\s\-]?([A-Z0-9]{2,4})\b")

TRIPLE_PIPE_RE = re.compile(r"(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)")
PAIR_RE = re.compile(r"(\d+)\s*\|\s*(\d+)")
PCT_RE = re.compile(r"(\d{1,3}(?:[.,]\d+)?)\s*%")

ENTERO_1_3 = re.compile(r"\b\d{1,3}\b")
ENTERO_3 = re.compile(r"\b\d{3}\b")

def normalize_space(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

def try_parse_int(x: Any) -> Optional[int]:
    try:
        if x is None or x == "": return None
        return int(str(x).strip())
    except Exception: return None

def try_parse_float(x: Any) -> Optional[float]:
    try:
        if x is None or x == "": return None
        return float(str(x).replace(",", ".").strip())
    except Exception: return None

TYPE_CASTERS: Dict[str, Callable[[Any], Any]] = {
    "Máquina": try_parse_int, "Variante": try_parse_int, "Frecuencia": try_parse_int,
    "AB": try_parse_int, "SD": try_parse_int, "CI": try_parse_int,
    "%": try_parse_float, "EV": try_parse_int, "TE": try_parse_int,
}

DEDUP_KEY = ("Folio","Fecha","Máquina")
def make_key(row: Dict[str, Any]) -> Tuple[Any, Any, Any]:
    return (row.get("Folio"), row.get("Fecha"), row.get("Máquina"))
