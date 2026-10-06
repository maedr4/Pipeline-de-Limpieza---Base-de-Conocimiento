# Limpieza de texto

Pipeline académico para publicaciones de redes. No hay que instalar nada.

## Abrir

Doble clic en `ejecutar.bat`, o:

```
py -3 app.py
```

Hace falta Python 3 de python.org (trae tkinter). No uses el alias de la Microsoft Store: ese `python` no es Python.

La lógica está en `pipeline.py`. La ventana solo la muestra. `py -3 pipeline.py` corre el mismo pipeline en consola y un chequeo.

## Recorrido

ruido → tokens → variantes → stems | lemas → normalizado

Stems y lemas salen en paralelo, sobre los mismos tokens. No se lematiza un stem. El texto que se guarda es el de lemas.

## Qué mostrar en clase

- `creerlo` separa el clítico y cae en `creer`. `estuvo` el stemmer no lo corta; el lema sí (`estar`).
- `corrieron` → stem `corr`, lema `correr`.
- `partido` → stem `part`, lema `partido` (no es `partir`).
- `fueron` queda marcado como ambiguo ser/ir.
- `no` se conserva. Las stopwords se quitan al final, no antes.

## Qué no está

Snowball completo, etiquetado gramatical, derivación (`buenísimo` no vuelve a `bueno`), corrector ortográfico. El léxico es cerrado: lo que no tiene regla se queda, y el registro dice `identidad`.

`vendor/` trae customtkinter, darkdetect y packaging para no usar pip. Licencias en `vendor/licencias/`.
