"""Ventana del pipeline. La lógica está en pipeline.py.

    py -3 app.py
    o doble clic en ejecutar.bat

No hay que instalar nada: customtkinter va en vendor/.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "vendor"))

import customtkinter as ctk

import fuente
import pipeline

ctk.set_appearance_mode("light")
ctk.set_default_color_theme(str(ROOT / "tema.json"))

CLAY = ("#c96442", "#c96442")
CLAY_HOVER = ("#a84e32", "#d4765a")
ON_CLAY = ("#fffaf6", "#fffaf6")
INK = ("#1a1915", "#f3f1ea")
MUTED = ("#746e66", "#a39e94")
SOFT = ("#f6ebe4", "#2a211c")
CLAY_TEXT = ("#a84e32", "#e7b2a1")
SURFACE_2 = ("#f3f0e8", "#1c1c19")
LINE = ("#e6e1d6", "#2a2a26")
CARD = ("#fffcf8", "#161614")

PILLS = ("Ruido", "Tokens", "Variantes", "Stems", "Lemas", "Final")
MUESTRA_BOTONES = (
    (0, "Ruido"),
    (1, "Morfología"),
    (2, "Variantes"),
    (3, "Dataset"),
)


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Limpieza de texto")
        self.geometry("1180x780")
        self.minsize(1020, 700)
        self._fuentes()
        self.resultados: list[pipeline.Resultado] = []
        self.indice = 0
        self.paso = 0
        self._muestra = -1
        self._cargando = False
        self.fuente_url = ""
        self._etiquetas: list[str] = []
        self._armar()
        self._cargar(0)

    def _fuentes(self):
        self.f_titulo = ctk.CTkFont(family="Georgia", size=30)
        self.f_serif = ctk.CTkFont(family="Georgia", size=22)
        self.f_ui = ctk.CTkFont(family="Segoe UI", size=13)
        self.f_small = ctk.CTkFont(family="Segoe UI", size=12)
        self.f_kicker = ctk.CTkFont(family="Segoe UI", size=11)
        self.f_btn = ctk.CTkFont(family="Segoe UI", size=14)
        self.f_mono = ctk.CTkFont(family="Consolas", size=14)
        self.f_mono_s = ctk.CTkFont(family="Consolas", size=12)

    def _armar(self):
        self.grid_columnconfigure(0, weight=0, minsize=400)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._header()
        self._columna_entrada()
        self._columna_recorrido()
        self.bind("<Control-Return>", self._atajo)

    def _header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=28, pady=(22, 4))
        header.grid_columnconfigure(0, weight=1)
        izq = ctk.CTkFrame(header, fg_color="transparent")
        izq.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(izq, text="REDES SOCIALES", font=self.f_kicker, text_color=CLAY_TEXT).pack(anchor="w")
        ctk.CTkLabel(izq, text="Limpieza de texto", font=self.f_titulo, text_color=INK).pack(anchor="w", pady=(2, 0))
        ctk.CTkLabel(
            izq,
            text="ruido   →   tokens   →   variantes   →   stems  |  lemas   →   normalizado",
            font=self.f_small,
            text_color=MUTED,
        ).pack(anchor="w", pady=(2, 0))
        self.switch = ctk.CTkSwitch(header, text="Oscuro", font=self.f_small, command=self._tema)
        self.switch.grid(row=0, column=1, sticky="e", padx=(16, 0))

    def _columna_entrada(self):
        card = ctk.CTkFrame(self, fg_color=CARD, border_width=1, border_color=LINE, corner_radius=12)
        card.grid(row=1, column=0, sticky="nsew", padx=(28, 8), pady=(12, 22))
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(card, text="ENTRADA", font=self.f_kicker, text_color=MUTED).grid(
            row=0, column=0, sticky="w", padx=18, pady=(16, 0)
        )
        ctk.CTkLabel(
            card,
            text="Una publicación, o un dataset con una por línea.",
            font=self.f_small,
            text_color=MUTED,
        ).grid(row=1, column=0, sticky="w", padx=18, pady=(2, 8))

        self.entrada = ctk.CTkTextbox(
            card, font=self.f_ui, corner_radius=8, border_width=1, border_spacing=8, wrap="word"
        )
        self.entrada.grid(row=2, column=0, sticky="nsew", padx=18)
        self.entrada.bind("<KeyRelease>", self._editado)
        self.entrada.bind("<Control-Return>", self._atajo)

        self.contador = ctk.CTkLabel(card, text="", font=self.f_kicker, text_color=MUTED)
        self.contador.grid(row=3, column=0, sticky="w", padx=18, pady=(6, 8))

        muestras = ctk.CTkFrame(card, fg_color="transparent")
        muestras.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 12))
        self._muestra_btns = []
        for col, (indice, nombre) in enumerate(MUESTRA_BOTONES):
            muestras.grid_columnconfigure(col, weight=1)
            boton = ctk.CTkButton(
                muestras,
                text=nombre,
                height=30,
                font=self.f_small,
                corner_radius=8,
                border_width=1,
                command=lambda i=indice: self._cargar(i),
            )
            boton.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 4, 0))
            self._muestra_btns.append(boton)

        ctk.CTkLabel(card, text="INTERNET", font=self.f_kicker, text_color=MUTED).grid(
            row=5, column=0, sticky="w", padx=18, pady=(0, 6)
        )
        url_marco = ctk.CTkFrame(card, fg_color="transparent")
        url_marco.grid(row=6, column=0, sticky="ew", padx=18, pady=(0, 4))
        url_marco.grid_columnconfigure(0, weight=1)
        self.url_entry = ctk.CTkEntry(
            url_marco,
            font=self.f_small,
            corner_radius=8,
            border_width=1,
            placeholder_text=fuente.EJEMPLO,
        )
        self.url_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.url_entry.insert(0, fuente.EJEMPLO)
        self.boton_traer = ctk.CTkButton(
            url_marco,
            text="Traer",
            width=90,
            height=30,
            font=self.f_small,
            corner_radius=8,
            command=self._traer,
        )
        self.boton_traer.grid(row=0, column=1, sticky="e")
        self.fuente_estado = ctk.CTkLabel(
            card, text="", font=self.f_kicker, text_color=MUTED, wraplength=340, justify="left"
        )
        self.fuente_estado.grid(row=7, column=0, sticky="w", padx=18, pady=(0, 12))

        ctk.CTkLabel(card, text="OPCIONES", font=self.f_kicker, text_color=MUTED).grid(
            row=8, column=0, sticky="w", padx=18, pady=(0, 6)
        )
        checks = ctk.CTkFrame(card, fg_color="transparent")
        checks.grid(row=9, column=0, sticky="ew", padx=18, pady=(0, 12))
        checks.grid_columnconfigure((0, 1), weight=1)
        self.checks = {}
        opciones = (
            ("urls", "URLs"),
            ("menciones", "Menciones"),
            ("hashtag", "Palabra del hashtag"),
            ("emojis", "Emojis"),
            ("elongacion", "Elongación"),
            ("variantes", "Variantes"),
            ("stopwords", "Stopwords al final"),
        )
        for i, (clave, texto) in enumerate(opciones):
            box = ctk.CTkCheckBox(checks, text=texto, font=self.f_small, checkbox_width=18, checkbox_height=18)
            box.select()
            box.grid(row=i // 2, column=i % 2, sticky="w", pady=3, padx=(0, 8))
            self.checks[clave] = box

        ctk.CTkButton(
            card,
            text="Ejecutar pipeline",
            height=42,
            font=self.f_btn,
            corner_radius=8,
            command=self._ejecutar,
        ).grid(row=10, column=0, sticky="ew", padx=18, pady=(0, 6))
        ctk.CTkLabel(card, text="Ctrl + Enter", font=self.f_kicker, text_color=MUTED).grid(
            row=11, column=0, sticky="w", padx=18, pady=(0, 14)
        )
        self._marcar_muestra(-1)

    def _columna_recorrido(self):
        card = ctk.CTkFrame(self, fg_color=CARD, border_width=1, border_color=LINE, corner_radius=12)
        card.grid(row=1, column=1, sticky="nsew", padx=(8, 28), pady=(12, 22))
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(6, weight=1)

        self.selector_host = ctk.CTkFrame(card, fg_color="transparent")
        self.selector_host.grid(row=0, column=0, sticky="ew", padx=18)
        self.fuente_mostrar = ctk.CTkLabel(
            card, text="", font=self.f_kicker, text_color=MUTED, wraplength=560, justify="left"
        )
        self.fuente_mostrar.grid(row=1, column=0, sticky="w", padx=18, pady=(2, 0))

        pills = ctk.CTkFrame(card, fg_color="transparent")
        pills.grid(row=2, column=0, sticky="ew", padx=14, pady=(10, 8))
        self._pills = []
        for i, nombre in enumerate(PILLS):
            pills.grid_columnconfigure(i, weight=1, uniform="pasos")
            boton = ctk.CTkButton(
                pills,
                text=nombre,
                height=32,
                font=self.f_small,
                corner_radius=8,
                command=lambda n=i: self._ir(n),
            )
            boton.grid(row=0, column=i, sticky="ew", padx=3)
            self._pills.append(boton)

        titulo = ctk.CTkFrame(card, fg_color="transparent")
        titulo.grid(row=3, column=0, sticky="w", padx=18, pady=(4, 8))
        self.numero = ctk.CTkLabel(titulo, text="01", font=self.f_serif, text_color=CLAY)
        self.heading = ctk.CTkLabel(titulo, text="Ruido", font=self.f_serif, text_color=INK)
        self.numero.pack(side="left")
        self.heading.pack(side="left", padx=(10, 0))

        self.callout = ctk.CTkFrame(card, fg_color=SOFT, corner_radius=10)
        self.callout.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 8))
        ctk.CTkLabel(self.callout, text="QUÉ HACE ESTE PASO", font=self.f_kicker, text_color=CLAY_TEXT).pack(
            anchor="w", padx=14, pady=(10, 2)
        )
        self.explicacion = ctk.CTkLabel(
            self.callout, text="", font=self.f_ui, text_color=INK, justify="left", anchor="w", wraplength=560
        )
        self.explicacion.pack(anchor="w", fill="x", padx=14, pady=(0, 12))
        self.callout.bind("<Configure>", self._wrap)

        barra = ctk.CTkFrame(card, fg_color="transparent")
        barra.grid(row=5, column=0, sticky="ew", padx=18, pady=(2, 4))
        barra.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(barra, text="SALIDA", font=self.f_kicker, text_color=MUTED).grid(row=0, column=0, sticky="w")
        self.metrica = ctk.CTkLabel(barra, text="", font=self.f_kicker, text_color=MUTED)
        self.metrica.grid(row=0, column=1, sticky="e")

        self.salida = ctk.CTkTextbox(
            card, font=self.f_mono, corner_radius=8, border_width=1, border_spacing=10, wrap="word"
        )
        self.salida.grid(row=6, column=0, sticky="nsew", padx=18)

        ctk.CTkLabel(card, text="REGISTRO", font=self.f_kicker, text_color=MUTED).grid(
            row=7, column=0, sticky="w", padx=18, pady=(8, 4)
        )
        self.detalle = ctk.CTkTextbox(
            card, font=self.f_mono_s, height=118, corner_radius=8, border_width=1, border_spacing=8, wrap="none"
        )
        self.detalle.grid(row=8, column=0, sticky="ew", padx=18, pady=(0, 16))

    def _wrap(self, event):
        if event.width > 80:
            self.explicacion.configure(wraplength=event.width - 28)

    def _tema(self):
        ctk.set_appearance_mode("dark" if self.switch.get() else "light")
        self._pintar_pills()
        self._marcar_muestra(self._muestra)

    def _atajo(self, _event=None):
        self._ejecutar()
        return "break"

    def _editado(self, _event=None):
        if self._cargando:
            return
        if self._muestra != -1:
            self._muestra = -1
            self._marcar_muestra(-1)
        self._contar()

    def _contar(self):
        texto = self.entrada.get("1.0", "end").strip()
        lineas = [ln for ln in texto.splitlines() if ln.strip()]
        extra = f"   ·   {len(lineas)} publicaciones" if len(lineas) > 1 else ""
        self.contador.configure(text=f"{len(texto)} caracteres{extra}")

    def _marcar_muestra(self, indice: int):
        self._muestra = indice
        for i, boton in enumerate(self._muestra_btns):
            if i == indice:
                boton.configure(fg_color=SOFT, hover_color=SOFT, text_color=CLAY_TEXT, border_color=CLAY)
            else:
                boton.configure(
                    fg_color="transparent", hover_color=SURFACE_2, text_color=INK, border_color=LINE
                )

    def _pintar_pills(self):
        for i, boton in enumerate(self._pills):
            if i == self.paso:
                boton.configure(fg_color=CLAY, hover_color=CLAY_HOVER, text_color=ON_CLAY)
            else:
                boton.configure(fg_color=SURFACE_2, hover_color=LINE, text_color=INK)

    def _cargar(self, indice: int):
        self._cargando = True
        texto = "\n".join(pipeline.MUESTRAS) if indice == 3 else pipeline.MUESTRAS[indice]
        self.entrada.delete("1.0", "end")
        self.entrada.insert("1.0", texto)
        self._cargando = False
        self.fuente_url = ""
        self.fuente_estado.configure(text="")
        self._marcar_muestra(indice)
        self._contar()
        self._ejecutar()

    def _traer(self):
        url = self.url_entry.get().strip() or fuente.EJEMPLO
        self.boton_traer.configure(state="disabled", text="…")
        self.fuente_estado.configure(text=f"trayendo {url}")
        hilo = threading.Thread(target=self._traer_fondo, args=(url,), daemon=True)
        hilo.start()

    def _traer_fondo(self, url: str):
        try:
            texto, nota = fuente.traer(url)
        except Exception as exc:
            self.after(0, lambda: self._traer_fin("", f"error: {exc}"))
            return
        self.after(0, lambda: self._traer_fin(texto, nota))

    def _traer_fin(self, texto: str, nota: str):
        self.boton_traer.configure(state="normal", text="Traer")
        if not texto:
            self.fuente_estado.configure(text=nota)
            return
        self.fuente_url = nota
        self.fuente_estado.configure(text=f"fuente: {nota}")
        self._cargando = True
        self.entrada.delete("1.0", "end")
        self.entrada.insert("1.0", texto)
        self._cargando = False
        self._marcar_muestra(-1)
        self.indice = 0
        self._contar()
        self._ejecutar()

    def _opciones(self) -> pipeline.Opciones:
        return pipeline.Opciones(
            urls=bool(self.checks["urls"].get()),
            menciones=bool(self.checks["menciones"].get()),
            hashtag_palabra=bool(self.checks["hashtag"].get()),
            emojis=bool(self.checks["emojis"].get()),
            elongacion=bool(self.checks["elongacion"].get()),
            variantes=bool(self.checks["variantes"].get()),
            stopwords=bool(self.checks["stopwords"].get()),
        )

    def _ejecutar(self):
        crudo = self.entrada.get("1.0", "end").strip()
        lineas = [ln.strip() for ln in crudo.splitlines() if ln.strip()] or [""]
        try:
            self.resultados = [pipeline.procesar(ln, self._opciones()) for ln in lineas]
        except Exception as exc:
            self.resultados = []
            self._texto(self.salida, f"{type(exc).__name__}: {exc}")
            self._texto(self.detalle, "")
            return
        if self.indice >= len(self.resultados):
            self.indice = 0
        self._selector()
        self._mostrar()

    def _selector(self):
        for widget in self.selector_host.winfo_children():
            widget.destroy()
        self._etiquetas = []
        if len(self.resultados) < 2:
            return
        for i, resultado in enumerate(self.resultados):
            corto = resultado.normalizado or "(vacío)"
            if len(corto) > 52:
                corto = corto[:51] + "…"
            self._etiquetas.append(f"{i + 1}    {corto}")
        menu = ctk.CTkOptionMenu(
            self.selector_host,
            values=self._etiquetas,
            command=self._elegir,
            font=self.f_small,
            dropdown_font=self.f_small,
            height=32,
            dynamic_resizing=False,
            fg_color=SURFACE_2,
            button_color=LINE,
            button_hover_color=CLAY,
            text_color=INK,
            dropdown_fg_color=CARD,
            dropdown_hover_color=SOFT,
            dropdown_text_color=INK,
        )
        menu.pack(fill="x", pady=(14, 0))
        menu.set(self._etiquetas[self.indice])

    def _elegir(self, valor: str):
        self.indice = self._etiquetas.index(valor)
        self._mostrar()

    def _ir(self, paso: int):
        self.paso = paso
        if self.resultados:
            self._mostrar()
        else:
            self._pintar_pills()

    def _cuerpo(self, paso: pipeline.Paso) -> str:
        if paso.clave != "normalizado" or len(self.resultados) < 2:
            return paso.cuerpo
        lineas = [paso.cuerpo, "", "dataset"]
        for i, resultado in enumerate(self.resultados):
            marca = "·" if i == self.indice else " "
            lineas.append(f"{marca} {i + 1}    {resultado.normalizado}")
        return "\n".join(lineas)

    def _mostrar(self):
        if not self.resultados:
            return
        paso = self.resultados[self.indice].pasos[self.paso]
        self._pintar_pills()
        self.fuente_mostrar.configure(text=f"fuente: {self.fuente_url}" if self.fuente_url else "")
        self.numero.configure(text=f"{self.paso + 1:02d}")
        self.heading.configure(text=paso.titulo)
        self.explicacion.configure(text=paso.explicacion)
        metrica = paso.metrica
        if len(self.resultados) > 1:
            metrica = f"{self.indice + 1} / {len(self.resultados)}    ·    {metrica}"
        self.metrica.configure(text=metrica)
        self.salida.configure(wrap="word" if paso.clave in {"ruido", "normalizado"} else "none")
        self._texto(self.salida, self._cuerpo(paso))
        self._texto(self.detalle, paso.detalle)

    def _texto(self, caja: ctk.CTkTextbox, texto: str):
        caja.delete("1.0", "end")
        caja.insert("1.0", texto)
        caja.see("1.0")


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
