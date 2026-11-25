# Treballar des del núvol

## Què hi ha i què no

| Al núvol | Només a l'ordinador local |
|---|---|
| Els dos repositoris, amb la guia d'estil, aquestes notes i les eines | IngeTrazo obert (captures del programa real, ratolí) |
| El codi d'IngeTrazo (repositori públic `ingelibre/ingetrazo`) | Blender amb targeta gràfica i les extensions instal·lades |
| `gh` per a versions i *pull requests* (si la sessió hi té accés) | Models reals de prova i dibuixos de l'usuari (no es publiquen) |

El que només es pot comprovar a l'ordinador (dins el programa, instal·lació) s'ha de dir clarament com a **no comprovat**.

## Preparació

```bash
git clone https://github.com/ingelibre/ingetrazo ../ingetrazo
git -C ../ingetrazo checkout v0.6.3.2        # la versió amb què s'ha provat
pip install PySide6 numpy pillow             # Python 3.12
```

En un Linux sense pantalla, Qt pot demanar paquets del sistema (`libegl1 libgl1 libxkbcommon0 libfontconfig1 fonts-dejavu-core`). **No s'ha comprovat en Linux:** tot s'ha provat a Windows.

## Proves

```bash
bash tools/run_offline_tests.sh ../ingetrazo
```

- **Render Studio:** 44 grups sense Blender; el 25-11-2026 passaven tots amb IngeTrazo 0.6.3.2. Amb 0.6.2.1 en fallen 2 (`.igmat` i caixa de secció necessiten 0.6.3).
- **Library:** 4 passen i 1 té la fallada coneguda (vegeu `PENDENT.md` al repositori de Render Studio).
- Les proves que acaben en `_blender` o `_job` necessiten Blender (5.3 a l'ordinador local). Alguna es pot fer amb el mòdul `bpy` (`pip install bpy`).
- Fallades ja conegudes a les proves amb Blender: «Watercolour: the picture is painted» (`test_output_job`) i dues a `test_lights_job`. `test_live_blender` falla de vegades.
- Fora de pantalla, les lletres són un 20 % més amples i Qt no propaga la roda simulada ni hi ha focus (vegeu els paranys de la guia).

## Ensenyar el que es fa

L'usuari sovint no és davant l'ordinador i **vol captures**. Sense el programa real es poden fer del tauler, fora de pantalla (només al repositori de Render Studio):

```bash
QT_QPA_PLATFORM=offscreen python tools/panel_shots.py ../ingetrazo . sortida.png tools/shots_example.py
```

Digueu sempre si una captura és de dins o de fora del programa.

**Escena de demostració** que li agrada: la matriu de 8 × 8 prismes amb graduació de colors (`docs/demo/prismes.igz`, o `tools/make_prisms_demo.py`, al repositori de Render Studio). És la de la captura del catàleg: pestanya Principal i vista prèvia, girada de manera que el groc quedi a davant a l'esquerra.

## Publicar una versió

1. **Traduccions:** els textos nous, als 20 idiomes de `locales/` (l'anglès és la clau). Comproveu que no en falti cap i que es conservin les variables (`{path}`, `{n}`…). L'usuari va triar traduir abans de publicar.
2. Apugeu `__version__` i poseu al dia el `README`.
3. Passeu les proves. Després:

   ```bash
   git archive --format=zip -9 -o releases/<paquet>-<versió>.zip HEAD <paquet>
   ```

   Proveu també el que surt del `.zip`.
4. Commit del `.zip`, etiqueta (`vX.Y.Z` a Render Studio; `<paquet>-vX.Y.Z` a l'altre), `main` i `gh release create`.
5. Catàleg: un PR per extensió des de `main` de `ingelibre/ingetrazo-extensions`, a la branca d'un *fork*, canviant `version`, `download` i `sha256` de `extensions/<id>.toml`. Comproveu-ho amb `python tools/catalog.py check <id>`.
6. El camp `ingetrazo` de la fitxa és la versió **mínima** per instal·lar (ara 0.6.2.1): no l'apugeu sense motiu.
7. **Textos del catàleg i de la interfície sense marques comercials** d'altres programes o fabricants (ho va demanar un mantenidor). El format `.skp` i els identificadors sí que es poden anomenar.
8. La captura del catàleg: `screenshots/<id>.webp`, menys de 600 KB.

Un PR només es publica sol si la revisió no troba res «for the reviewer to read»; els nostres sempre en tenen, així que els aprova una persona.
