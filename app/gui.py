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
TIPOS_GUARDIA = ["8h", "12h", "17h", "24h"]
GRADOS = ["R1", "R2", "R3", "R4", "R5"]
HORAS = [f"{h:02d}" for h in range(24)]

# Columnas visibles (sin los datetime crudos)
VCOLS = [
    ("dia_ini", "Día inicio", 6),
    ("hora_ini", "Hora inicio (00-23)", 10),
    ("dia_fin", "Día fin", 6),
    ("hora_fin", "Hora fin (00-23)", 10),
    ("municipio", "Municipio", 16),
    ("tipo_guardia", "Tipo (8h/12h/17h/24h)", 10),
    ("grado", "Grado (R1..R5)", 10),
    ("observaciones", "Observaciones", 18),
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

    def _build_header(self):
        frm = ttk.Frame(self, padding=8)
        frm.pack(fill=tk.X)
        ttk.Label(frm, text="Año:").pack(side=tk.LEFT)
        anio_entry = ttk.Entry(frm, textvariable=self.anio_var, width=6)
        anio_entry.pack(side=tk.LEFT, padx=(4,12))
        ttk.Label(frm, text="Mes:").pack(side=tk.LEFT)
        mes_entry = ttk.Entry(frm, textvariable=self.mes_var, width=4)
        mes_entry.pack(side=tk.LEFT, padx=(4,12))

        # Cuando cambia año o mes, refrescar listas de días disponibles
        def _refresh_days(_e=None):
            try:
                y = int(self.anio_var.get())
                m = int(self.mes_var.get())
                mdays = _cal.monthrange(y, m)[1]
            except Exception:
                mdays = 31
            self.dias_mes = [f"{d:02d}" for d in range(1, mdays+1)]
            # Actualizar combos de día en todas las filas
            for rw in getattr(self, "rows", []):
                if "dia_ini" in rw: rw["dia_ini"]["cb"]["values"] = self.dias_mes
                if "dia_fin" in rw: rw["dia_fin"]["cb"]["values"] = self.dias_mes

        anio_entry.bind("<FocusOut>", _refresh_days)
        mes_entry.bind("<FocusOut>", _refresh_days)

        ttk.Label(frm, text="Municipio por defecto:").pack(side=tk.LEFT)
        ttk.Entry(frm, textvariable=self.municipio_default_var, width=16).pack(side=tk.LEFT, padx=(4,12))

        ttk.Label(frm, text="Salida:").pack(side=tk.LEFT, padx=(8,0))
        out_entry = ttk.Entry(frm, textvariable=self.salida_dir, width=60)
        out_entry.pack(side=tk.LEFT, padx=(4,4))
        ttk.Button(frm, text="Cambiar...", command=self._select_output_dir).pack(side=tk.LEFT)

        # Inicializar lista de días del mes por defecto
        _refresh_days()

    def _build_table(self):
        self.table_frame = ttk.Frame(self, padding=(8,0,8,8))
        self.table_frame.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(self.table_frame)
        header.pack(fill=tk.X)
        ttk.Label(header, text="#", width=3).grid(row=0, column=0, padx=2, pady=2, sticky="w")
        for c, (key, title, w) in enumerate(VCOLS, start=1):
            ttk.Label(header, text=title).grid(row=0, column=c, padx=2, pady=2, sticky="w")
        ttk.Label(header, text="").grid(row=0, column=len(VCOLS)+1)

        self.canvas = tk.Canvas(self.table_frame, borderwidth=0)
        self.scroll_y = ttk.Scrollbar(self.table_frame, orient="vertical", command=self.canvas.yview)
        self.rows_frame = ttk.Frame(self.canvas)

        self.rows_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.rows_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scroll_y.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scroll_y.pack(side="right", fill="y")

        self.rows = []
        self.add_row()  # primera fila

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

    def add_row(self, preset=None):
        if len(self.rows) >= MAX_ROWS:
            messagebox.showwarning("Límite", f"Máximo {MAX_ROWS} guardias.")
            return
        r = len(self.rows)
        ttk.Label(self.rows_frame, text=str(r+1)).grid(row=r, column=0, padx=2, pady=2, sticky="w")

        row_widgets = {}
        col_idx = 1
        for key, title, w in VCOLS:
            if key in ("dia_ini","dia_fin"):
                var = tk.StringVar(value=(preset.get(key, "") if preset else ""))
                cb = ttk.Combobox(self.rows_frame, textvariable=var, values=getattr(self, "dias_mes", [f"{d:02d}" for d in range(1,32)]), width=6, state="readonly")
                cb.grid(row=r, column=col_idx, padx=2, pady=2, sticky="w")
                row_widgets[key] = {"var": var, "cb": cb}
            elif key in ("hora_ini","hora_fin"):
                var = tk.StringVar(value=(preset.get(key, "") if preset else ""))
                cb = ttk.Combobox(self.rows_frame, textvariable=var, values=HORAS, width=6, state="readonly")
                cb.grid(row=r, column=col_idx, padx=2, pady=2, sticky="w")
                row_widgets[key] = {"var": var, "cb": cb}
            elif key == "tipo_guardia":
                var = tk.StringVar(value=(preset.get(key, "") if preset else ""))
                cb = ttk.Combobox(self.rows_frame, textvariable=var, values=TIPOS_GUARDIA, width=10, state="readonly")
                cb.grid(row=r, column=col_idx, padx=2, pady=2, sticky="w")
                row_widgets[key] = var
            elif key == "grado":
                var = tk.StringVar(value=(preset.get(key, "") if preset else ""))
                cb = ttk.Combobox(self.rows_frame, textvariable=var, values=GRADOS, width=10, state="readonly")
                cb.grid(row=r, column=col_idx, padx=2, pady=2, sticky="w")
                row_widgets[key] = var
            else:
                var = tk.StringVar(value=(preset.get(key, "") if preset else ""))
                ent = ttk.Entry(self.rows_frame, textvariable=var, width=w)
                ent.grid(row=r, column=col_idx, padx=2, pady=2, sticky="w")
                row_widgets[key] = var
            col_idx += 1

        btn = ttk.Button(self.rows_frame, text="Borrar", command=lambda i=r: self.delete_row(i))
        btn.grid(row=r, column=len(VCOLS)+1, padx=2, pady=2, sticky="w")
        row_widgets["_btn"] = btn

        self.rows.append(row_widgets)

    def delete_row(self, idx):
        if idx < 0 or idx >= len(self.rows):
            return
        for child in list(self.rows_frame.children.values()):
            child.destroy()
        del self.rows[idx]
        tmp = self.rows[:]
        self.rows = []
        for preset in tmp:
            # Convertir a dict de valores simples
            vals = {}
            for k, v in preset.items():
                if k.startswith("_"): continue
                if isinstance(v, dict) and "var" in v:
                    vals[k] = v["var"].get()
                elif hasattr(v, "get"):
                    vals[k] = v.get()
                else:
                    vals[k] = ""
            self.add_row(preset=vals)

    def rows_to_df(self):
        # Construye inicio_datetime y fin_datetime con YYYY-MM-DD HH:00
        rows = []
        try:
            y = int(self.anio_var.get())
            m = int(self.mes_var.get())
        except Exception:
            messagebox.showerror("Error", "Año/Mes inválidos.")
            return pd.DataFrame(columns=["inicio_datetime","fin_datetime","municipio","tipo_guardia","grado","observaciones"])

        for rw in self.rows:
            vals = {}
            # Extrae valores
            vals["dia_ini"] = rw["dia_ini"]["var"].get().strip()
            vals["hora_ini"] = rw["hora_ini"]["var"].get().strip()
            vals["dia_fin"] = rw["dia_fin"]["var"].get().strip()
            vals["hora_fin"] = rw["hora_fin"]["var"].get().strip()
            vals["municipio"] = (rw["municipio"].get().strip() if hasattr(rw["municipio"], "get") else "")
            vals["tipo_guardia"] = (rw["tipo_guardia"].get().strip() if hasattr(rw["tipo_guardia"], "get") else "")
            vals["grado"] = (rw["grado"].get().strip() if hasattr(rw["grado"], "get") else "")
            vals["observaciones"] = (rw["observaciones"].get().strip() if hasattr(rw["observaciones"], "get") else "")

            if not any(vals.values()):
                continue

            # Completar municipio por defecto si vacío
            if not vals["municipio"]:
                vals["municipio"] = self.municipio_default_var.get().strip()

            # Validación mínima de combos seleccionados
            if not (vals["dia_ini"] and vals["hora_ini"] and vals["dia_fin"] and vals["hora_fin"]):
                # fila incompleta: la ignoramos
                continue

            try:
                d1 = int(vals["dia_ini"]); h1 = int(vals["hora_ini"])
                d2 = int(vals["dia_fin"]); h2 = int(vals["hora_fin"])
                inicio = datetime(y, m, d1, h1, 0)
                fin = datetime(y, m, d2, h2, 0)
                if fin <= inicio:
                    # si alguien introduce fin <= inicio, lo descartamos de momento
                    continue
            except Exception:
                # fila inválida, la saltamos
                continue

            rows.append({
                "inicio_datetime": inicio.strftime("%Y-%m-%d %H:%M"),
                "fin_datetime": fin.strftime("%Y-%m-%d %H:%M"),
                "municipio": vals["municipio"],
                "tipo_guardia": vals["tipo_guardia"],
                "grado": vals["grado"],
                "observaciones": vals["observaciones"],
            })

        return pd.DataFrame(rows, columns=["inicio_datetime","fin_datetime","municipio","tipo_guardia","grado","observaciones"])

    def load_csv(self):
        path = filedialog.askopenfilename(title="Cargar guardias CSV", filetypes=[("CSV","*.csv")])
        if not path:
            return
        try:
            df = pd.read_csv(path, dtype=str).fillna("")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo leer el CSV:\n{e}")
            return
        # Reconstruir GUI
        for child in list(self.rows_frame.children.values()):
            child.destroy()
        self.rows = []
        for _, row in df.iterrows():
            # Parsear inicio/fin para extraer día/hora
            try:
                ini = datetime.fromisoformat(row["inicio_datetime"].strip())
                fin = datetime.fromisoformat(row["fin_datetime"].strip())
                preset = {
                    "dia_ini": f"{ini.day:02d}", "hora_ini": f"{ini.hour:02d}",
                    "dia_fin": f"{fin.day:02d}", "hora_fin": f"{fin.hour:02d}",
                    "municipio": str(row.get("municipio", "")),
                    "tipo_guardia": str(row.get("tipo_guardia","")),
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

    def run_calc(self):
        df = self.rows_to_df()
        if df.empty:
            messagebox.showwarning("Aviso", "No hay guardias válidas para calcular.")
            return
        try:
            anio = int(self.anio_var.get())
            mes = int(self.mes_var.get())
        except ValueError:
            messagebox.showerror("Error", "Año/Mes inválidos.")
            return
        try:
            reglas = cargar_reglas(Path("config/reglas.yml"))
            tarifas = CargadorTarifas(Path("config/tarifas.xlsx"))
            cal = CalendarioFestivos(anio=anio, reglas=reglas, municipio_default=self.municipio_default_var.get().strip())
            detalle, resumen = calcular_importes(df, cal, tarifas, reglas, anio=anio, mes=mes)
            out_dir = Path(self.salida_dir.get().strip())
            out_dir.mkdir(parents=True, exist_ok=True)
            det_p = out_dir / f"detalle_{anio:04d}-{mes:02d}.csv"
            res_p = out_dir / f"resumen_{anio:04d}-{mes:02d}.csv"
            escribir_detalle(detalle, det_p)
            escribir_resumen(resumen, res_p)
            messagebox.showinfo("Cálculo completado", f"Se generaron:\n- {det_p}\n- {res_p}")
        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error durante el cálculo:\n{e}")

def launch():
    app = GuardiaGUI()
    app.mainloop()

if __name__ == "__main__":
    launch()
