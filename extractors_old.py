# -*- coding: utf-8 -*-
"""
extractors.py — Parser robusto PDF → filas
Arreglos:
- No se pierden horas: se delimita por (Fecha + Hora) juntos, incluso si están en líneas distintas.
- Patente 4 letras + 2 dígitos reconstruida aunque venga cortada (p.ej. "DTCB6" + salto + "6").
- Mantiene A→B→C (texto→tablas→OCR opcional).
"""
from __future__ import annotations
import logging
import re
from typing import List, Dict, Any, Tuple
from pathlib import Path

import pdfplumber

# Opcionales
try:
    import tabula  # type: ignore
except Exception:
    tabula = None

try:
    from pdf2image import convert_from_path  # type: ignore
    import pytesseract  # type: ignore
except Exception:
    convert_from_path = None
    pytesseract = None

LOGGER = logging.getLogger("extractors")

# ====== Regex y utilidades ======

def normalize_space(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

# Delimitador principal: FECHA + HORA (hora puede venir en la línea siguiente)
FECHA_HORA_RE = re.compile(
    r"(?P<Fecha>\d{2}-\d{2}-\d{4})\s*(?:\n|\s)+(?P<Hora>\d{2}:\d{2}:\d{2})"
)

TRIPLE_PIPE_RE = re.compile(r"(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)")  # AB | SD | CI
PAIR_RE        = re.compile(r"(\d+)\s*\|\s*(\d+)")               # EV | TE
PCT_RE         = re.compile(r"(\d{1,3}(?:[.,]\d+)?)\s*%")

# Folio flexible 12–14 dígitos (permitiendo separaciones)
FOLIO_FLEX_RE  = re.compile(r"((?:\d[\s-]?){12,16})")

def _tokens(s: str) -> List[str]:
    return normalize_space(s.replace("\n", " ")).split(" ")

# ===== Helpers =====

def _take_machine(tokens: List[str]) -> Tuple[int | None, int]:
    for i, t in enumerate(tokens[:5]):
        if t.isdigit() and 1 <= len(t) <= 3:
            return int(t), i + 1
    return None, 0

def _reconstruct_plate(tokens: List[str], start: int) -> Tuple[str | None, int]:
    """
    Patente: EXACTAMENTE 4 letras + 2 dígitos.
    - Busca patrón directo en una ventana antes del folio.
    - Si solo encuentra 4L+1D, intenta sumar el dígito suelto siguiente (antes del folio).
    """
    limit = min(len(tokens), start + 12)
    # cortar antes del folio (primer bloque largo de dígitos)
    for k in range(start, len(tokens)):
        if re.fullmatch(r"\d{10,}", tokens[k] or ""):
            limit = min(limit, k)
            break

    def cj(seq):  # clean join
        return re.sub(r"[^A-Za-z0-9]", "", " ".join(seq)).upper()

    # directo: 4L2D
    for i in range(start, limit):
        for j in range(i, min(i + 6, limit)):
            cand = cj(tokens[i:j + 1])
            m = re.search(r"[A-Z]{4}\d{2}\b", cand)
            if m:
                return m.group(0), j + 1

    # cortado: 4L1D + (dígito suelto)
    for i in range(start, limit):
        for j in range(i, min(i + 6, limit)):
            cand = cj(tokens[i:j + 1])
            m5 = re.search(r"([A-Z]{4}\d)\b$", cand)
            if m5 and j + 1 < limit and re.fullmatch(r"\d\b", tokens[j + 1] or ""):
                return (m5.group(1) + tokens[j + 1]).upper(), j + 2

    return None, start

def _take_folio(tokens: List[str], start: int) -> Tuple[str | None, int]:
    digs = ""
    i = start
    while i < len(tokens) and re.fullmatch(r"\d{1,}", tokens[i] or ""):
        digs += tokens[i]
        if 12 <= len(digs) <= 14:
            return digs, i + 1
        if len(digs) > 14:
            break
        i += 1
    # fallback token largo
    for j in range(start, min(start + 8, len(tokens))):
        if re.fullmatch(r"\d{12,16}", tokens[j] or ""):
            cand = re.sub(r"\D+", "", tokens[j])
            if 12 <= len(cand) <= 14:
                return cand, j + 1
    return None, start

def _take_variant_freq(tokens: List[str], start: int) -> Tuple[int | None, int | None, int]:
    var = freq = None
    i = start
    for k in range(i, min(i + 6, len(tokens))):
        if re.fullmatch(r"\d{3}", tokens[k] or ""):
            var = int(tokens[k]); i = k + 1; break
    for k in range(i, min(i + 6, len(tokens))):
        if re.fullmatch(r"\d{1,3}", tokens[k] or ""):
            freq = int(tokens[k]); i = k + 1; break
    return var, freq, i

# ===== Parser de un bloque (con Fecha y Hora provistas) =====

def _parse_block(block: str, fecha: str, hora: str | None) -> Dict[str, Any] | None:
    # Une dígitos partidos por saltos de línea (ayuda a folio, %, EV/TE)
    b = re.sub(r"(\d)\s*\n\s*(\d)", r"\1\2", block)
    b = normalize_space(b)

    # Tomamos tokens DESPUÉS del match fecha/hora original (ya vienen en 'block')
    tokens = _tokens(b)

    # Máquina
    maquina, pos = _take_machine(tokens)

    # Patente
    patente, pos = _reconstruct_plate(tokens, pos)

    # Folio, Variante, Frecuencia
    folio,   pos = _take_folio(tokens, pos)
    variante, frecuencia, pos = _take_variant_freq(tokens, pos)

    # Conductor: todo lo que hay antes de AB|SD|CI
    ab = sd = ci = None
    conductor = None
    m_tri = TRIPLE_PIPE_RE.search(b)
    if m_tri:
        left = b[:m_tri.start()]
        conductor = normalize_space(left) or None
        try:
            ab, sd, ci = map(int, m_tri.groups())
        except Exception:
            pass

    # % y EV|TE
    pct = ev = te = None
    m_pct = PCT_RE.search(b)
    zone = b[m_pct.end():] if m_pct else b
    if m_pct:
        try: pct = float(m_pct.group(1).replace(",", "."))
        except Exception: pct = None
    m_pair = PAIR_RE.search(zone)
    if m_pair:
        try: ev = int(m_pair.group(1))
        except Exception: ev = None
        try: te = int(m_pair.group(2))
        except Exception: te = None

    row = {
        "Fecha": fecha, "Hora": hora, "Máquina": maquina,
        "Patente": patente, "Folio": folio,
        "Variante": variante, "Frecuencia": frecuencia,
        "Conductor": conductor, "AB": ab, "SD": sd, "CI": ci, "%": pct, "EV": ev, "TE": te,
    }
    if not row["Folio"] or not row["Fecha"]:
        return None
    return row

# ===== Intento A: texto =====

def parse_pdf_text(pdf_path: str | Path) -> Tuple[List[Dict[str, Any]], List[int]]:
    rows: List[Dict[str, Any]] = []
    by_page: List[int] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
            # delimitar por (Fecha + Hora) JUNTOS para no perder la hora
            matches = list(FECHA_HORA_RE.finditer(text))
            if not matches:
                by_page.append(0)
                continue
            # construir bloques desde cada match hasta el siguiente
            idxs = [m.start() for m in matches] + [len(text)]
            page_rows = 0
            for i, m in enumerate(matches):
                block = text[idxs[i]: idxs[i+1]]
                fecha = m.group("Fecha")
                hora  = m.group("Hora")
                r = _parse_block(block[m.end():], fecha, hora)  # pasa solo el tail tras fecha/hora
                if r:
                    rows.append(r); page_rows += 1
            by_page.append(page_rows)
    return rows, by_page

# ===== Intento B: tabula =====

def parse_pdf_tabula(pdf_path: str | Path) -> Tuple[List[Dict[str, Any]], List[int]]:
    if tabula is None:
        return [], []
    try:
        dfs = tabula.read_pdf(str(pdf_path), pages="all", lattice=True, multiple_tables=True) or []
        if not dfs:
            dfs = tabula.read_pdf(str(pdf_path), pages="all", stream=True, multiple_tables=True) or []
    except Exception:
        return [], []
    rows: List[Dict[str, Any]] = []
    for df in dfs:
        for _, r in df.iterrows():
            line = " ".join(str(v) for v in r.to_list())
            # Buscar fecha+hora dentro de la línea
            m = FECHA_HORA_RE.search(line)
            if not m:
                continue
            tail = line[m.end():]
            rr = _parse_block(tail, m.group("Fecha"), m.group("Hora"))
            if rr:
                rows.append(rr)
    return rows, []

# ===== Intento C: OCR =====

def parse_pdf_ocr(pdf_path: str | Path) -> Tuple[List[Dict[str, Any]], List[int]]:
    if convert_from_path is None or pytesseract is None:
        return [], []
    images = convert_from_path(str(pdf_path), dpi=300)
    text = "\n".join(__import__('pytesseract').image_to_string(img, lang="spa") for img in images)
    matches = list(FECHA_HORA_RE.finditer(text))
    if not matches:
        return [], []
    idxs = [m.start() for m in matches] + [len(text)]
    rows: List[Dict[str, Any]] = []
    for i, m in enumerate(matches):
        block = text[idxs[i]: idxs[i+1]]
        r = _parse_block(block[m.end():], m.group("Fecha"), m.group("Hora"))
        if r:
            rows.append(r)
    return rows, [len(rows)]

# ===== Orquestador =====

def parse_pdf_any(pdf_path: str | Path, use_ocr: bool = False) -> Tuple[List[Dict[str, Any]], List[int], str]:
    rows, by_page = parse_pdf_text(pdf_path)
    if rows:
        return rows, by_page, "text"
    rows, by_page = parse_pdf_tabula(pdf_path)
    if rows:
        return rows, by_page, "tabula"
    if use_ocr:
        rows, by_page = parse_pdf_ocr(pdf_path)
        if rows:
            return rows, by_page, "ocr"
    return [], [], "none"
