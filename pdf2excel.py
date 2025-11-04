# -*- coding: utf-8 -*-
from __future__ import annotations
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any
from schema import ROW_SCHEMA
from extractors import parse_pdf_any
from excel_io import append_and_dedup, create_new_excel

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
LOGGER = logging.getLogger("pdf2excel")

def process_pdfs(pdf_paths: List[str], use_ocr: bool) -> List[Dict[str, Any]]:
    all_rows: List[Dict[str, Any]] = []
    total = len(pdf_paths)
    for i, pdf in enumerate(pdf_paths, 1):
        rows, by_page, source = parse_pdf_any(pdf, use_ocr)
        count = sum(by_page) if by_page else len(rows)
        pages_info = ", ".join(f"p{idx+1}:{n}" for idx, n in enumerate(by_page)) if by_page else "-"
        LOGGER.info("[%-3s/%-3s] %s ➜ método=%s | filas=%s | por página: %s", i, total, pdf, source, count, pages_info)
        all_rows.extend(rows)
    return all_rows

def cmd_create(args: argparse.Namespace) -> None:
    rows = process_pdfs(args.pdf, args.ocr)
    if not rows:
        LOGGER.warning("No se detectaron filas en los PDF suministrados.")
    if not args.out:
        raise SystemExit("Debe indicar --out para 'create'.")
    path = create_new_excel(args.out, rows)
    LOGGER.info("Escritura completada en: %s (hoja 'Datos')", path)

def cmd_append(args: argparse.Namespace) -> None:
    rows = process_pdfs(args.pdf, args.ocr)
    if not rows:
        LOGGER.warning("No se detectaron filas en los PDF suministrados.")
    if not args.excel:
        raise SystemExit("Debe indicar --excel para 'append'.")
    path = append_and_dedup(args.excel, rows, args.out)
    LOGGER.info("Append + deduplicado completado en: %s (hoja 'Datos')", path)

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Extrae filas desde PDF y exporta a Excel (hoja 'Datos')")
    sub = p.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create", help="Crear nuevo Excel desde PDF(s)")
    p_create.add_argument("--pdf", nargs="+", required=True, help="Ruta(s) a PDF")
    p_create.add_argument("--out", required=True, help="Archivo .xlsx de salida")
    p_create.add_argument("--ocr", action="store_true", help="Habilita OCR si es escaneado")
    p_create.set_defaults(func=cmd_create)

    p_append = sub.add_parser("append", help="Agregar a Excel existente (sin duplicar)")
    p_append.add_argument("--excel", required=True, help="Excel base (.xlsx)")
    p_append.add_argument("--pdf", nargs="+", required=True, help="Ruta(s) a PDF")
    p_append.add_argument("--out", required=False, help="Archivo .xlsx destino (opcional)")
    p_append.add_argument("--ocr", action="store_true", help="Habilita OCR si es escaneado")
    p_append.set_defaults(func=cmd_append)

    return p

def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
