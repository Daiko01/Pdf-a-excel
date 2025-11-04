# -*- coding: utf-8 -*-
from __future__ import annotations
import logging
from typing import List, Dict, Any, Tuple
from pathlib import Path
import re
import pdfplumber

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

from schema import (
    ROW_SCHEMA,
    FECHA_RE,
    HORA_RE,
    PATENTE_RE,
    TRIPLE_PIPE_RE,
    PAIR_RE,
    PCT_EV_RE,
    ENTERO_1_3,
    ENTERO_3,
    normalize_space,
)

LOGGER = logging.getLogger("extractors")

HEADER_NOISE = re.compile(
    r"(?:^|#)\s*Fecha\s+M[aá]qui?\s*na\s+Paten\s*te.*?(?:AB\s*\|\s*SD.*?TE)",
    flags=re.IGNORECASE | re.DOTALL,
)

def _split_blocks_by_fecha(text: str) -> List[str]:
    """Divide el texto por cada aparición de una fecha dd-mm-aaaa (sin hora)."""
    idxs = [m.start() for m in FECHA_RE.finditer(text)]
    blocks: List[str] = []
    if not idxs:
        return blocks
    idxs.append(len(text))
    for i in range(len(idxs) - 1):
        block = text[idxs[i]: idxs[i + 1]]
        blocks.append(block)
    return blocks

def _parse_block(block: str) -> Dict[str, Any] | None:
    # Limpieza básica: unir espacios y quitar basura de encabezados
    b = HEADER_NOISE.sub(" ", block)
    b = b.replace("\n", " ")
    b = normalize_space(b)

    m_fecha = FECHA_RE.search(b)
    if not m_fecha:
        return None
    fecha = m_fecha.group("Fecha")
    tail = b[m_fecha.end():].strip()

    # Máquina: primer entero 1–3 dígitos tras la fecha
    m_ma = ENTERO_1_3.search(tail)
    maquina = int(m_ma.group()) if m_ma else None

    # Patente
    m_pat = PATENTE_RE.search(tail)
    patente = m_pat.group() if m_pat else None

    # Hora: aparece en otra línea del bloque
    m_h = HORA_RE.search(b)
    hora = m_h.group("Hora") if m_h else None

    # AB | SD | CI
    ab = sd = ci = None
    m_triple = TRIPLE_PIPE_RE.search(b)
    if m_triple:
        ab, sd, ci = map(int, m_triple.groups())

    # %EV
    pct_ev = None
    m_pct = PCT_EV_RE.search(b)
    if m_pct:
        try:
            pct_ev = float(m_pct.group(1).replace(",", "."))
        except Exception:
            pct_ev = None

    # EV | TE (buscar **después** del %EV)
    te = None
    if m_pct:
        after_pct = b[m_pct.end():]
        m_pair = PAIR_RE.search(after_pct)
        if m_pair:
            try:
                te = int(m_pair.group(2))
            except Exception:
                te = None

    # Variante y Frecuencia (tras el prefijo del folio)
    variante = None
    frecuencia = None

    # Folio: el PDF parte el folio en prefijo (9-10 dígitos) cerca de la patente
    # y un sufijo de 4 dígitos cerca del final del bloque. Los unimos.
    folio = None
    suffix_pos = None
    if m_pat:
        after_pat = tail[m_pat.end():]
        m_prefix = re.search(r"\b\d{7,10}\b", after_pat)  # prefijo
        if m_prefix:
            folio_prefix = m_prefix.group()
            after_prefix = after_pat[m_prefix.end():]
            m_var = ENTERO_3.search(after_prefix)
            if m_var:
                try:
                    variante = int(m_var.group())
                except Exception:
                    variante = None
                after_var = after_prefix[m_var.end():]
                m_freq = ENTERO_1_3.search(after_var)
                if m_freq:
                    try:
                        frecuencia = int(m_freq.group())
                    except Exception:
                        frecuencia = None

            # sufijo: último número de 4 dígitos del bloque
            for m in re.finditer(r"\b\d{4}\b", b):
                folio_suffix = m.group()
                suffix_pos = m.start()
            if suffix_pos is not None:
                folio = f"{folio_prefix}{folio_suffix}"

    # Conductor: entre frecuencia y el bloque AB|SD|CI, y agregar cola después del sufijo del folio
    conductor = None
    if m_triple:
        left = b[:m_triple.start()]
        anchor = m_fecha.end()
        if frecuencia is not None:
            m_find = re.search(rf"\b{frecuencia}\b", left)
            if m_find:
                anchor = m_find.end()
        conductor = normalize_space(left[anchor:])

    # Apéndice del apellido que queda tras el sufijo del folio (suelen venir luego)
    if suffix_pos is not None:
        tail_after = b[suffix_pos + 4:]
        extra_words = re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]+", tail_after)
        if extra_words:
            extra = " ".join(extra_words)
            conductor = (f"{conductor} {extra}".strip()) if conductor else extra

    row = {
        "Fecha": fecha,
        "Hora": hora,
        "Máquina": maquina,
        "Patente": patente,
        "Folio": folio,
        "Variante": variante,
        "Frecuencia": frecuencia,
        "Conductor": conductor,
        "AB": ab,
        "SD": sd,
        "CI": ci,
        "%EV": pct_ev,
        "TE": te,
    }
    if not row["Folio"] or not row["Fecha"]:
        return None
    return row

# -------------------------------
# Intento A: Texto con pdfplumber
# -------------------------------
def parse_pdf_text(pdf_path: str | Path) -> Tuple[List[Dict[str, Any]], List[int]]:
    pdf_path = str(pdf_path)
    rows: List[Dict[str, Any]] = []
    rows_per_page: List[int] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
            blocks = _split_blocks_by_fecha(text)
            page_rows = 0
            for b in blocks:
                r = _parse_block(b)
                if r:
                    rows.append(r)
                    page_rows += 1
            rows_per_page.append(page_rows)
    return rows, rows_per_page

# -------------------------------
# Intento B: Tabula (tablas)
# -------------------------------
def parse_pdf_tabula(pdf_path: str | Path) -> Tuple[List[Dict[str, Any]], List[int]]:
    if tabula is None:
        return [], []
    try:
        dfs = tabula.read_pdf(str(pdf_path), pages="all", lattice=True, multiple_tables=True)
        if not dfs:
            dfs = tabula.read_pdf(str(pdf_path), pages="all", stream=True, multiple_tables=True)
    except Exception:
        return [], []

    rows: List[Dict[str, Any]] = []
    for df in dfs or []:
        # Intento conservador: concatenar fila como texto y reusar parser por bloque
        for _, r in df.iterrows():
            try:
                line_txt = " ".join(str(v) for v in r.to_list())
            except Exception:
                continue
            parsed = _parse_block(line_txt)
            if parsed:
                rows.append(parsed)
    return rows, []

# -------------------------------
# Intento C: OCR (opcional)
# -------------------------------
def parse_pdf_ocr(pdf_path: str | Path) -> Tuple[List[Dict[str, Any]], List[int]]:
    if convert_from_path is None or pytesseract is None:
        return [], []
    images = convert_from_path(str(pdf_path), dpi=300)
    all_text = []
    for img in images:
        txt = pytesseract.image_to_string(img, lang="spa")
        all_text.append(txt)
    text = "\n".join(all_text)
    blocks = _split_blocks_by_fecha(text)
    rows: List[Dict[str, Any]] = []
    for b in blocks:
        r = _parse_block(b)
        if r:
            rows.append(r)
    # Conteo por página (aprox. uniforme)
    per_page = max(1, len(rows) // max(1, len(images)))
    rows_per_page = [per_page] * len(images)
    return rows, rows_per_page

# -------------------------------
# Orquestador: A → B → C
# -------------------------------
def parse_pdf_any(pdf_path: str | Path, use_ocr: bool = False) -> Tuple[List[Dict[str, Any]], List[int], str]:
    rows, by_page = parse_pdf_text(pdf_path)
    if rows:
        return rows, by_page, "text"
    b_rows, b_by = parse_pdf_tabula(pdf_path)
    if b_rows:
        return b_rows, b_by, "tabula"
    if use_ocr:
        o_rows, o_by = parse_pdf_ocr(pdf_path)
        if o_rows:
            return o_rows, o_by, "ocr"
    return [], [], "none"
