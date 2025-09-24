# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
import pandas as pd
from datetime import datetime
import calendar as _cal

from app.io_csv import escribir_detalle, escribir_resumen
from app.reglas import cargar_reglas
from app.tarifas import CargadorTarifas
from app.calendario import CalendarioFestivos
from app.calculo import calcular_importes

MAX_ROWS = 24
GRADOS = ["R1", "R2", "R3", "R4", "R5"]

# Definimos todas las columnas (incluye el # de fila)
# width = ancho en caracteres para alinear widgets y encabezados
COLS = [
    {"key": "_idx",       "title": "#",                       "width": 3},   # solo etiqueta
    {"key": "dia_ini",    "title": "Día inicio",              "width": 10},  # combo
    {"key": "hora_ini",   "title": "Hora inicio (00–23)",     "width": 16},  # combo
    {"key": "dia_fin",    "title": "Día fin",                 "width": 10},  # combo
    {"key": "hora_fin",   "title": "Hora fin (00–23)",        "width": 16},  # combo
    {"key": "municipio",  "title": "Municipio",               "width": 20},  # entry
    {"key": "grado",      "title": "Grado (R1..R5)",          "width": 14},  # combo
    {"key": "observ",     "title": "Observaciones",           "width": 26},  # entry
    {"key": "_del",       "title": "",                        "width": 8},   # botón borrar
]

class GuardiaGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Guardias MIR — Cálculo de importe")
        self.geometry("1200x720")
        self.resizable(True, True)

        self.anio_var = tk.StringVar(value="2025")
        self.mes_var = tk.StringVar(value="9")
        self.municipio_default_var = tk.StringVar(value="Sevilla")
        self.salida_dir = tk.StringVar(value=str(Path("output").resolve()))

        self._build_header()
        self._build_table()
        self._build_buttons()

    # ---------- Barra superior ----------
    def _build_header(self):
        frm = ttk.Frame(self, padding=8)
        frm.pack(fill=tk.X)
        ttk.Label(frm, text="Año:").pack(side=tk.LEFT)
        anio_entry = ttk.Entry(frm, textvariable=self.anio_var, width=6)
        anio_entry.pack(side=tk.LEFT, padx=(4,12))
        ttk.Label(frm, text="Mes:").pack(side=tk.LEFT)
        mes_entry = ttk.Entry(frm, textvariable=self.mes_var, width=4)
        mes_entry.pack(side=tk.LEFT, padx=(4,12))

        def _refresh_days(_e=None):
            try:
                y = int(self.anio_var.get())
                m = int(self.mes_var.get())
                mdays = _cal.monthrange(y, m)[1]
            except Exception:
                mdays = 31
            self.dias_mes = [f"{d:02d}" for d in range(1, mdays+1)]
            for rw in getattr(self, "rows", []):
                if "dia_ini" in rw: rw["dia_ini"]["cb"]["values"] = self.dias_mes
                if "dia_fin" in rw: rw["dia_fin"]["cb"]["values"] = self.dias_mes

        anio_entry.bind("<FocusOut>", _refresh_days)
        mes_entry.bind("<FocusOut>", _refresh_days)

        ttk.Label(frm, text="Municipio por defecto:").pack(side=tk.LEFT)
        ttk.Entry(frm, textvariable=self.municipio_default_var, width=18).pack(side=tk.LEFT, padx=(4,12))

        ttk.Label(frm, text="Salida:").pack(side=tk.LEFT, padx=(8,0))
        out_entry = ttk.Entry(frm, textvariable=self.salida_dir, width=60)
        out_entry.pack(side=tk.LEFT, padx=(4,4))
        ttk.Button(frm, text="Cambiar...", command=self._select_output_dir).pack(side=tk.LEFT)

        _refresh_days()

    # ---------- Tabla alineada ----------
    def _build_table(self):
        wrap = ttk.Frame(self, padding=(8,0,8,8))
        wrap.pack(fill=tk.BOTH, expand=True)

        # Encabezados
        self.header = ttk.Frame(wrap)
        self.header.pack(fill=tk.X)
        for c, col in enumerate(COLS):
            lbl = ttk.Label(self.header, text=col["title"], anchor="w")
            lbl.grid(row=0, column=c, sticky="ew", padx=2, pady=(0,4))
            self.header.grid_columnconfigure(c, weight=1, uniform="cols")

        # Scrollable body
        self.canvas = tk.Canvas(wrap, borderwidth=0, highlightthickness=0)
        self.scroll_y = ttk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        self.rows_frame = ttk.Frame(self.canvas)

        self.rows_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.rows_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scroll_y.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scroll_y.pack(side="right", fill="y")

        # Alinear columnas del body igual que el header
        for c, col in enumerate(COLS):
            self.rows_frame.grid_columnconfigure(c, weight=1, uniform="cols")

        # Inicializar filas
        self.rows = []
        self.add_row()

    def _build_buttons(self):
        frm = ttk.Frame(self, padding=8)
        frm.pack(fill=tk.X)
        ttk.Button(frm, text="Añadir fila", command=self.add_row).pack(side=tk.LEFT)
        ttk.Button(frm, text="Cargar CSV...", command=self.load_csv).pack(side=tk.LEFT, padx=(8,0))
        ttk.Button(frm, text="Guardar CSV...", command=self.save_csv).pack(side=tk.LEFT, padx=(8,0))
        ttk.Button(frm, text="Calcular", command=self.run_calc).pack(side=tk.RIGHT)

    def _select_output_dir(self):
        d = filedialog.askdirectory(title="Seleccionar carpeta de salida")
        if d:
            self.salida_dir.set(d)

    # ---------- Filas ----------
    def add_row(self, preset=None):
        if len(self.rows) >= MAX_ROWS:
            messagebox.showwarning("Límite", f"Máximo {MAX_ROWS} guardias.")
            return

        r = len(self.rows)  # índice
        row_widgets = {}

        # Columna 0: índice
        ttk.Label(self.rows_frame, text=str(r+1)).grid(row=r, column=0, sticky="w", padx=2, pady=2)

        # Helpers para crear widgets con mismo ancho lógico que encabezados
        def add_combo(col_idx, values, value=""):
            var = tk.StringVar(value=value)
            cb = ttk.Combobox(self.rows_frame, textvariable=var, values=values,
                              width=COLS[col_idx]["width"], state="readonly")
            cb.grid(row=r, column=col_idx, sticky="w", padx=2, pady=2)
            return {"var": var, "cb": cb}

        def add_entry(col_idx, value=""):
            var = tk.StringVar(value=value)
            ent = ttk.Entry(self.rows_frame, textvariable=var, width=COLS[col_idx]["width"])
            ent.grid(row=r, column=col_idx, sticky="w", padx=2, pady=2)
            return var

        # 1: dia_ini, 2: hora_ini, 3: dia_fin, 4: hora_fin
        row_widgets["dia_ini"]  = add_combo(1, getattr(self, "dias_mes", [f"{d:02d}" for d in range(1,32)]),
                                            (preset.get("dia_ini","") if preset else ""))
        row_widgets["hora_ini"] = add_combo(2, [f"{h:02d}" for h in range(24)],
                                            (preset.get("hora_ini","") if preset else ""))
        row_widgets["dia_fin"]  = add_combo(3, getattr(self, "dias_mes", [f"{d:02d}" for d in range(1,32)]),
                                            (preset.get("dia_fin","") if preset else ""))
        row_widgets["hora_fin"] = add_combo(4, [f"{h:02d}" for h in range(24)],
                                            (preset.get("hora_fin","") if preset else ""))

        # 5: municipio, 6: grado, 7: observaciones
        row_widgets["municipio"] = add_entry(5, (preset.get("municipio","") if preset else ""))
        var_gr = tk.StringVar(value=(preset.get("grado","") if preset else ""))
        cb_gr = ttk.Combobox(self.rows_frame, textvariable=var_gr, values=GRADOS,
                             width=COLS[6]["width"], state="readonly")
        cb_gr.grid(row=r, column=6, sticky="w", padx=2, pady=2)
        row_widgets["grado"] = var_gr
        row_widgets["observaciones"] = add_entry(7, (preset.get("observaciones","") if preset else ""))

        # 8: botón borrar
        btn = ttk.Button(self.rows_frame, text="Borrar", width=COLS[8]["width"], command=lambda i=r: self.delete_row(i))
        btn.grid(row=r, column=8, sticky="w", padx=2, pady=2)
        row_widgets["_btn"] = btn

        self.rows.append(row_widgets)

    def delete_row(self, idx):
        if idx < 0 or idx >= len(self.rows):
            return
        # Re-render completo para mantener índices y alineación
        for child in list(self.rows_frame.children.values()):
            child.destroy()
        del self.rows[idx]
        tmp = self.rows[:]
        self.rows = []
        for preset in tmp:
            vals = {}
            # Convertir a valores simples
            for k, v in preset.items():
                if k.startswith("_"):
                    continue
                if isinstance(v, dict) and "var" in v:
                    vals[k] = v["var"].get()
                elif hasattr(v, "get"):
                    vals[k] = v.get()
                else:
                    vals[k] = ""
            self.add_row(preset=vals)

    # ---------- CSV <-> DF ----------
    def rows_to_df(self):
        rows = []
        try:
            y = int(self.anio_var.get())
            m = int(self.mes_var.get())
        except Exception:
            messagebox.showerror("Error", "Año/Mes inválidos.")
            return pd.DataFrame(columns=["inicio_datetime","fin_datetime","municipio","grado","observaciones"])

        for rw in self.rows:
            dia_ini  = rw["dia_ini"]["var"].get().strip()
            hora_ini = rw["hora_ini"]["var"].get().strip()
            dia_fin  = rw["dia_fin"]["var"].get().strip()
            hora_fin = rw["hora_fin"]["var"].get().strip()
            municipio = (rw["municipio"].get().strip() if hasattr(rw["municipio"], "get") else "")
            grado = (rw["grado"].get().strip() if hasattr(rw["grado"], "get") else "")
            observ = (rw["observaciones"].get().strip() if hasattr(rw["observaciones"], "get") else "")

            if not any([dia_ini, hora_ini, dia_fin, hora_fin, municipio, grado, observ]):
                continue
            if not municipio:
                municipio = self.municipio_default_var.get().strip()
            if not (dia_ini and hora_ini and dia_fin and hora_fin and grado):
                continue

            try:
                d1 = int(dia_ini); h1 = int(hora_ini)
                d2 = int(dia_fin); h2 = int(hora_fin)
                inicio = datetime(y, m, d1, h1, 0)
                fin = datetime(y, m, d2, h2, 0)
                if fin <= inicio:
                    continue
            except Exception:
                continue

            rows.append({
                "inicio_datetime": inicio.strftime("%Y-%m-%d %H:%M"),
                "fin_datetime": fin.strftime("%Y-%m-%d %H:%M"),
                "municipio": municipio,
                "grado": grado,
                "observaciones": observ,
            })

        return pd.DataFrame(rows, columns=["inicio_datetime","fin_datetime","municipio","grado","observaciones"])

    def load_csv(self):
        path = filedialog.askopenfilename(title="Cargar guardias CSV", filetypes=[("CSV","*.csv")])
        if not path:
            return
        try:
            df = pd.read_csv(path, dtype=str).fillna("")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo leer el CSV:\n{e}")
            return

        for child in list(self.rows_frame.children.values()):
            child.destroy()
        self.rows = []
        for _, row in df.iterrows():
            try:
                ini = datetime.fromisoformat(row["inicio_datetime"].strip())
                fin = datetime.fromisoformat(row["fin_datetime"].strip())
                preset = {
                    "dia_ini": f"{ini.day:02d}", "hora_ini": f"{ini.hour:02d}",
                    "dia_fin": f"{fin.day:02d}", "hora_fin": f"{fin.hour:02d}",
                    "municipio": str(row.get("municipio","")),
                    "grado": str(row.get("grado","")),
                    "observaciones": str(row.get("observaciones","")),
                }
            except Exception:
                preset = {}
            self.add_row(preset=preset)
        if len(self.rows) == 0:
            self.add_row()

    def save_csv(self):
        df = self.rows_to_df()
        if df.empty:
            messagebox.showwarning("Aviso", "No hay filas válidas para guardar.")
            return
        path = filedialog.asksaveasfilename(title="Guardar guardias CSV", defaultextension=".csv", filetypes=[("CSV","*.csv")])
        if not path:
            return
        try:
            df.to_csv(path, index=False, encoding="utf-8")
            messagebox.showinfo("OK", f"Guardado: {path}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar:\n{e}")

    # ---------- Ejecutar cálculo ----------
    def run_calc(self):
        df = self.rows_to_df()
        if df.empty:
            messagebox.showwarning("Aviso", "No hay guardias válidas para calcular.")
            return
        try:
            anio = int(self.anio_var.get()); mes = int(self.mes_var.get())
        except ValueError:
            messagebox.showerror("Error", "Año/Mes inválidos.")
            return
        try:
            reglas = cargar_reglas(Path("config/reglas.yml"))
            tarifas = CargadorTarifas(Path("config/tarifas.xlsx"))
            cal = CalendarioFestivos(anio=anio, reglas=reglas, municipio_default=self.municipio_default_var.get().strip())
            detalle, resumen = calcular_importes(df, cal, tarifas, reglas, anio=anio, mes=mes)
            out_dir = Path(self.salida_dir.get().strip()); out_dir.mkdir(parents=True, exist_ok=True)
            det_p = out_dir / f"detalle_{anio:04d}-{mes:02d}.csv"
            res_p = out_dir / f"resumen_{anio:04d}-{mes:02d}.csv"
            escribir_detalle(detalle, det_p); escribir_resumen(resumen, res_p)
            messagebox.showinfo("Cálculo completado", f"Se generaron:\n- {det_p}\n- {res_p}")
        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error durante el cálculo:\n{e}")

def launch():
    app = GuardiaGUI()
    app.mainloop()

if __name__ == "__main__":
    launch()
