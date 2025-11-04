# Construir instalador .EXE (Windows) con PyInstaller

Sigue estos pasos exactamente (Windows 10/11):

## 1) Requisitos
- Python 3.10 o superior instalado (recomendado 64-bit).
- Pip actualizado.
- (Opcional) Java si vas a usar `tabula-py` (solo necesario si usas el modo Tabula en PDFs tipo tabla).

## 2) Preparar entorno
Abre **PowerShell** o **CMD** en la carpeta del proyecto `pdf2excel` (donde está `gui.py`). Luego:

```bat
python -m venv .venv
.\.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
```

> Nota: Si no usarás OCR/Tabula, puedes omitir instalar esas dependencias opcionales del `requirements.txt`.

## 3) Construir el .exe (recomendado: onefile, sin consola)
Desde la misma terminal activada:
```bat
build.bat
```
Esto ejecuta internamente:
```bat
pyinstaller --noconfirm --clean --name "PDF-a-Excel" --windowed --onefile ^
  --collect-all pdfplumber --collect-all openpyxl ^
  --collect-all tabula --collect-all pytesseract --collect-all PIL ^
  gui.py
```
- El ejecutable quedará en: `dist\PDF-a-Excel.exe`.

> Si no quieres incluir dependencias opcionales, edita `build.bat` y borra las líneas `--collect-all tabula`, `--collect-all pytesseract`, `--collect-all PIL`.

## 4) (Opcional) Versión con consola para depuración
Si quieres ver logs/tracebacks en una ventana de consola:
```bat
build_console.bat
```
Genera `dist\PDF-a-Excel-console.exe` (consola visible).

## 5) Probar el ejecutable
- Copia `PDF-a-Excel.exe` a una carpeta fuera del proyecto y ejecútalo.
- Carga tus PDFs y genera el Excel.
- Si usas OCR, asegúrate de tener **Tesseract** instalado en Windows y en PATH.
- Si usas Tabula, asegúrate de tener **Java** instalado.

## 6) Problemas comunes
- **Antivirus marca falso positivo**: es típico con ejecutables “onefile”. Puedes:
  - Usar el modo `onedir` (edita el `build.bat`: quita `--onefile`), o
  - Firmar digitalmente el .exe si dispones de certificado, o
  - Añadir una exclusión en tu antivirus para pruebas internas.
- **Faltan recursos/librerías**: ejecuta con consola (`build_console.bat`) y revisa errores. Luego añade `--collect-all paquete` a `build.bat`.

## 7) Atajos y distribución
- Para crear un acceso directo, haz clic derecho en `PDF-a-Excel.exe` → *Crear acceso directo*.
- Puedes comprimir la carpeta `dist\` y compartir el zip a tus usuarios.

¡Listo! Cualquier duda, pásame el error exacto y te digo qué flag agregar al PyInstaller.
