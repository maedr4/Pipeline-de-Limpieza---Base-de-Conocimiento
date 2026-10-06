"""Pipeline de limpieza para texto de redes sociales.

La ventana está en app.py. Acá está el proceso, en orden, sin cajas negras:

    crudo
      → ruido          la cadena todavía no son palabras
      → tokens         segmentación léxica
      → variantes      q, xq, tildes omitidas
      → stems          ┐ mismo token, dos salidas
      → lemas          ┘ no se lematiza un stem
      → normalizado    lemas de contenido, sin stopwords

Stemming y lematización no se encadenan. Un stem no es una palabra
(corrieron → corr). Un lema sí (corrieron → correr). El dataset guarda lemas.

Techo, a propósito: léxico cerrado, sin POS, sin Snowball, sin derivación
(buenísimo no vuelve a bueno). Lo que no entra en una regla queda como está
y el registro lo dice. Eso es el punto de la clase, no un hueco escondido.
"""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Tipos
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Opciones:
    urls: bool = True
    menciones: bool = True
    hashtag_palabra: bool = True  # False = se borra el hashtag entero
    emojis: bool = True
    elongacion: bool = True
    variantes: bool = True
    stopwords: bool = True


@dataclass(frozen=True)
class Paso:
    clave: str
    titulo: str
    explicacion: str
    cuerpo: str
    detalle: str
    metrica: str


@dataclass(frozen=True)
class Resultado:
    pasos: tuple[Paso, ...]
    tokens: tuple[str, ...]
    stems: tuple[str, ...]
    lemas: tuple[str, ...]
    normalizado: str


# ---------------------------------------------------------------------------
# Patrones de ruido. Se aplican sobre la cadena, antes de que existan tokens.
# ---------------------------------------------------------------------------

URL_RE = re.compile(r"https?://[^\s]+|www\.[^\s]+", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.\w+\b")
MENCION_RE = re.compile(r"@[\w.]+")
HASHTAG_RE = re.compile(r"#([A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9_]+)")
EMOJI_RE = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F900-\U0001F9FF"
    "\u200d"
    "\ufe0f"
    "]+"
)
EMOTICON_RE = re.compile(r"(?:[:;8][-^']?[)D(Pp/\\])|(?:[)(D][-^']?[:;])|<3")
RISA_RE = re.compile(
    r"\b(?:(?:ja){2,}j?|(?:je){2,}j?|(?:ji){2,}j?|lol+|lmao+|xd+|jjj+)\b",
    re.IGNORECASE,
)
RT_RE = re.compile(r"(?:^|\s)rt\b[:\s]*", re.IGNORECASE)
ELONG_RE = re.compile(r"[a-záéíóúüñ]*([a-záéíóúüñ])\1{2,}[a-záéíóúüñ]*")
TOKEN_RE = re.compile(r"[a-záéíóúüñ]+")

# Un token es esto. Se muestra tal cual en el paso de tokenización.
TOKEN_PATRON = "[a-záéíóúüñ]+"


# ---------------------------------------------------------------------------
# Stopwords. Se aplican al final, sobre lemas, no antes.
# no / sin / ni / nunca / jamás / tampoco / nada / nadie no están:
# son polaridad. Borrar "no" invierte el sentido de un dataset de sentimiento.
# sí (afirmación) se conserva; si (condicional) se quita.
# ser, estar, haber e ir se tratan como funcionales una vez lematizados.
# ---------------------------------------------------------------------------

STOPWORDS = frozenset(
    """
    a al ante bajo con contra de del desde durante en entre hacia hasta
    para por segun según sobre tras
    el la los las un una unos unas
    y e o u
    que qué quien quienes cuyo cuya cuyos cuyas
    como cómo cuando donde dónde
    su sus mi mis tu tus me te se nos os le les lo
    ya muy tan tanto más mas menos
    pero porque pues aunque mientras si
    todo toda todos todas cada
    otro otra otros otras
    este esta estos estas ese esa eso esos esas esto
    algo alguien
    poco poca pocos pocas
    ser estar haber ir
    es son era eran fue fueron soy eres somos
    está estan están estoy estamos
    ha han hay he has
    rt
    """.split()
)

# Formas que el stemmer no corta: no tienen morfología léxica que nos importe.
# "estaban" no está acá (su lema sí). Por eso el stem de estaban sí se ve.


# ---------------------------------------------------------------------------
# Variantes de redes. Lista cerrada. No es un corrector ortográfico.
# d → de y x → por son ambiguas; el paso entero se puede apagar.
# ---------------------------------------------------------------------------

VARIANTES: dict[str, tuple[str, str]] = {
    "q": ("que", "abreviatura"),
    "k": ("que", "abreviatura"),
    "ke": ("que", "abreviatura"),
    "qe": ("que", "abreviatura"),
    "xq": ("porque", "abreviatura"),
    "pq": ("porque", "abreviatura"),
    "xk": ("porque", "abreviatura"),
    "x": ("por", "abreviatura"),
    "d": ("de", "abreviatura"),
    "tb": ("también", "abreviatura"),
    "tmb": ("también", "abreviatura"),
    "tbn": ("también", "abreviatura"),
    "bn": ("bien", "abreviatura"),
    "xfa": ("por favor", "abreviatura"),
    "porfa": ("por favor", "abreviatura"),
    "porfis": ("por favor", "abreviatura"),
    "pa": ("para", "abreviatura"),
    "pal": ("para el", "abreviatura"),
    "toy": ("estoy", "abreviatura"),
    "tas": ("estás", "abreviatura"),
    "sta": ("está", "abreviatura"),
    "ps": ("pues", "abreviatura"),
    "dia": ("día", "tilde omitida"),
    "dias": ("días", "tilde omitida"),
    "pesimo": ("pésimo", "tilde omitida"),
    "pesima": ("pésima", "tilde omitida"),
    "buenisimo": ("buenísimo", "tilde omitida"),
    "buenisima": ("buenísima", "tilde omitida"),
    "muchisimo": ("muchísimo", "tilde omitida"),
    "muchisima": ("muchísima", "tilde omitida"),
    "historico": ("histórico", "tilde omitida"),
    "historica": ("histórica", "tilde omitida"),
    "historicos": ("históricos", "tilde omitida"),
    "historicas": ("históricas", "tilde omitida"),
    "tambien": ("también", "tilde omitida"),
    "futbol": ("fútbol", "tilde omitida"),
    "atencion": ("atención", "tilde omitida"),
    "economia": ("economía", "tilde omitida"),
    "numero": ("número", "tilde omitida"),
    "mas": ("más", "tilde omitida"),
}

RISAS_TOKEN = frozenset(
    {"jaja", "jajaja", "jajajaja", "jeje", "jejeje", "jiji", "lol", "lmao", "xd", "jjj"}
)


# ---------------------------------------------------------------------------
# Stemmer de sufijos. Un solo corte: gana el sufijo más largo que deje
# una raíz de al menos `minima` letras. No es Snowball.
# ponytail: un corte, no el algoritmo completo. Los irregulares que no
# terminan en estos sufijos se quedan como están; eso lo resuelve el lema.
# ---------------------------------------------------------------------------

SUFIJOS: tuple[tuple[str, int], ...] = (
    ("amientos", 3),
    ("imientos", 3),
    ("aciones", 3),
    ("iciones", 3),
    ("adoras", 3),
    ("adores", 3),
    ("amiento", 3),
    ("imiento", 3),
    ("ciones", 3),
    ("siones", 3),
    ("encia", 3),
    ("ancia", 3),
    ("mente", 3),
    ("ando", 3),
    ("iendo", 3),
    ("aron", 3),
    ("ieron", 3),
    ("aban", 3),
    ("ian", 3),
    ("cion", 3),
    ("sion", 3),
    ("ados", 3),
    ("adas", 3),
    ("idos", 3),
    ("idas", 3),
    ("amos", 3),
    ("emos", 3),
    ("imos", 3),
    ("aste", 3),
    ("iste", 3),
    ("ado", 3),
    ("ada", 3),
    ("ido", 3),
    ("ida", 3),
    ("os", 3),
    ("as", 3),
    ("es", 3),
)

# Clíticos que se separan solo si el resto parece un verbo (creerlo → creer).
# "estable" no se parte: el resto no es verbo. Un solo clítico, no "dímelo".
CLITICOS = ("nos", "los", "las", "les", "me", "te", "se", "lo", "la", "le")


# ---------------------------------------------------------------------------
# Léxico. Los regulares no se escriben a mano: se genera el paradigma y se
# tiran las formas que ya son stopword o sustantivo (sin POS no se desambigua,
# y preferimos no inventar un verbo para "como" o "partido").
# Los irregulares sí están escritos: no hay regla de sufijo que los cubra.
# ---------------------------------------------------------------------------

VERBOS_REGULARES = {
    "ar": """
        comentar visitar funcionar llevar esperar comprar celebrar hablar
        mirar usar pagar llegar terminar pasar quedar gustar necesitar
        trabajar llamar dejar buscar bailar
    """.split(),
    "er": """
        correr responder comer vender aprender comprender meter
    """.split(),
    "ir": """
        subir vivir abrir escribir recibir permitir asistir decidir
        existir ocurrir
    """.split(),
}

# esta/estas no están: sin tilde son demostrativos. "está" sí.
# hacia no está: es preposición, y "hacía" sin tilde se le confundiría.
IRREGULARES: dict[str, str] = {
    "ser": "ser",
    "soy": "ser", "eres": "ser", "es": "ser", "somos": "ser", "son": "ser",
    "fui": "ser", "fue": "ser", "fuimos": "ser", "fueron": "ser",
    "era": "ser", "eras": "ser", "éramos": "ser", "eramos": "ser", "eran": "ser",
    "sea": "ser", "sean": "ser", "sido": "ser", "siendo": "ser",
    "estar": "estar",
    "estoy": "estar", "estás": "estar", "está": "estar",
    "estamos": "estar", "están": "estar",
    "estuve": "estar", "estuviste": "estar", "estuvo": "estar", "estuvieron": "estar",
    "estaba": "estar", "estabas": "estar", "estábamos": "estar",
    "estabamos": "estar", "estaban": "estar", "estando": "estar",
    "ir": "ir",
    "voy": "ir", "vas": "ir", "va": "ir", "vamos": "ir", "van": "ir",
    "iba": "ir", "ibas": "ir", "íbamos": "ir", "ibamos": "ir", "iban": "ir",
    "yendo": "ir",
    "haber": "haber",
    "he": "haber", "has": "haber", "ha": "haber", "hemos": "haber", "han": "haber",
    "hay": "haber", "hubo": "haber", "había": "haber", "habia": "haber",
    "tener": "tener",
    "tengo": "tener", "tiene": "tener", "tienen": "tener", "tienes": "tener",
    "tuve": "tener", "tuvo": "tener", "tuvieron": "tener",
    "tenía": "tener", "tenia": "tener", "teniendo": "tener", "tenido": "tener",
    "hacer": "hacer",
    "hago": "hacer", "hace": "hacer", "hacen": "hacer", "haces": "hacer",
    "hice": "hacer", "hizo": "hacer", "hicieron": "hacer",
    "hacía": "hacer", "haciendo": "hacer", "hecho": "hacer",
    "poder": "poder",
    "puedo": "poder", "puede": "poder", "pueden": "poder", "puedes": "poder",
    "pude": "poder", "pudo": "poder", "pudieron": "poder",
    "podía": "poder", "podia": "poder", "pudiendo": "poder",
    "decir": "decir",
    "digo": "decir", "dice": "decir", "dicen": "decir", "dices": "decir",
    "dije": "decir", "dijo": "decir", "dijeron": "decir",
    "decía": "decir", "diciendo": "decir", "dicho": "decir",
    "ver": "ver",
    "veo": "ver", "ves": "ver", "ve": "ver", "ven": "ver", "vemos": "ver",
    "vio": "ver", "vieron": "ver", "viendo": "ver", "visto": "ver",
    "dar": "dar",
    "doy": "dar", "das": "dar", "da": "dar", "dan": "dar", "damos": "dar",
    "dio": "dar", "dieron": "dar", "dando": "dar", "dado": "dar",
    "saber": "saber",
    "sé": "saber", "sabes": "saber", "sabe": "saber", "saben": "saber",
    "supe": "saber", "supo": "saber", "sabiendo": "saber",
    "querer": "querer",
    "quiero": "querer", "quiere": "querer", "quieren": "querer",
    "quise": "querer", "quiso": "querer", "queriendo": "querer",
    "venir": "venir",
    "vengo": "venir", "viene": "venir", "vienen": "venir",
    "vine": "venir", "vino": "venir", "vinieron": "venir", "viniendo": "venir",
    "poner": "poner",
    "pongo": "poner", "pone": "poner", "ponen": "poner",
    "puse": "poner", "puso": "poner", "poniendo": "poner", "puesto": "poner",
    "salir": "salir",
    "salgo": "salir", "sale": "salir", "salen": "salir",
    "salió": "salir", "salio": "salir", "salieron": "salir", "saliendo": "salir",
    # creer no se genera como regular: el pretérito es creyó, no creió.
    "creer": "creer", "creo": "creer", "crees": "creer", "cree": "creer",
    "creemos": "creer", "creen": "creer", "creí": "creer", "creyó": "creer",
    "creyeron": "creer", "creyendo": "creer", "creído": "creer",
    # participios que el generador no puede armar
    "abierto": "abrir", "abierta": "abrir",
    "escrito": "escribir", "escrita": "escribir",
}

# Alternancia vocálica: no es un sufijo, es otra forma del tema. Lista.
ALTERNANTES = {
    "encuentro": "encontrar", "encuentra": "encontrar", "encuentran": "encontrar",
    "empiezo": "empezar", "empieza": "empezar", "empiezan": "empezar",
    "pido": "pedir", "pide": "pedir", "piden": "pedir",
    "siento": "sentir", "siente": "sentir", "sienten": "sentir",
    "duermo": "dormir", "duerme": "dormir", "duermen": "dormir",
    "sigo": "seguir", "sigue": "seguir", "siguen": "seguir",
}

# Homógrafos. El registro lo dice; sin POS no hay más que una convención.
AMBIGUOS = {
    "fue": "ser o ir",
    "fui": "ser o ir",
    "fueron": "ser o ir",
    "fuimos": "ser o ir",
    "ve": "ver o ir",
    "vino": "venir o el sustantivo",
    "era": "ser o el sustantivo",
}

SUSTANTIVOS = frozenset(
    """
    servicio vez atención cliente onda usuario partido jugador tiempo
    fútbol app día desastre precio gente presidente elección votante
    calle casa cosa persona año país gobierno empresa trabajo problema
    mundo vida mano parte caso grupo sistema programa estado número
    pregunta respuesta mensaje comentario foto video amigo familia
    ciudad equipo gol hora noche mañana semana mes clase profesor
    estudiante dinero cuenta salud uso mercado pasado comida entrada
    salida economía cliente atención jugador usuario precio calle
    votante elección presidente desastre
    """.split()
)

ADJETIVOS = frozenset(
    """
    pésimo pésima buenísimo buenísima muchísimo muchísima
    histórico histórica bueno malo grande nuevo mejor peor
    público social político económico nacional
    """.split()
)

# Temas -ir para la regla abierta de gerundio, cuando el verbo no está en el diccionario.
TEMAS_IR = frozenset(
    "viv sal ven sent dorm segu serv pid recib permit asist decid exist sub escrib abr".split()
)


_ACENTOS = str.maketrans("áéíóúüÁÉÍÓÚÜ", "aeiouuAEIOUU")


def sin_acentos(texto: str) -> str:
    """Quita tildes. La ñ se queda: es otra letra, no un acento."""
    return texto.translate(_ACENTOS)


def _paradigma(infinitivo: str) -> dict[str, str]:
    """Formas de un verbo regular. Las ambiguas se filtran después."""
    tema, conj = infinitivo[:-2], infinitivo[-2:]
    if conj == "ar":
        sufijos = (
            "o", "as", "a", "amos", "an",
            "é", "e", "aste", "ó", "aron",
            "aba", "abas", "ábamos", "abamos", "aban",
            "ando", "ado", "ada", "ados", "adas",
            "aré", "arás", "ará", "aremos", "arán",
            "aría", "arías", "aríamos", "arían",
            "e", "es", "emos", "en",
        )
    elif conj == "er":
        sufijos = (
            "o", "es", "e", "emos", "en",
            "í", "i", "iste", "ió", "io", "ieron",
            "ía", "ia", "ías", "ias", "íamos", "iamos", "ían", "ian",
            "iendo", "ido", "ida", "idos", "idas",
            "eré", "erá", "eremos", "erán",
            "ería", "erían",
            "a", "as", "amos", "an",
        )
    elif conj == "ir":
        sufijos = (
            "o", "es", "e", "imos", "en",
            "í", "i", "iste", "ió", "io", "ieron",
            "ía", "ia", "ías", "ias", "íamos", "iamos", "ían", "ian",
            "iendo", "ido", "ida", "idos", "idas",
            "iré", "irá", "iremos", "irán",
            "iría", "irían",
            "a", "as", "amos", "an",
        )
    else:
        raise ValueError(infinitivo)
    formas = {infinitivo: infinitivo}
    for sufijo in sufijos:
        formas[tema + sufijo] = infinitivo
    return formas


def _armar_diccionario() -> dict[str, tuple[str, str]]:
    """token → (lema, de dónde salió). El origen se imprime en el registro."""
    fuente: dict[str, tuple[str, str]] = {}
    bloqueo = STOPWORDS | SUSTANTIVOS
    for grupo in VERBOS_REGULARES.values():
        for infinitivo in grupo:
            for forma, lema in _paradigma(infinitivo).items():
                if forma in bloqueo:
                    continue
                fuente[forma] = (lema, "paradigma regular")
    for forma, lema in IRREGULARES.items():
        fuente[forma] = (lema, "irregular")
    for forma, lema in ALTERNANTES.items():
        fuente[forma] = (lema, "alternancia vocálica")
    # partido es sustantivo en este léxico. Si algún día se genera como
    # participio de partir, esta línea gana. Hoy partir no está en la lista.
    fuente["partido"] = ("partido", "sustantivo; no es partir")
    return fuente


FUENTE = _armar_diccionario()
# Solo para reconocer el resto de un clítico. No se usa para lematizar:
# si no, "esta" sin tilde caería en "está" → estar.
FUENTE_PLANO = {sin_acentos(k): k for k in FUENTE}

LEXICO = (
    SUSTANTIVOS
    | ADJETIVOS
    | STOPWORDS
    | set(FUENTE)
    | {lema for lema, _ in FUENTE.values()}
    | {sin_acentos(k) for k in FUENTE}
)

CONOCIDAS = LEXICO | {"no", "si", "sí", "hola", "gracias", "ok", "bueno"}

SUFIJOS_LARGOS = tuple(sorted(SUFIJOS, key=lambda par: len(par[0]), reverse=True))


# ---------------------------------------------------------------------------
# Presentación
# ---------------------------------------------------------------------------

def _columnas(filas: list[tuple[str, ...]]) -> str:
    if not filas:
        return "—"
    anchos = [max(len(fila[i]) for fila in filas) for i in range(len(filas[0]))]
    lineas = []
    for fila in filas:
        partes = []
        for i, celda in enumerate(fila):
            partes.append(celda.ljust(anchos[i]) if i < len(anchos) - 1 else celda)
        lineas.append("  ".join(partes))
    return "\n".join(lineas)


def _numerar(tokens: list[str]) -> str:
    if not tokens:
        return "—"
    ancho = len(str(len(tokens)))
    return "\n".join(f"{i:>{ancho}}   {token}" for i, token in enumerate(tokens, 1))


def _fila(etiqueta: str, detalle: str) -> str:
    return f"{etiqueta:<18} {detalle}"


def partir_camel(texto: str) -> str:
    """#AtencionAlCliente → Atencion Al Cliente. Tiene que ocurrir antes de las minúsculas."""
    texto = re.sub(r"([a-záéíóúüñ])([A-ZÁÉÍÓÚÜÑ])", r"\1 \2", texto)
    texto = re.sub(r"([A-ZÁÉÍÓÚÜÑ]+)([A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ])", r"\1 \2", texto)
    return texto


# ---------------------------------------------------------------------------
# 1. Ruido
# ---------------------------------------------------------------------------

def _recortar_url(url: str) -> str:
    return url.rstrip(".,;:!?)]}")


def remover_ruido(texto: str, opciones: Opciones) -> tuple[str, list[str]]:
    """Limpia la cadena. Cada regla anota lo que encontró, aunque no haya nada."""
    log: list[str] = []
    original = texto

    texto = html.unescape(texto)
    texto = unicodedata.normalize("NFKC", texto)
    texto = texto.replace("\u200b", "").replace("\ufeff", "")
    if texto != original:
        log.append(_fila("unicode", "entidades HTML y NFKC"))
    else:
        log.append(_fila("unicode", "—"))

    rt = RT_RE.findall(texto)
    texto = RT_RE.sub(" ", texto)
    log.append(_fila("rt", ", ".join(s.strip() for s in rt) if rt else "—"))

    if opciones.urls:
        urls = [_recortar_url(u) for u in URL_RE.findall(texto)]
        texto = URL_RE.sub(" ", texto)
        log.append(_fila("urls", ", ".join(urls) if urls else "—"))
    else:
        log.append(_fila("urls", "desactivada"))

    emails = EMAIL_RE.findall(texto)
    texto = EMAIL_RE.sub(" ", texto)
    log.append(_fila("emails", ", ".join(emails) if emails else "—"))

    if opciones.menciones:
        menciones = MENCION_RE.findall(texto)
        texto = MENCION_RE.sub(" ", texto)
        log.append(_fila("menciones", ", ".join(menciones) if menciones else "—"))
    else:
        log.append(_fila("menciones", "desactivada"))

    hallados_hash: list[str] = []

    def _hash(m: re.Match[str]) -> str:
        crudo, palabra = m.group(0), m.group(1)
        if not opciones.hashtag_palabra:
            hallados_hash.append(f"{crudo} → eliminado")
            return " "
        partido = partir_camel(palabra)
        if partido != palabra:
            hallados_hash.append(f"{crudo} → {partido}")
        else:
            hallados_hash.append(f"{crudo} → {palabra}")
        return f" {partido} "

    texto = HASHTAG_RE.sub(_hash, texto)
    if hallados_hash:
        log.append(_fila("hashtags", " · ".join(hallados_hash)))
    else:
        log.append(_fila("hashtags", "—"))

    if opciones.emojis:
        emojis = EMOJI_RE.findall(texto)
        caras = EMOTICON_RE.findall(texto)
        texto = EMOJI_RE.sub(" ", texto)
        texto = EMOTICON_RE.sub(" ", texto)
        sacados = emojis + caras
        log.append(_fila("emojis", " ".join(sacados) if sacados else "—"))
    else:
        log.append(_fila("emojis", "desactivada"))

    risas = RISA_RE.findall(texto)
    texto = RISA_RE.sub(" ", texto)
    log.append(_fila("risas", ", ".join(risas) if risas else "—"))

    texto = texto.lower()
    log.append(_fila("minúsculas", "toda la cadena"))

    if opciones.elongacion:
        cambios: list[str] = []

        def _elong(m: re.Match[str]) -> str:
            palabra = m.group(0)
            corta = re.sub(r"(.)\1+", r"\1", palabra)
            media = re.sub(r"(.)\1{2,}", r"\1\1", palabra)
            nuevo = corta if corta in CONOCIDAS else media
            if nuevo != palabra:
                cambios.append(f"{palabra} → {nuevo}")
            return nuevo

        texto = ELONG_RE.sub(_elong, texto)
        log.append(_fila("elongación", ", ".join(cambios) if cambios else "—"))
    else:
        log.append(_fila("elongación", "desactivada"))

    digitos = re.findall(r"\d+", texto)
    texto = re.sub(r"\d+", " ", texto)
    log.append(_fila("dígitos", ", ".join(digitos) if digitos else "—"))

    signos = re.findall(r"[^a-záéíóúüñ\s]", texto)
    texto = re.sub(r"[^a-záéíóúüñ\s]+", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    log.append(_fila("puntuación", f"{len(signos)} signos → espacio" if signos else "—"))
    return texto, log


# ---------------------------------------------------------------------------
# 2. Tokens
# ---------------------------------------------------------------------------

def tokenizar(texto: str) -> list[str]:
    """Segmenta en unidades léxicas. No es split(): el patrón descarta lo que no es letra."""
    return TOKEN_RE.findall(texto)


# ---------------------------------------------------------------------------
# 3. Variantes
# ---------------------------------------------------------------------------

def normalizar_variantes(
    tokens: list[str], activas: bool
) -> tuple[list[str], list[str]]:
    """Equivalencia de grafía. Una abreviatura puede volverse dos tokens (xfa → por favor)."""
    if not activas:
        return list(tokens), ["desactivada: los tokens pasan igual"]
    salida: list[str] = []
    cambios: list[tuple[str, str, str]] = []
    for token in tokens:
        if token in RISAS_TOKEN:
            cambios.append((token, "—", "risa residual, se descarta"))
            continue
        if token in VARIANTES:
            reemplazo, clase = VARIANTES[token]
            partes = reemplazo.split()
            salida.extend(partes)
            cambios.append((token, " ".join(partes), clase))
            continue
        salida.append(token)
    sin_cambio = len(tokens) - len(cambios)
    detalle = [
        _columnas([(a, "→", b, c) for a, b, c in cambios]) if cambios else "Ningún token está en la lista.",
        "",
        f"sin cambio: {sin_cambio}",
    ]
    return salida, detalle


# ---------------------------------------------------------------------------
# 4. Stemming
# ---------------------------------------------------------------------------

def _parece_verbo(plano: str) -> bool:
    if plano in FUENTE_PLANO:
        return True
    return plano.endswith(("ar", "er", "ir", "ando", "iendo", "ado", "ido", "ada", "ida"))


def separar_clitico(token: str) -> tuple[str, str]:
    """creerlo → (creer, lo). estable no se toca."""
    plano = sin_acentos(token)
    for clitico in CLITICOS:
        if not plano.endswith(clitico):
            continue
        resto = plano[: -len(clitico)]
        if len(resto) < 4 or not _parece_verbo(resto):
            continue
        return token[: -len(clitico)], clitico
    return token, ""


def stem_token(token: str) -> tuple[str, str]:
    """Un corte. Devuelve (stem, regla que disparó)."""
    if token in STOPWORDS:
        return token, "stopword, no se stemma"
    resto, clitico = separar_clitico(token)
    prefijo = f"clítico -{clitico}; " if clitico else ""
    if len(resto) < 5:
        return resto, prefijo + "token corto"
    plano = sin_acentos(resto)
    for sufijo, minima in SUFIJOS_LARGOS:
        if plano.endswith(sufijo) and len(plano) - len(sufijo) >= minima:
            return plano[: -len(sufijo)], prefijo + f"-{sufijo}"
    return resto, prefijo + "sin sufijo"


# ---------------------------------------------------------------------------
# 5. Lematización
# ---------------------------------------------------------------------------

def _regla_abierta(token: str) -> tuple[str, str] | None:
    """Solo si el diccionario no tiene la forma. Sufijos poco ambiguos, o plural con singular conocido."""
    if token.endswith("ando") and len(token) > 6:
        return token[:-4] + "ar", "gerundio -ando → -ar"
    if token.endswith("iendo") and len(token) > 6:
        tema = token[:-5]
        if tema.endswith(("rr", "ll")):
            tema = tema[:-1]
        conj = "ir" if tema in TEMAS_IR else "er"
        return tema + conj, f"gerundio -iendo → -{conj}"
    if token.endswith("aron") and len(token) > 6:
        return token[:-4] + "ar", "pretérito -aron → -ar"
    if token.endswith("ieron") and len(token) > 6:
        tema = token[:-5]
        if tema.endswith(("rr", "ll")):
            tema = tema[:-1]
            return tema + "er", "pretérito -ieron → -er"
        if tema in TEMAS_IR:
            return tema + "ir", "pretérito -ieron → -ir"
        return None
    if token.endswith("ciones") and len(token) > 6:
        return token[:-6] + "ción", "plural -ciones → -ción"
    if token.endswith("siones") and len(token) > 6:
        return token[:-6] + "sión", "plural -siones → -sión"
    if len(token) > 4 and token.endswith("es") and token[-3] in "lrndzj":
        singular = token[:-2]
        if singular in LEXICO:
            return singular, "plural -es, singular en el léxico"
    if len(token) > 3 and token.endswith("s") and token[-2] in "aeiouáéíóúü":
        singular = token[:-1]
        if singular in LEXICO:
            return singular, "plural -s, singular en el léxico"
    return None


def lema_token(token: str) -> tuple[str, str]:
    """Diccionario, después reglas abiertas, después identidad. El clítico se anota y se descarta."""
    resto, clitico = separar_clitico(token)
    nota_clitico = f"clítico -{clitico}; " if clitico else ""
    hit = FUENTE.get(resto)
    if hit:
        lema, origen = hit
        nota = nota_clitico + origen
        if resto in AMBIGUOS:
            nota += f"; ambiguo ({AMBIGUOS[resto]}), se elige {lema}"
        return lema, nota
    abierta = _regla_abierta(resto)
    if abierta:
        lema, origen = abierta
        return lema, nota_clitico + origen
    return resto, nota_clitico + "identidad"


def lematizar(tokens: list[str]) -> tuple[list[str], list[tuple[str, str, str]]]:
    filas = []
    lemas = []
    for token in tokens:
        lema, regla = lema_token(token)
        lemas.append(lema)
        filas.append((token, lema, regla))
    return lemas, filas


# ---------------------------------------------------------------------------
# 6. Texto normalizado
# ---------------------------------------------------------------------------

def texto_normalizado(lemas: list[str], filtrar: bool) -> tuple[str, list[str]]:
    """Lemas de contenido, en orden. La negación no se filtra: no está en STOPWORDS."""
    if not filtrar:
        return " ".join(lemas), ["filtro de stopwords desactivado"]
    se_van = [lema for lema in lemas if lema in STOPWORDS]
    se_quedan = [lema for lema in lemas if lema and lema not in STOPWORDS]
    negacion = [lema for lema in se_quedan if lema in {"no", "sin", "ni", "nunca", "jamás", "tampoco", "nada", "nadie"}]
    detalle = [
        "se quitan al final, no antes: la morfología tiene que verse en los pasos anteriores",
        "",
        "retiradas: " + (", ".join(se_van) if se_van else "—"),
        "negación conservada: " + (", ".join(negacion) if negacion else "—"),
    ]
    return " ".join(se_quedan), detalle


# ---------------------------------------------------------------------------
# Orquestación. Esta función es el índice del pipeline.
# ---------------------------------------------------------------------------

EXPLICACION = {
    "ruido": (
        "Se limpia la cadena antes de tokenizar: URLs, menciones, emojis, risas y letras "
        "estiradas no son palabras. El hashtag se parte en CamelCase antes de las minúsculas; "
        "si no, #AtencionAlCliente queda como una sola ficha. Cada regla deja registro de lo que sacó."
    ),
    "tokens": (
        "Un token es una secuencia de letras, con ñ y tildes. El patrón es "
        f"{TOKEN_PATRON}. No es un split() ciego: descarta lo que no es letra. "
        "El orden importa: tokenizar la URL cruda parte https y t.co en basura. Por eso este paso va después del ruido."
    ),
    "variantes": (
        "Lista cerrada, token por token, no un corrector. Dos clases: abreviatura "
        "(xq → porque, q → que) y tilde omitida (dias → días). Si no está en la lista, no se toca. "
        "d → de y x → por son ambiguas: el paso se puede apagar."
    ),
    "stems": (
        "Corta el sufijo más largo y deja una raíz, que a menudo no es palabra: corrieron → corr. "
        "Un solo corte, raíz mínima de 3, tokens de menos de 5 no se tocan. No es Snowball. "
        "estuvo no coincide con ningún sufijo y se conserva: el irregular es trabajo del lematizador."
    ),
    "lemas": (
        "Devuelve la entrada de diccionario: estaban → estar. Orden: clítico (creerlo → creer), "
        "diccionario (regulares generados + irregulares escritos), reglas abiertas (gerundio, plural) "
        "y, si nada aplica, identidad. No es derivación: buenísimo no vuelve a bueno. "
        "esta sin tilde no se mapea a estar."
    ),
    "normalizado": (
        "Secuencia de lemas de contenido, en orden. Las stopwords se quitan aquí, no antes, "
        "para que la morfología se vea arriba. Se conserva la negación (no, sin, ni, nunca): "
        "borrarla rompe un dataset de sentimiento. Lo que se guarda es el lema, no el stem."
    ),
}


def procesar(texto: str, opciones: Opciones | None = None) -> Resultado:
    opciones = opciones or Opciones()

    limpio, log_ruido = remover_ruido(texto or "", opciones)
    tokens_crudos = tokenizar(limpio)
    tokens, log_var = normalizar_variantes(tokens_crudos, opciones.variantes)
    trazas_stem = [stem_token(t) for t in tokens]
    stems = [stem for stem, _ in trazas_stem]
    lemas, trazas_lema = lematizar(tokens)
    final, log_final = texto_normalizado(lemas, opciones.stopwords)

    filas_stem = [
        (f"{i:02d}", token, "→", stem, regla)
        for i, (token, (stem, regla)) in enumerate(zip(tokens, trazas_stem), 1)
    ]
    filas_lema = [
        (f"{i:02d}", token, "→", lema, regla)
        for i, (token, lema, regla) in enumerate(trazas_lema, 1)
    ]
    cortes = sorted({
        regla.split("; ")[-1]
        for _, regla in trazas_stem
        if regla.split("; ")[-1].startswith("-")
    })
    n_identidad = sum(1 for _, _, regla in trazas_lema if "identidad" in regla)
    n_abierta = sum(
        1 for _, _, regla in trazas_lema
        if regla.split("; ")[-1].startswith(("gerundio", "pretérito", "plural"))
    )
    n_clitico = sum(1 for _, _, regla in trazas_lema if regla.startswith("clítico"))
    n_dict = len(trazas_lema) - n_identidad - n_abierta
    n_cambios = 0
    if opciones.variantes:
        n_cambios = sum(token in RISAS_TOKEN or token in VARIANTES for token in tokens_crudos)
    retiradas = [lema for lema in lemas if lema in STOPWORDS] if opciones.stopwords else []

    pasos = (
        Paso(
            "ruido",
            "Ruido",
            EXPLICACION["ruido"],
            limpio or "—",
            "\n".join(log_ruido),
            f"{len(texto or '')} caracteres → {len(limpio)}",
        ),
        Paso(
            "tokens",
            "Tokens",
            EXPLICACION["tokens"],
            _numerar(tokens_crudos),
            "\n".join([
                f"patrón  {TOKEN_PATRON}",
                "se aplica sobre el texto ya limpio",
                "un findall: cada coincidencia es un token, en orden",
                "",
                f"{len(tokens_crudos)} tokens",
            ]),
            f"{len(tokens_crudos)} tokens",
        ),
        Paso(
            "variantes",
            "Variantes",
            EXPLICACION["variantes"],
            log_var[0] if log_var else "—",
            "\n".join(linea for linea in log_var[1:] if linea.strip()) or "—",
            f"{n_cambios} cambios" if opciones.variantes else "desactivado",
        ),
        Paso(
            "stems",
            "Stems",
            EXPLICACION["stems"],
            _columnas(filas_stem) if filas_stem else "—",
            "\n".join([
                "Un corte: el sufijo más largo. Raíz mínima de 3 letras.",
                "Tokens de menos de 5 no se tocan.",
                "No es Snowball. elección / elecciones no comparten stem.",
                "",
                "sufijos que cortaron: " + (", ".join(cortes) if cortes else "ninguno"),
            ]),
            (f"{len(cortes)} corte" if len(cortes) == 1 else f"{len(cortes)} cortes") if cortes else "sin cortes",
        ),
        Paso(
            "lemas",
            "Lemas",
            EXPLICACION["lemas"],
            _columnas(filas_lema) if filas_lema else "—",
            "\n".join([
                "1. clítico, si el resto parece verbo",
                "2. diccionario: paradigma regular generado, irregulares a mano, alternancias",
                "3. regla abierta: gerundio, pretérito claro, plural con singular conocido",
                "4. identidad: el token se queda",
                "",
                f"diccionario {n_dict} · regla abierta {n_abierta} · identidad {n_identidad} · clítico {n_clitico}",
            ]),
            f"{n_dict} diccionario · {n_abierta} reglas · {n_identidad} identidad",
        ),
        Paso(
            "normalizado",
            "Normalizado",
            EXPLICACION["normalizado"],
            final or "—",
            "\n".join(log_final),
            f"{len(final.split()) if final else 0} lemas de contenido · {len(retiradas)} stopwords fuera",
        ),
    )
    return Resultado(
        pasos=pasos,
        tokens=tuple(tokens),
        stems=tuple(stems),
        lemas=tuple(lemas),
        normalizado=final,
    )


MUESTRAS = (
    "RT @maria_dev: Noooo puedo creerlo!!! El servicio estuvo pésimo otra vez 😡😡 visiten https://t.co/ab12 #AtencionAlCliente q onda???",
    "jajajaja los usuarios estaban comentando q el partido estuvo buenísimo, los jugadores corrieron todo el tiempo #Futbol 🔥",
    "@soporte xq no funciona la app??? llevo 3 dias esperando y nadie responde... esto es un desastre!!! 😭 https://empresa.com/ayuda",
    "Los precios subieron muchísimo y la gente está comprando menos. No sé qué vamos a hacer #Economía",
    "RT @noticias: El presidente dijo que las elecciones fueron históricas. Los votantes salieron a celebrar a las calles. #Elecciones2026",
)


def demo() -> None:
    """Un chequeo runnable. Falla si el pipeline deja de hacer lo que la clase muestra."""
    r = procesar(MUESTRAS[0])
    assert "http" not in r.pasos[0].cuerpo
    assert "@" not in r.pasos[0].cuerpo
    assert "😡" not in r.pasos[0].cuerpo
    assert "poder" in r.lemas
    assert "creer" in r.lemas
    assert "estar" in r.lemas
    assert "visitar" in r.lemas
    assert "atención" in r.lemas
    assert r.normalizado.split()[0] == "no"
    assert "el" not in r.normalizado.split()
    i = r.tokens.index("creerlo")
    assert r.lemas[i] == "creer"
    j = r.tokens.index("estuvo")
    assert r.stems[j] == "estuvo" and r.lemas[j] == "estar"
    k = r.tokens.index("visiten")
    assert r.stems[k] == "visiten" and r.lemas[k] == "visitar"

    r2 = procesar(MUESTRAS[1])
    i = r2.tokens.index("corrieron")
    assert r2.stems[i] == "corr" and r2.lemas[i] == "correr"
    assert r2.lemas[r2.tokens.index("partido")] == "partido"
    assert r2.stems[r2.tokens.index("partido")] == "part"
    assert r2.lemas[r2.tokens.index("estaban")] == "estar"
    assert r2.stems[r2.tokens.index("estaban")] == "est"
    assert "usuario" in r2.lemas and "comentar" in r2.lemas
    assert "jajaja" not in r2.tokens

    r3 = procesar(MUESTRAS[2])
    assert "porque" in r3.tokens
    assert "funcionar" in r3.lemas
    assert "día" in r3.lemas
    assert "http" not in r3.normalizado
    assert "no" in r3.normalizado.split()

    r4 = procesar(MUESTRAS[4])
    assert "elección" in r4.lemas
    assert "decir" in r4.lemas
    assert "salir" in r4.lemas
    fueron = r4.pasos[4].cuerpo
    assert "ambiguo" in fueron

    extra = procesar("están bailando en las elecciones")
    assert extra.stems[extra.tokens.index("bailando")] == "bail"
    assert extra.lemas[extra.tokens.index("bailando")] == "bailar"
    assert extra.lemas[extra.tokens.index("elecciones")] == "elección"
    assert extra.normalizado == "bailar elección"

    assert lema_token("comprarlo") == ("comprar", "clítico -lo; paradigma regular")
    assert lema_token("estable")[0] == "estable"
    assert procesar("   ").normalizado == ""
    assert procesar("hola", Opciones(variantes=False)).tokens == ("hola",)
    print("demo ok")


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    demo()
    for n, muestra in enumerate(MUESTRAS, 1):
        print(f"{n}  {procesar(muestra).normalizado}")
