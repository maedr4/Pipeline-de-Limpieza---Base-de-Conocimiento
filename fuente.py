"""De dónde sale el texto, antes del pipeline.

Un GET. Sirve una página pública, un RSS/Atom, o un listado .json de Reddit.
No abre sesión y no ejecuta JavaScript: X, Instagram y Facebook arman el muro
en el navegador y acá no devuelven publicaciones. Eso no se evade.

ponytail: urllib + html.parser. Un navegador headless cuando haga falta entrar
a un sitio que no entrega HTML.
"""

from __future__ import annotations

import html
import json
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

EJEMPLO = "https://www.meneame.net/rss2.php"
_MAX = 1_500_000
_TOPE = 20
_UA = "LimpiezaTexto/1.0 (pipeline academico)"


class _Extractor(HTMLParser):
    """Texto visible. script/style no entran. Cada bloque largo es una línea."""

    _SALTO = {"p", "br", "li", "h1", "h2", "h3", "h4", "tr", "article", "blockquote"}
    _MUDO = {"script", "style", "noscript", "svg", "head"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lineas: list[str] = []
        self._mudo = 0
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self._MUDO:
            self._mudo += 1
        elif tag in self._SALTO:
            self._cerrar()

    def handle_endtag(self, tag):
        if tag in self._MUDO and self._mudo:
            self._mudo -= 1
        elif tag in self._SALTO:
            self._cerrar()

    def handle_data(self, data):
        if not self._mudo:
            self._buf.append(data)

    def cerrar(self):
        self._cerrar()

    def _cerrar(self):
        linea = " ".join("".join(self._buf).split())
        self._buf = []
        if len(linea) >= 25 and " " in linea:
            self.lineas.append(linea)


def extraer_html(documento: str) -> list[str]:
    parser = _Extractor()
    parser.feed(documento)
    parser.cerrar()
    vistos: set[str] = set()
    salida = []
    for linea in parser.lineas:
        if linea in vistos:
            continue
        vistos.add(linea)
        salida.append(linea)
        if len(salida) >= _TOPE:
            break
    return salida


def _plano(fragmento: str) -> str:
    parser = _Extractor()
    parser.feed(html.unescape(fragmento or ""))
    parser.cerrar()
    return " ".join(parser.lineas) if parser.lineas else " ".join(fragmento.split())


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def extraer_feed(xml_texto: str) -> list[str]:
    root = ET.fromstring(xml_texto)
    lineas = []
    for nodo in root.iter():
        if _local(nodo.tag) not in {"item", "entry"}:
            continue
        titulo = cuerpo = ""
        for hijo in list(nodo):
            nombre = _local(hijo.tag)
            if nombre == "title":
                titulo = " ".join((hijo.text or "").split())
            elif nombre in {"description", "summary", "content"}:
                cuerpo = _plano("".join(hijo.itertext()))
        if cuerpo.startswith(titulo):
            texto = cuerpo
        elif titulo and cuerpo:
            texto = f"{titulo}. {cuerpo}"
        else:
            texto = titulo or cuerpo
        texto = " ".join(texto.split())
        if len(texto) >= 20:
            lineas.append(texto)
        if len(lineas) >= _TOPE:
            break
    return lineas


def extraer_reddit(data) -> list[str]:
    """Listado público: título + texto del post, o el cuerpo del comentario."""
    nodos = data if isinstance(data, list) else [data]
    lineas = []
    for nodo in nodos:
        if not isinstance(nodo, dict):
            continue
        children = ((nodo.get("data") or {}).get("children")) or []
        for child in children:
            dato = (child or {}).get("data") or {}
            if dato.get("stickied"):
                continue
            titulo = " ".join((dato.get("title") or "").split())
            cuerpo = (dato.get("selftext") or dato.get("body") or "").strip()
            if cuerpo in {"[deleted]", "[removed]"}:
                cuerpo = ""
            else:
                cuerpo = " ".join(cuerpo.split())
            if titulo and cuerpo:
                texto = f"{titulo}. {cuerpo}"
            else:
                texto = titulo or cuerpo
            if len(texto) >= 20:
                lineas.append(texto)
            if len(lineas) >= _TOPE:
                return lineas
    return lineas


def _decodificar(raw: bytes, charset: str | None) -> str:
    for nombre in (charset, "utf-8", "latin-1"):
        if not nombre:
            continue
        try:
            return raw.decode(nombre)
        except LookupError:
            continue
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _clasificar(texto: str, ctype: str) -> tuple[list[str], str]:
    recorte = texto.lstrip("\ufeff \t\r\n")
    tipo = ctype.lower()
    if "json" in tipo or recorte[:1] in "{[":
        try:
            data = json.loads(recorte)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict) and data.get("message") and not (data.get("data") or {}).get("children"):
            raise RuntimeError(f"el sitio respondió: {data['message']}")
        if data is not None:
            lineas = extraer_reddit(data)
            if lineas:
                return lineas, "reddit"
    if "xml" in tipo or "rss" in tipo or recorte.lower().startswith(("<rss", "<feed", "<?xml")):
        try:
            return extraer_feed(texto), "rss"
        except ET.ParseError:
            pass
    return extraer_html(texto), "html"


def traer(url: str) -> tuple[str, str]:
    """Devuelve (texto, nota). Una publicación por línea. La nota dice la fuente real."""
    url = (url or "").strip()
    if not url:
        raise ValueError("falta la dirección")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    partes = urllib.parse.urlparse(url)
    if partes.scheme not in {"http", "https"} or not partes.netloc:
        raise ValueError("tiene que ser una dirección http o https")

    pedido = urllib.request.Request(
        url,
        headers={"User-Agent": _UA, "Accept": "*/*", "Accept-Language": "es,en;q=0.8"},
    )
    try:
        with urllib.request.urlopen(pedido, timeout=12) as resp:
            raw = resp.read(_MAX + 1)[:_MAX]
            charset = resp.headers.get_content_charset()
            final = resp.geturl()
            ctype = resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403, 429}:
            raise RuntimeError(
                f"el sitio respondió {exc.code} y no entregó el texto. "
                "Sin sesión no hay muro. Probá una página pública, un RSS, "
                f"o {EJEMPLO}"
            ) from exc
        raise RuntimeError(f"el sitio respondió {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"no se pudo abrir el sitio: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError("el sitio no respondió a tiempo") from exc

    lineas, clase = _clasificar(_decodificar(raw, charset), ctype)
    if not lineas:
        raise RuntimeError(
            "no llegó texto visible. Si la página se arma en el navegador "
            f"(X, Instagram, Facebook), un GET no alcanza. Probá {EJEMPLO}"
        )
    return "\n".join(lineas), f"{clase} · {len(lineas)} textos · {final}"


def demo() -> None:
    html_doc = (
        "<html><head><style>.x{color:red}</style></head><body>"
        "<nav>Home</nav>"
        "<p>Los usuarios estaban comentando que el servicio estuvo pésimo otra vez.</p>"
        "<script>var secreto = 1</script></body></html>"
    )
    lineas = extraer_html(html_doc)
    assert len(lineas) == 1 and "pésimo" in lineas[0] and "secreto" not in lineas[0]

    posts = extraer_reddit(
        {
            "data": {
                "children": [
                    {"data": {"title": "El servicio estuvo pésimo", "selftext": "Nadie responde.", "stickied": False}},
                    {"data": {"title": "anuncio", "stickied": True, "selftext": "no entra"}},
                ]
            }
        }
    )
    assert posts == ["El servicio estuvo pésimo. Nadie responde."]
    print("fuente ok")


if __name__ == "__main__":
    demo()
