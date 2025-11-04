@echo off
setlocal
REM Construcción con consola para depuración
pyinstaller --noconfirm --clean --name "PDF-a-Excel-console" --console --onefile ^
  --collect-all pdfplumber --collect-all openpyxl ^
  --collect-all tabula --collect-all pytesseract --collect-all PIL ^
  gui.py
endlocal
