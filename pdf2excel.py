# -*- coding: utf-8 -*-
from __future__ import annotations
import argparse, logging
from typing import List, Dict, Any
from extractors import parse_pdf_any
from excel_io import append_and_dedup, create_new_excel

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
LOGGER = logging.getLogger("pdf2excel")

def process_pdfs(pdf_paths: List[str], use_ocr: bool) -> List[Dict[str, Any]]:
    all_rows: List[Dict[str, Any]] = []
    for pdf in pdf_paths:
        rows, by_page, source = parse_pdf_any(pdf, use_ocr)
        total = sum(by_page) if by_page else len(rows)
        LOGGER.info("PDF '%s' ➜ método=%s | filas=%s", pdf, source, total)
        all_rows.extend(rows)
    return all_rows

def cmd_create(args: argparse.Namespace) -> None:
    rows = process_pdfs(args.pdf, args.ocr)
    if not rows: LOGGER.warning("No se detectaron filas.")
    if not args.out: raise SystemExit("Debe indicar --out para 'create'.")
    path = create_new_excel(args.out, rows); LOGGER.info("Escritura: %s", path)

def cmd_append(args: argparse.Namespace) -> None:
    rows = process_pdfs(args.pdf, args.ocr)
    if not rows: LOGGER.warning("No se detectaron filas.")
    if not args.excel: raise SystemExit("Debe indicar --excel para 'append'.")
    path = append_and_dedup(args.excel, rows, args.out); LOGGER.info("Append + dedup: %s", path)

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="PDF → Excel (Datos)")
    sub = p.add_subparsers(dest="command", required=True)
    p_create = sub.add_parser("create", help="Crear nuevo Excel")
    p_create.add_argument("--pdf", nargs="+", required=True); p_create.add_argument("--out", required=True)
    p_create.add_argument("--ocr", action="store_true"); p_create.set_defaults(func=cmd_create)
    p_append = sub.add_parser("append", help="Agregar a Excel (sin duplicar)")
    p_append.add_argument("--excel", required=True); p_append.add_argument("--pdf", nargs="+", required=True)
    p_append.add_argument("--out"); p_append.add_argument("--ocr", action="store_true"); p_append.set_defaults(func=cmd_append)
    return p

def main():
    parser = build_parser(); args = parser.parse_args(); args.func(args)

if __name__ == "__main__": main()
