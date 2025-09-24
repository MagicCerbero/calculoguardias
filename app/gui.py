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

# ---- Definición de columnas (usaremos el mismo ancho para encabezado y celdas) ----
COLS = [
    {"key": "_idx",       "title": "#",            "width_chars": 3},
    {"key": "dia_ini",    "title": "Día inicio",   "width_chars": 6},
    {"key": "hora_ini",   "title": "Hora ini",     "width_chars": 8},
    {"key": "tipo_ini",   "title": "Pago ini",     "width_chars": 18},  # N/F/E
    {"key": "dia_fin",    "title": "Día fin",      "width_chars": 6},
    {"key": "hora_fin",   "title": "Hora fin",     "width_chars": 8},
    {"key": "tipo_fin",   "title": "Pago fin",     "width_chars": 18},  # N/F/E
    {"key": "municipio",  "title": "Municipio",    "width_chars": 28},
    {"key": "grado",      "title": "Grado",        "width_chars": 8},
    {"key": "observ",     "title": "Observ.",      "width_chars": 36},
    {"key": "_del",       "title": "",             "width_chars": 8},
]
SPACER_COL = len(COLS)  # columna espaciadora para absorber crecimiento

# ---- Fallback de municipios (si falta data/municipios_sevilla.csv) ----
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

        # Fuente base y mapeo de caracteres -> píxeles para alinear header/celdas
        self._font = tkfont.nametofont("TkDefaultFont")
        self._col_px = {i: self._chars_to_px(col["width_chars"]) for i, col in enumerate(COLS)}

        self.municipios = _load_municipios()

        # Campos superiores
        self.nombre_var = tk.StringVar(value="")
        self.irpf_var = tk.StringVar(value="0")
        self.anio_var = tk.StringVar(value="2025")
        self.mes_var = tk.StringVar(value="9")
        self.municipio_default_var = tk.StringVar(value=(self.municipios[0] if self.municipios else "Sevilla"))
        self.salida_dir = tk.StringVar(value=str(Path("output").resolve()))

        self._build_header()
        self._build_table()
        self._build_buttons()

    # Conversión: caracteres visuales a píxeles (mismo ancho para encabezado y celda)
    def _chars_to_px(self, chars: int) -> int:
        return self._font.measure("0" * max(chars, 1)) + 16  # +padding/borde

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

    # ---- Tabla tipo Excel (encabezados y celdas con el MISMO ancho) ----
    def _build_table(self):
        wrap = ttk.Frame(self, padding=(8,0,8,8))
        wrap.pack(fill=tk.BOTH, expand=True)

        # Encabezado: un frame por columna con ancho fijo en píxeles
        self.header = ttk.Frame(wrap)
        self.header.pack(fill=tk.X, pady=(0,2))

        for c, col in enumerate(COLS):
            wpx = self._col_px[c]
            hcell = tk.Frame(self.header, bd=1, relief="solid", width=wpx, height=28)
            hcell.grid(row=0, column=c, sticky="w")
            hcell.grid_propagate(False)  # <- CLAVE: no dejar que se estire/encoga
            ttk.Label(hcell, text=col["title"], anchor="center").pack(fill="both")
            self.header.grid_columnconfigure(c, weight=0)

        # Espaciadora que absorbe el crecimiento de la ventana
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

        # Columnas del cuerpo: fijas + espaciadora
        for c, _ in enumerate(COLS):
            self.rows_frame.grid_columnconfigure(c, weight=0)
        self.rows_frame.grid_columnconfigure(SPACER_COL, weight=1)

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

    # ---- Filas ----
    def add_row(self, preset=None):
        if len(self.rows) >= MAX_ROWS:
            messagebox.showwarning("Límite", f"Máximo {MAX_ROWS} guardias.")
            return
        r = len(self.rows)
        row_widgets = {}

        def cell(col_idx, height=30):
            f = tk.Frame(self.rows_frame, bd=1, relief="solid",
                         width=self._col_px[col_idx], height=height)
            f.grid(row=r, column=col_idx, sticky="w")
            f.grid_propagate(False)  # <- CLAVE
            return f

        # índice
        idx = cell(0)
        ttk.Label(idx, text=str(r+1)).pack(fill="both")

        # helpers
        def add_ac_combo(col_idx, values, value=""):
            f = cell(col_idx)
            var = tk.StringVar(value=value)
            cb = AutoCompleteCombobox(f, textvariable=var, values=values,
                                      width=COLS[col_idx]["width_chars"], state="normal")
            cb.set_completion_list(values)
            cb.place(relx=0.0, rely=0.5, x=6, anchor="w")  # evitar padding que distorsione
            return {"var": var, "cb": cb}

        def add_entry(col_idx, value=""):
            f = cell(col_idx)
            var = tk.StringVar(value=value)
            ent = ttk.Entry(f, textvariable=var, width=COLS[col_idx]["width_chars"])
            ent.place(relx=0.0, rely=0.5, x=6, anchor="w")
            return var

        def add_combo(col_idx, values, value=""):
            f = cell(col_idx)
            var = tk.StringVar(value=value)
            cb = ttk.Combobox(f, textvariable=var, values=values,
                              width=COLS[col_idx]["width_chars"], state="readonly")
            cb.place(relx=0.0, rely=0.5, x=6, anchor="w")
            return var

        def add_tipo_radios(col_idx, value=""):
            f = cell(col_idx)
            var = tk.StringVar(value=value)  # "", "normal", "festivo", "especial"
            # distribución exacta para no romper el ancho
            inner = ttk.Frame(f)
            inner.place(relx=0.0, rely=0.5, x=4, anchor="w")
            ttk.Radiobutton(inner, text="N", value="normal",   variable=var).pack(side=tk.LEFT, padx=2)
            ttk.Radiobutton(inner, text="F", value="festivo",  variable=var).pack(side=tk.LEFT, padx=2)
            ttk.Radiobutton(inner, text="E", value="especial", variable=var).pack(side=tk.LEFT, padx=2)
            def _clear(_e): var.set("")
            f.bind("<Double-Button-1>", _clear)
            return var

        dias_vals = getattr(self, "dias_mes", [f"{d:02d}" for d in range(1,32)])
        horas_vals = [f"{h:02d}" for h in range(24)]

        row_widgets["dia_ini"]  = add_ac_combo(1, dias_vals, (preset.get("dia_ini","") if preset else ""))
        row_widgets["hora_ini"] = add_ac_combo(2, horas_vals, (preset.get("hora_ini","") if preset else ""))
        row_widgets["tipo_ini"] = add_tipo_radios(3, (preset.get("tipo_ini","") if preset else ""))

        row_widgets["dia_fin"]  = add_ac_combo(4, dias_vals, (preset.get("dia_fin","") if preset else ""))
        row_widgets["hora_fin"] = add_ac_combo(5, horas_vals, (preset.get("hora_fin","") if preset else ""))
        row_widgets["tipo_fin"] = add_tipo_radios(6, (preset.get("tipo_fin","") if preset else ""))

        row_widgets["municipio"] = add_ac_combo(7, self.municipios, (preset.get("municipio","") if preset else ""))
        row_widgets["grado"] = add_combo(8, GRADOS, (preset.get("grado","") if preset else ""))
        row_widgets["observaciones"] = add_entry(9, (preset.get("observaciones","") if preset else ""))

        fdel = cell(10)
        btn = ttk.Button(fdel, text="Borrar", width=COLS[10]["width_chars"], command=lambda i=r: self.delete_row(i))
        btn.place(relx=0.0, rely=0.5, x=6, anchor="w")
        row_widgets["_btn"] = btn

        # espaciadora
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
