# -*- coding: utf-8 -*-
from __future__ import annotations
import threading, traceback
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pdfplumber

# Correct imports
from extractors import parse_pdf_any, parse_pdf_text
from excel_io import create_new_excel, append_and_dedup

APP_TITLE = "PDF ➜ Excel — GUI (corregido)"

class App(ttk.Frame):
    def __init__(self, master: tk.Tk):
        super().__init__(master)
        self.master.title(APP_TITLE); self.master.geometry("900x660")
        self.pack(fill="both", expand=True); self._build_ui()

    def _build_ui(self):
        pad = {"padx": 8, "pady": 6}
        frm_pdf = ttk.LabelFrame(self, text="PDF(s)"); frm_pdf.pack(fill="x", **pad)
        ttk.Button(frm_pdf, text="Agregar PDF(s)", command=self.on_add_pdfs).pack(side="left", **pad)
        ttk.Button(frm_pdf, text="Limpiar lista", command=self.on_clear_pdfs).pack(side="left", **pad)
        self.lst_pdfs = tk.Listbox(frm_pdf, height=6, selectmode=tk.EXTENDED); self.lst_pdfs.pack(fill="x", padx=8, pady=(0,8))

        frm_mode = ttk.LabelFrame(self, text="Modo"); frm_mode.pack(fill="x", **pad)
        self.mode = tk.StringVar(value="create")
        ttk.Radiobutton(frm_mode, text="Crear nuevo Excel (create)", variable=self.mode, value="create", command=self._toggle_mode).pack(anchor="w", **pad)
        ttk.Radiobutton(frm_mode, text="Agregar a Excel existente (append)", variable=self.mode, value="append", command=self._toggle_mode).pack(anchor="w", **pad)

        frm_paths = ttk.Frame(self); frm_paths.pack(fill="x", **pad)
        self.var_excel = tk.StringVar(); self.var_out = tk.StringVar(); self.var_ocr = tk.BooleanVar(value=False)
        self.lbl_excel = ttk.Label(frm_paths, text="Excel base (.xlsx):"); self.lbl_excel.grid(row=0, column=0, sticky="w", **pad)
        self.ent_excel = ttk.Entry(frm_paths, textvariable=self.var_excel); self.ent_excel.grid(row=0, column=1, sticky="ew", **pad)
        ttk.Button(frm_paths, text="Buscar...", command=self.on_choose_excel).grid(row=0, column=2, **pad)
        self.lbl_out = ttk.Label(frm_paths, text="Excel salida (.xlsx):"); self.lbl_out.grid(row=1, column=0, sticky="w", **pad)
        self.ent_out = ttk.Entry(frm_paths, textvariable=self.var_out); self.ent_out.grid(row=1, column=1, sticky="ew", **pad)
        ttk.Button(frm_paths, text="Guardar como...", command=self.on_choose_out).grid(row=1, column=2, **pad)
        ttk.Checkbutton(frm_paths, text="Habilitar OCR (PDF escaneado)", variable=self.var_ocr).grid(row=2, column=1, sticky="w", **pad)
        frm_paths.columnconfigure(1, weight=1)

        frm_actions = ttk.Frame(self); frm_actions.pack(fill="x", **pad)
        self.btn_run = ttk.Button(frm_actions, text="Ejecutar", command=self.on_run); self.btn_run.pack(side="left", **pad)
        self.btn_save_log = ttk.Button(frm_actions, text="Guardar log", command=self.on_save_log); self.btn_save_log.pack(side="left", **pad)

        self.pbar = ttk.Progressbar(self, mode="determinate"); self.pbar.pack(fill="x", **pad)
        self.progress_var = tk.StringVar(value="Listo.")
        self.lbl_progress = ttk.Label(self, textvariable=self.progress_var, anchor="w"); self.lbl_progress.pack(fill="x", padx=8)

        self.txt = tk.Text(self, height=18); self.txt.pack(fill="both", expand=True, padx=8, pady=(0,8))
        self._toggle_mode()

    def log(self, msg: str):
        self.txt.insert("end", msg + "\n"); self.txt.see("end"); self.txt.update_idletasks()

    def _toggle_mode(self):
        is_create = (self.mode.get() == "create")
        self.lbl_excel.configure(state=("disabled" if is_create else "normal"))
        self.ent_excel.configure(state=("disabled" if is_create else "normal"))

    def on_add_pdfs(self):
        paths = filedialog.askopenfilenames(title="Selecciona PDF(s)", filetypes=[("PDF","*.pdf")])
        for p in paths:
            if p and p not in self.lst_pdfs.get(0, "end"): self.lst_pdfs.insert("end", p)

    def on_clear_pdfs(self): self.lst_pdfs.delete(0, "end")
    def on_choose_excel(self):
        p = filedialog.askopenfilename(title="Excel base (.xlsx)", filetypes=[("Excel","*.xlsx")])
        if p: self.var_excel.set(p)
    def on_choose_out(self):
        p = filedialog.asksaveasfilename(title="Guardar Excel como...", defaultextension=".xlsx", filetypes=[("Excel","*.xlsx")])
        if p: self.var_out.set(p)
    def on_save_log(self):
        p = filedialog.asksaveasfilename(title="Guardar log", defaultextension=".txt", filetypes=[("Texto","*.txt")])
        if not p: return
        with open(p, "w", encoding="utf-8") as f: f.write(self.txt.get("1.0", "end"))

    def _count_total_pages(self, pdfs: list[str]) -> int:
        total = 0
        for pdf in pdfs:
            try:
                with pdfplumber.open(pdf) as doc:
                    total += len(doc.pages)
            except Exception:
                pass
        return max(total, 1)

    def on_run(self):
        pdfs = list(self.lst_pdfs.get(0, "end"))
        if not pdfs: messagebox.showwarning(APP_TITLE, "Agrega al menos un PDF."); return
        mode = self.mode.get(); out = self.var_out.get().strip(); base = self.var_excel.get().strip(); use_ocr = self.var_ocr.get()
        if mode == "create" and not out: messagebox.showwarning(APP_TITLE, "Para CREATE debes indicar 'Excel salida'."); return
        if mode == "append" and not base: messagebox.showwarning(APP_TITLE, "Para APPEND debes indicar 'Excel base'."); return
        self.btn_run.configure(state="disabled")
        threading.Thread(target=self._worker, args=(mode, pdfs, base, out, use_ocr), daemon=True).start()

    def _worker(self, mode: str, pdfs: list[str], base: str, out: str, use_ocr: bool):
        try:
            self.txt.delete("1.0", "end")
            total_pages = self._count_total_pages(pdfs)
            self.pbar.configure(maximum=total_pages, value=0)
            processed_pages = 0
            all_rows = []

            for pdf in pdfs:
                self.log(f"Procesando: {pdf}")
                rows, by_page = parse_pdf_text(pdf)
                for idx, n in enumerate(by_page, 1):
                    processed_pages += 1
                    self.pbar.configure(value=processed_pages)
                    self.progress_var.set(f"Páginas {processed_pages}/{total_pages} — {int(processed_pages/total_pages*100)}%")
                    self.log(f"  p{idx}: filas={n}")
                    self.update_idletasks()
                all_rows.extend(rows)

                if sum(by_page) == 0:
                    r2, _, src = parse_pdf_any(pdf, use_ocr)
                    if r2:
                        all_rows.extend(r2)
                        self.log(f"  fallback {src}: filas={len(r2)}")

            if not all_rows: self.log("No se detectaron filas en los PDF.")

            if mode == "create":
                out_path = out or str(Path.cwd() / "Reporte.xlsx")
                path = create_new_excel(out_path, all_rows); self.log(f"OK: {path}")
            else:
                path = append_and_dedup(base, all_rows, out or None); self.log(f"OK: {path}")

            self.progress_var.set("Completado ✅"); messagebox.showinfo(APP_TITLE, "Operación completada.")
        except Exception:
            self.progress_var.set("Error ❌"); self.log(traceback.format_exc()); messagebox.showerror(APP_TITLE, "Ocurrió un error.")
        finally:
            self.btn_run.configure(state="normal")

def main():
    root = tk.Tk(); style = ttk.Style(root)
    try: style.theme_use("clam")
    except Exception: pass
    App(root); root.mainloop()

if __name__ == "__main__":
    main()
