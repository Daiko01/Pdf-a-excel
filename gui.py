# -*- coding: utf-8 -*-
from __future__ import annotations
import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from extractors import parse_pdf_any
from excel_io import create_new_excel, append_and_dedup

APP_TITLE = "PDF ➜ Excel — GUI"

class App(ttk.Frame):
    def __init__(self, master: tk.Tk):
        super().__init__(master)
        self.master.title(APP_TITLE)
        self.master.geometry("880x640")
        self.pack(fill="both", expand=True)
        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 8, "pady": 6}

        frm_pdf = ttk.LabelFrame(self, text="PDF(s)")
        frm_pdf.pack(fill="x", **pad)
        ttk.Button(frm_pdf, text="Agregar PDF(s)", command=self.on_add_pdfs).pack(side="left", **pad)
        ttk.Button(frm_pdf, text="Limpiar lista", command=self.on_clear_pdfs).pack(side="left", **pad)
        self.lst_pdfs = tk.Listbox(frm_pdf, height=5, selectmode=tk.EXTENDED)
        self.lst_pdfs.pack(fill="x", padx=8, pady=(0,8))

        frm_mode = ttk.LabelFrame(self, text="Modo")
        frm_mode.pack(fill="x", **pad)
        self.mode = tk.StringVar(value="create")
        ttk.Radiobutton(frm_mode, text="Crear nuevo Excel (create)", variable=self.mode, value="create", command=self._toggle_mode).pack(anchor="w", **pad)
        ttk.Radiobutton(frm_mode, text="Agregar a Excel existente (append)", variable=self.mode, value="append", command=self._toggle_mode).pack(anchor="w", **pad)

        frm_paths = ttk.Frame(self)
        frm_paths.pack(fill="x", **pad)

        self.var_excel = tk.StringVar()
        self.var_out = tk.StringVar()
        self.var_ocr = tk.BooleanVar(value=False)

        self.lbl_excel = ttk.Label(frm_paths, text="Excel base (.xlsx):")
        self.lbl_excel.grid(row=0, column=0, sticky="w", **pad)
        self.ent_excel = ttk.Entry(frm_paths, textvariable=self.var_excel)
        self.ent_excel.grid(row=0, column=1, sticky="ew", **pad)
        ttk.Button(frm_paths, text="Buscar...", command=self.on_choose_excel).grid(row=0, column=2, **pad)

        self.lbl_out = ttk.Label(frm_paths, text="Excel salida (.xlsx):")
        self.lbl_out.grid(row=1, column=0, sticky="w", **pad)
        self.ent_out = ttk.Entry(frm_paths, textvariable=self.var_out)
        self.ent_out.grid(row=1, column=1, sticky="ew", **pad)
        ttk.Button(frm_paths, text="Guardar como...", command=self.on_choose_out).grid(row=1, column=2, **pad)

        ttk.Checkbutton(frm_paths, text="Habilitar OCR (PDF escaneado)", variable=self.var_ocr).grid(row=2, column=1, sticky="w", **pad)
        frm_paths.columnconfigure(1, weight=1)

        frm_actions = ttk.Frame(self)
        frm_actions.pack(fill="x", **pad)
        self.btn_run = ttk.Button(frm_actions, text="Ejecutar", command=self.on_run)
        self.btn_run.pack(side="left", **pad)
        self.btn_save_log = ttk.Button(frm_actions, text="Guardar log", command=self.on_save_log)
        self.btn_save_log.pack(side="left", **pad)

        self.pbar = ttk.Progressbar(self, mode="determinate")
        self.pbar.pack(fill="x", **pad)

        self.txt = tk.Text(self, height=18)
        self.txt.pack(fill="both", expand=True, padx=8, pady=(0,8))

        self._toggle_mode()

    def log(self, msg: str):
        self.txt.insert("end", msg + "\n")
        self.txt.see("end")
        self.txt.update_idletasks()

    def error(self, msg: str):
        self.log("ERROR: " + msg)

    def _toggle_mode(self):
        mode = self.mode.get()
        is_create = (mode == "create")
        self.lbl_excel.configure(state=("disabled" if is_create else "normal"))
        self.ent_excel.configure(state=("disabled" if is_create else "normal"))
        self.lbl_out.configure(state="normal")
        self.ent_out.configure(state="normal")

    def on_add_pdfs(self):
        paths = filedialog.askopenfilenames(title="Selecciona PDF(s)", filetypes=[("PDF","*.pdf")])
        for p in paths:
            if p and p not in self.lst_pdfs.get(0, "end"):
                self.lst_pdfs.insert("end", p)

    def on_clear_pdfs(self):
        self.lst_pdfs.delete(0, "end")

    def on_choose_excel(self):
        p = filedialog.askopenfilename(title="Excel base (.xlsx)", filetypes=[("Excel","*.xlsx")])
        if p:
            self.var_excel.set(p)

    def on_choose_out(self):
        p = filedialog.asksaveasfilename(title="Guardar Excel como...", defaultextension=".xlsx", filetypes=[("Excel","*.xlsx")])
        if p:
            self.var_out.set(p)

    def on_save_log(self):
        p = filedialog.asksaveasfilename(title="Guardar log", defaultextension=".txt", filetypes=[("Texto","*.txt")])
        if not p:
            return
        with open(p, "w", encoding="utf-8") as f:
            f.write(self.txt.get("1.0", "end"))
        messagebox.showinfo(APP_TITLE, f"Log guardado en:\n{p}")

    def on_run(self):
        pdfs = list(self.lst_pdfs.get(0, "end"))
        if not pdfs:
            messagebox.showwarning(APP_TITLE, "Agrega al menos un PDF.")
            return
        mode = self.mode.get()
        out = self.var_out.get().strip()
        base = self.var_excel.get().strip()
        use_ocr = self.var_ocr.get()

        if mode == "create" and not out:
            messagebox.showwarning(APP_TITLE, "Para CREATE debes indicar 'Excel salida'.")
            return
        if mode == "append" and not base:
            messagebox.showwarning(APP_TITLE, "Para APPEND debes indicar 'Excel base'.")
            return

        self.btn_run.configure(state="disabled")
        t = threading.Thread(target=self._worker, args=(mode, pdfs, base, out, use_ocr), daemon=True)
        t.start()

    def _worker(self, mode: str, pdfs: list[str], base: str, out: str, use_ocr: bool):
        try:
            self.txt.delete("1.0", "end")
            self.log(f"Modo: {mode} | OCR: {use_ocr}")
            self.pbar.configure(maximum=len(pdfs), value=0)

            all_rows = []
            for i, pdf in enumerate(pdfs, 1):
                self.log(f"Procesando: {pdf}")
                rows, by_page, source = parse_pdf_any(pdf, use_ocr)
                total = sum(by_page) if by_page else len(rows)
                pages_info = ", ".join(f"p{idx+1}:{n}" for idx, n in enumerate(by_page)) if by_page else "-"
                self.log(f"  método={source} | filas={total} | por página: {pages_info}")
                all_rows.extend(rows)
                self.pbar.configure(value=i)

            if not all_rows:
                self.log("No se detectaron filas en los PDF suministrados.")

            if mode == "create":
                out_path = out or str(Path.cwd() / "Reporte_Fenur.xlsx")
                path = create_new_excel(out_path, all_rows)
                self.log(f"OK: Escritura completada en: {path} (hoja 'Datos')")
            else:
                out_path = out if out else None
                path = append_and_dedup(base, all_rows, out_path)
                self.log(f"OK: Append + deduplicado en: {path} (hoja 'Datos')")

            messagebox.showinfo(APP_TITLE, "Operación completada.")
        except Exception:
            import traceback
            err = traceback.format_exc()
            self.error(err)
            messagebox.showerror(APP_TITLE, "Ocurrió un error. Revisa el log.")
        finally:
            self.btn_run.configure(state="normal")

def main():
    root = tk.Tk()
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass
    App(root)
    root.mainloop()

if __name__ == "__main__":
    main()
