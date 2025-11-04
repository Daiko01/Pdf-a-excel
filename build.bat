@echo off
setlocal
REM Construcción recomendada: onefile, sin consola (GUI)
pyinstaller --noconfirm --clean --name "PDF-a-Excel" --windowed --onefile ^
  --collect-all pdfplumber --collect-all openpyxl ^
  --collect-all tabula --collect-all pytesseract --collect-all PIL ^
  gui.py
endlocal
