# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter import font as tkfont
from pathlib import Path
import pandas as pd
from datetime import datetime
import calendar as _cal
import re

from app.io_csv import escribir_detalle, escribir_resumen
from app.reglas import cargar_reglas
from app.tarifas import CargadorTarifas
from app.calendario import CalendarioFestivos
from app.calculo import calcular_importes

MAX_ROWS = 24
GRADOS = ["R1", "R2", "R3", "R4", "R5"]

# ---- Definición de columnas (anchos base en caracteres; la 1ª fila se mide y se fija en píxeles) ----
COLS = [
    {"key": "_idx",       "title": "#",            "width_chars": 3},
    {"key": "dia_ini",    "title": "Día inicio",   "width_chars": 6},
    {"key": "hora_ini",   "title": "Hora ini",     "width_chars": 8},
    {"key": "tipo_ini",   "title": "Pago ini",     "width_chars": 18},  # Radios N/F/E
    {"key": "dia_fin",    "title": "Día fin",      "width_chars": 6},
    {"key": "hora_fin",   "title": "Hora fin",     "width_chars": 8},
    {"key": "tipo_fin",   "title": "Pago fin",     "width_chars": 18},  # Radios N/F/E
    {"key": "municipio",  "title": "Municipio",    "width_chars": 28},
    {"key": "grado",      "title": "Grado",        "width_chars": 8},
    {"key": "observ",     "title": "Observ.",      "width_chars": 36},
    {"key": "_del",       "title": "",             "width_chars": 8},
]
SPACER_COL = len(COLS)  # columna espaciadora

# ---- Fallback de municipios ----
_MUN_FALLBACK = [
    "Aguadulce","Alanís","Albaida del Aljarafe","Alcalá de Guadaíra","Alcalá del Río",
    "Alcolea del Río","Algámitas","La Algaba","Almadén de la Plata","Almensilla","Arahal",
    "Aznalcázar","Aznalcóllar","Badolatosa","Benacazón","Bollullos de la Mitación","Bormujos",
    "Brenes","Burguillos","Las Cabezas de San Juan","Camas","La Campana","Cantillana",
    "Cañada Rosal","Carmona","Carrión de los Céspedes","Casariche","Castilblanco de los Arroyos",
    "Castilleja de Guzmán","Castilleja de la Cuesta","Castilleja del Campo","El Castillo de las Guardas",
    "Cazalla de la Sierra","Constantina","Coria del Río","Coripe","El Cuervo de Sevilla","Dos Hermanas",
    "Écija","El Garrobo","Gelves","Gerena","Gilena","Gines","Guadalcanal","Guillena","Herrera",
    "Huévar del Aljarafe","Isla Mayor","La Lantejuela","Lebrija","Lora de Estepa","Lora del Río",
    "La Luisiana","El Madroño","Mairena del Alcor","Mairena del Aljarafe","Marchena","Marinaleda",
    "Martín de la Jara","Los Molares","Montellano","Morón de la Frontera","Las Navas de la Concepción",
    "Olivares","Osuna","Los Palacios y Villafranca","Palomares del Río","Paradas","Pedrera","El Pedroso",
    "Peñaflor","Pilas","Pruna","La Puebla de Cazalla","La Puebla de los Infantes","La Puebla del Río",
    "El Real de la Jara","La Rinconada","La Roda de Andalucía","El Ronquillo","El Rubio","Salteras",
    "San Juan de Aznalfarache","San Nicolás del Puerto","Sanlúcar la Mayor","Santiponce","El Saucejo",
    "Sevilla","Tocina","Tomares","Umbrete","Utrera","Valencina de la Concepción","Villamanrique de la Condesa",
    "Villanueva de San Juan","Villanueva del Ariscal","Villanueva del Río y Minas","Villaverde del Río",
    "El Viso del Alcor","El Coronil","El Palmar de Troya"
]

def _load_municipios() -> list[str]:
    path = Path("data/municipios_sevilla.csv")
    if not path.exists():
        return _MUN_FALLBACK[:]
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
        if "municipio" not in df.columns:
            return _MUN_FALLBACK[:]
        vals = [str(m).strip() for m in df["municipio"].tolist() if str(m).strip()]
        vals = list(dict.fromkeys(vals))
        return vals if vals else _MUN_FALLBACK[:]
    except Exception:
        return _MUN_FALLBACK[:]

# ---- Combobox con autocompletado ----
class AutoCompleteCombobox(ttk.Combobox):
    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)
        self._full_values = list(self.cget("values")) if self.cget("values") else []
        self.bind("<KeyRelease>", self._on_key)
        self.bind("<<ComboboxSelected>>", self._restore_full)

    def set_completion_list(self, values):
        self._full_values = list(values)
        self["values"] = tuple(self._full_values)

    def _on_key(self, event):
        text = self.get()
        if not text:
            self["values"] = tuple(self._full_values)
            return
        t = text.lower()
        filtered = [v for v in self._full_values if v.lower().startswith(t)]
        if not filtered:
            filtered = [v for v in self._full_values if t in v.lower()]
        self["values"] = tuple(filtered) if filtered else tuple(self._full_values)
        try:
            self.event_generate("<Down>")
        except tk.TclError:
            pass

    def _restore_full(self, _e=None):
        self["values"] = tuple(self._full_values)

# ---- Ventana principal ----
class GuardiaGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Guardias MIR — Cálculo de importe")
        self.geometry("1320x800")
        self.resizable(True, True)

        # Métrica de fuente (solo para anchura base en chars)
        self._font = tkfont.nametofont("TkDefaultFont")

        self.municipios = _load_municipios()

        # Campos superiores
        self.nombre_var = tk.StringVar(value="")
        self.irpf_var = tk.StringVar(value="0")
        self.anio_var = tk.StringVar(value="2025")
        self.mes_var = tk.StringVar(value="9")
        self.municipio_default_var = tk.StringVar(value=(self.municipios[0] if self.municipios else "Sevilla"))
        self.salida_dir = tk.StringVar(value=str(Path("output").resolve()))

        # Almacena las referencias de frames del header y ancho fijo por columna (en píxeles)
        self.header_cells = []
        self.fixed_col_widths = None  # se fija tras medir la primera fila

        self._build_header()
        self._build_table()
        self._build_buttons()

    # ---- Barra superior ----
    def _build_header(self):
        frm = ttk.Frame(self, padding=8)
        frm.pack(fill=tk.X)

        ttk.Label(frm, text="Nombre:").grid(row=0, column=0, sticky="w", padx=(0,4))
        ttk.Entry(frm, textvariable=self.nombre_var, width=28).grid(row=0, column=1, sticky="w", padx=(0,16))

        ttk.Label(frm, text="% IRPF:").grid(row=0, column=2, sticky="w", padx=(0,4))
        ttk.Entry(frm, textvariable=self.irpf_var, width=6).grid(row=0, column=3, sticky="w", padx=(0,16))

        ttk.Label(frm, text="Año:").grid(row=0, column=4, sticky="w", padx=(0,4))
        anio_entry = ttk.Entry(frm, textvariable=self.anio_var, width=6)
        anio_entry.grid(row=0, column=5, sticky="w", padx=(0,12))

        ttk.Label(frm, text="Mes:").grid(row=0, column=6, sticky="w", padx=(0,4))
        mes_entry = ttk.Entry(frm, textvariable=self.mes_var, width=4)
        mes_entry.grid(row=0, column=7, sticky="w", padx=(0,12))

        ttk.Label(frm, text="Municipio por defecto:").grid(row=0, column=8, sticky="w", padx=(0,4))
        muni_cb = AutoCompleteCombobox(frm, textvariable=self.municipio_default_var, values=self.municipios,
                                       width=28, state="normal")
        muni_cb.set_completion_list(self.municipios)
        muni_cb.grid(row=0, column=9, sticky="w", padx=(0,12))

        ttk.Label(frm, text="Salida:").grid(row=0, column=10, sticky="w", padx=(0,4))
        out_entry = ttk.Entry(frm, textvariable=self.salida_dir, width=50)
        out_entry.grid(row=0, column=11, sticky="ew", padx=(0,4))
        ttk.Button(frm, text="Cambiar...", command=self._select_output_dir).grid(row=0, column=12, sticky="w")

        for c in range(13):
            frm.grid_columnconfigure(c, weight=(1 if c == 11 else 0))

        def _refresh_days(_e=None):
            try:
                y = int(self.anio_var.get()); m = int(self.mes_var.get())
                mdays = _cal.monthrange(y, m)[1]
            except Exception:
                mdays = 31
            self.dias_mes = [f"{d:02d}" for d in range(1, mdays+1)]
            for rw in getattr(self, "rows", []):
                if "dia_ini" in rw: rw["dia_ini"]["cb"].set_completion_list(self.dias_mes)
                if "dia_fin" in rw: rw["dia_fin"]["cb"].set_completion_list(self.dias_mes)

        anio_entry.bind("<FocusOut>", _refresh_days)
        mes_entry.bind("<FocusOut>", _refresh_days)
        _refresh_days()

    # ---- Tabla tipo Excel ----
    def _build_table(self):
        wrap = ttk.Frame(self, padding=(8,0,8,8))
        wrap.pack(fill=tk.BOTH, expand=True)

        # Encabezado (sin ancho fijo todavía; se ajustará tras medir 1ª fila)
        self.header = ttk.Frame(wrap)
        self.header.pack(fill=tk.X, pady=(0,2))
        self.header_cells = []
        for c, col in enumerate(COLS):
            cell = tk.Frame(self.header, bd=1, relief="solid")  # ancho se fijará luego
            cell.grid(row=0, column=c, sticky="w")
            ttk.Label(cell, text=col["title"], anchor="center").pack(fill="both", padx=2, pady=2)
            self.header.grid_columnconfigure(c, weight=0)
            self.header_cells.append(cell)

        # Espaciadora
        tk.Frame(self.header, bd=0).grid(row=0, column=SPACER_COL, sticky="ew")
        self.header.grid_columnconfigure(SPACER_COL, weight=1)

        # Cuerpo con scroll
        self.canvas = tk.Canvas(wrap, borderwidth=0, highlightthickness=0)
        self.scroll_y = ttk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        self.rows_frame = ttk.Frame(self.canvas)
        self.rows_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.rows_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scroll_y.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scroll_y.pack(side="right", fill="y")

        for c, _ in enumerate(COLS):
            self.rows_frame.grid_columnconfigure(c, weight=0)
        self.rows_frame.grid_columnconfigure(SPACER_COL, weight=1)

        self.rows = []
        # IMPORTANTE: la 1ª fila se crea y luego se miden sus anchos
        self.add_row()
        self.after(0, self._sync_header_to_first_row)

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

    # ---- Crear una celda (marco) con ancho fijo si ya lo conocemos ----
    def _make_cell_frame(self, parent, row_index, col_index, height=30):
        f = tk.Frame(parent, bd=1, relief="solid")
        f.grid(row=row_index, column=col_index, sticky="w")
        if self.fixed_col_widths:
            f.configure(width=self.fixed_col_widths[col_index], height=height)
            f.grid_propagate(False)
        return f

    # ---- Medir 1ª fila y fijar anchos del encabezado + futuras filas ----
    def _sync_header_to_first_row(self):
        if not self.rows:
            return
        first = self.rows[0]
        widths = []
        for col_index in range(len(COLS)):
            cell_frame = first["cell_frames"][col_index]
            cell_frame.update_idletasks()
            widths.append(cell_frame.winfo_reqwidth())

        # Guardar como anchos fijos
        self.fixed_col_widths = widths[:]

        # Aplicar al header
        for col_index, w in enumerate(self.fixed_col_widths):
            hcell = self.header_cells[col_index]
            hcell.configure(width=w, height=28)
            hcell.grid_propagate(False)

        # Reaplicar a la fila 0 (para que se ajuste exactamente)
        for col_index, w in enumerate(self.fixed_col_widths):
            fr = first["cell_frames"][col_index]
            fr.configure(width=w, height=30)
            fr.grid_propagate(False)

    # ---- Filas ----
    def add_row(self, preset=None):
        if len(self.rows) >= MAX_ROWS:
            messagebox.showwarning("Límite", f"Máximo {MAX_ROWS} guardias.")
            return
        r = len(self.rows)
        row_widgets = {"cell_frames": []}

        # helpers de widgets
        def add_ac_combo(parent, width_chars, values, value=""):
            var = tk.StringVar(value=value)
            cb = AutoCompleteCombobox(parent, textvariable=var, values=values,
                                      width=width_chars, state="normal")
            cb.set_completion_list(values)
            cb.pack(padx=4, pady=2, anchor="w")
            return {"var": var, "cb": cb}

        def add_entry(parent, width_chars, value=""):
            var = tk.StringVar(value=value)
            ent = ttk.Entry(parent, textvariable=var, width=width_chars)
            ent.pack(padx=4, pady=2, anchor="w")
            return var

        def add_combo(parent, width_chars, values, value=""):
            var = tk.StringVar(value=value)
            cb = ttk.Combobox(parent, textvariable=var, values=values,
                              width=width_chars, state="readonly")
            cb.pack(padx=4, pady=2, anchor="w")
            return var

        def add_tipo_radios(parent, value=""):
            var = tk.StringVar(value=value)  # "", "normal", "festivo", "especial"
            inner = ttk.Frame(parent)
            inner.pack(padx=2, pady=2, anchor="w")
            ttk.Radiobutton(inner, text="N", value="normal",   variable=var).pack(side=tk.LEFT, padx=2)
            ttk.Radiobutton(inner, text="F", value="festivo",  variable=var).pack(side=tk.LEFT, padx=2)
            ttk.Radiobutton(inner, text="E", value="especial", variable=var).pack(side=tk.LEFT, padx=2)
            def _clear(_e): var.set("")
            parent.bind("<Double-Button-1>", _clear)
            return var

        # celdas: crear frames (si ya tenemos fixed_col_widths, se aplican ahora)
        for col_index in range(len(COLS)):
            fr = self._make_cell_frame(self.rows_frame, r, col_index)
            row_widgets["cell_frames"].append(fr)

        # Col 0 índice
        ttk.Label(row_widgets["cell_frames"][0], text=str(r+1)).pack(padx=4, pady=2, anchor="w")

        dias_vals = getattr(self, "dias_mes", [f"{d:02d}" for d in range(1,32)])
        horas_vals = [f"{h:02d}" for h in range(24)]

        # Widgets en sus celdas
        row_widgets["dia_ini"]  = add_ac_combo(row_widgets["cell_frames"][1], COLS[1]["width_chars"], dias_vals, (preset.get("dia_ini","") if preset else ""))
        row_widgets["hora_ini"] = add_ac_combo(row_widgets["cell_frames"][2], COLS[2]["width_chars"], horas_vals, (preset.get("hora_ini","") if preset else ""))
        row_widgets["tipo_ini"] = add_tipo_radios(row_widgets["cell_frames"][3], (preset.get("tipo_ini","") if preset else ""))

        row_widgets["dia_fin"]  = add_ac_combo(row_widgets["cell_frames"][4], COLS[4]["width_chars"], dias_vals, (preset.get("dia_fin","") if preset else ""))
        row_widgets["hora_fin"] = add_ac_combo(row_widgets["cell_frames"][5], COLS[5]["width_chars"], horas_vals, (preset.get("hora_fin","") if preset else ""))
        row_widgets["tipo_fin"] = add_tipo_radios(row_widgets["cell_frames"][6], (preset.get("tipo_fin","") if preset else ""))

        row_widgets["municipio"] = add_ac_combo(row_widgets["cell_frames"][7], COLS[7]["width_chars"], self.municipios, (preset.get("municipio","") if preset else ""))
        row_widgets["grado"] = add_combo(row_widgets["cell_frames"][8], COLS[8]["width_chars"], GRADOS, (preset.get("grado","") if preset else ""))
        row_widgets["observaciones"] = add_entry(row_widgets["cell_frames"][9], COLS[9]["width_chars"], (preset.get("observaciones","") if preset else ""))

        btn = ttk.Button(row_widgets["cell_frames"][10], text="Borrar", width=COLS[10]["width_chars"], command=lambda i=r: self.delete_row(i))
        btn.pack(padx=4, pady=2, anchor="w")
        row_widgets["_btn"] = btn

        # Espaciadora
        tk.Frame(self.rows_frame).grid(row=r, column=SPACER_COL, sticky="ew")

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
            vals = {}
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
        # tras reconstruir, asegurar que header sigue alineado
        self.after(0, self._sync_header_to_first_row)

    # ---- CSV <-> DF ----
    def rows_to_df(self):
        rows = []
        try:
            y = int(self.anio_var.get()); m = int(self.mes_var.get())
        except Exception:
            messagebox.showerror("Error", "Año/Mes inválidos.")
            return pd.DataFrame(columns=[
                "inicio_datetime","fin_datetime","municipio","grado","observaciones","tipo_ini","tipo_fin"
            ])

        for rw in self.rows:
            dia_ini  = rw["dia_ini"]["var"].get().strip()
            hora_ini = rw["hora_ini"]["var"].get().strip()
            tipo_ini = (rw["tipo_ini"].get().strip() if hasattr(rw["tipo_ini"], "get") else "")
            dia_fin  = rw["dia_fin"]["var"].get().strip()
            hora_fin = rw["hora_fin"]["var"].get().strip()
            tipo_fin = (rw["tipo_fin"].get().strip() if hasattr(rw["tipo_fin"], "get") else "")
            municipio = rw["municipio"]["var"].get().strip() if isinstance(rw["municipio"], dict) else ""
            grado = (rw["grado"].get().strip() if hasattr(rw["grado"], "get") else "")
            observ = (rw["observaciones"].get().strip() if hasattr(rw["observaciones"], "get") else "")

            if not any([dia_ini, hora_ini, dia_fin, hora_fin, municipio, grado, observ, tipo_ini, tipo_fin]):
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
                "tipo_ini": tipo_ini,
                "tipo_fin": tipo_fin,
            })

        return pd.DataFrame(rows, columns=[
            "inicio_datetime","fin_datetime","municipio","grado","observaciones","tipo_ini","tipo_fin"
        ])

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
                ini = datetime.fromisoformat(str(row["inicio_datetime"]).strip())
                fin = datetime.fromisoformat(str(row["fin_datetime"]).strip())
                preset = {
                    "dia_ini": f"{ini.day:02d}", "hora_ini": f"{ini.hour:02d}",
                    "tipo_ini": str(row.get("tipo_ini","")),
                    "dia_fin": f"{fin.day:02d}", "hora_fin": f"{fin.hour:02d}",
                    "tipo_fin": str(row.get("tipo_fin","")),
                    "municipio": str(row.get("municipio","")),
                    "grado": str(row.get("grado","")),
                    "observaciones": str(row.get("observaciones","")),
                }
            except Exception:
                preset = {}
            self.add_row(preset=preset)

        if len(self.rows) == 0:
            self.add_row()

        # Ajustar encabezados a la nueva primera fila
        self.after(0, self._sync_header_to_first_row)

    def save_csv(self):
        df = self.rows_to_df()
        if df.empty:
            messagebox.showwarning("Aviso", "No hay filas válidas para guardar.")
            return
        path = filedialog.asksaveasfilename(
            title="Guardar guardias CSV",
            defaultextension=".csv",
            filetypes=[("CSV","*.csv")]
        )
        if not path:
            return
        try:
            df.to_csv(path, index=False, encoding="utf-8")
            messagebox.showinfo("OK", f"Guardado: {path}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar:\n{e}")

    # ---- Calcular ----
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

        # IRPF y nombre
        try:
            irpf = float(self.irpf_var.get().replace(",", ".").strip() or "0")
        except Exception:
            messagebox.showerror("Error", "IRPF inválido. Usa un número (p.ej. 15 o 15.5).")
            return
        irpf = max(0.0, min(irpf, 100.0))
        nombre = self.nombre_var.get().strip()
        nombre_sanit = re.sub(r"[^A-Za-z0-9_-]+", "_", nombre) if nombre else "sin_nombre"

        try:
            reglas = cargar_reglas(Path("config/reglas.yml"))
            tarifas = CargadorTarifas(Path("config/tarifas.xlsx"))
            cal = CalendarioFestivos(anio=anio, reglas=reglas, municipio_default=self.municipio_default_var.get().strip())

            detalle, resumen = calcular_importes(
                df, cal, tarifas, reglas, anio=anio, mes=mes, irpf_percent=irpf
            )

            out_dir = Path(self.salida_dir.get().strip()); out_dir.mkdir(parents=True, exist_ok=True)
            det_p = out_dir / f"detalle_{anio:04d}-{mes:02d}_{nombre_sanit}.csv"
            res_p = out_dir / f"resumen_{anio:04d}-{mes:02d}_{nombre_sanit}.csv"

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
