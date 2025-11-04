# pdf2excel (fix) — Python 3.10+

Extracción robusta desde PDFs con encabezados cortados y filas partidas en 2 líneas. `%EV` separado de `EV|TE` correctamente.

## Uso CLI
```bash
python pdf2excel.py create --pdf "A.pdf" "B.pdf" --out "Reporte.xlsx"
python pdf2excel.py append --excel "Reporte.xlsx" --pdf "C.pdf"
```

## GUI
```bash
python gui.py
```
