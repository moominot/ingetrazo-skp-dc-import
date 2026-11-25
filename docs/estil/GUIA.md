# Guia d'estil per a les extensions d'IngeTrazo

Estil visual i d'ús que s'ha anat decidint amb Render Studio (novembre de 2026) i que ha agradat. Serveix de referència per millorar la resta d'extensions. El codi de referència viu és la carpeta `render_studio/` del repositori `moominot/ingetrazo-render-studio`; a `codi/` n'hi ha una còpia simplificada per reutilitzar, i a `imatges/` com es veu (algunes imatges són d'abans dels darrers retocs: si no coincideixen, mana el codi).

La còpia **mestra** d'aquesta guia és al repositori de Render Studio (`docs/estil/`); la del repositori `ingetrazo-skp-dc-import` n'és una còpia. Si canvieu un criteri, actualitzeu-les totes dues.

## 1. Principis

1. **Senzillesa.** Poques opcions a la vista. Abans d'afegir-ne una, mira si es pot treure o fusionar.
2. **Cap desplegable «Avançat».** El que no és bàsic va al **mode expert**.
3. **Mateix aspecte a tot arreu:** targetes, botons plans i icones vectorials a l'estil d'IngeTrazo.
4. **Ha de caber al tauler estret (240 px)**, amb tema clar i fosc.

## 2. Estructura del tauler

De dalt a baix:

- **Capçalera d'IngeTrazo** (la fila amb el nom del panell): botó «Mode expert» (icona d'eines i text) i botó d'ajuda. Vegeu `codi/header_tools.py`.
- **Pestanyes**, amb 8 px de marge sobre el primer element.
- **Targetes** dins cada pestanya.
- **Peu**, en graella de dos per dos:
  - fila secundària, de 28 px: accions que obren finestres (Materials, Llums);
  - fila principal, de 42 px i icones de 22 px: les dues accions de resultat (Vista prèvia, Captura).
- **Línia de missatges** a sota, sola. No hi posis controls.

Imatge: `imatges/capcalera-i-peu.png`.

## 3. Targetes (`Card`, a `codi/ui_kit.py`)

- Capçalera amb **color diferencial**: el color d'accent, molt suau (alfa 46) sobre el fons de la targeta.
- **Icona** de 18 px, **nom en negreta** i fletxa de plegat a la dreta.
- Un clic a la capçalera plega i desplega; es recorda.
- Plegada, mesura **exactament la capçalera**.
- Substitueix tots els `QGroupBox`.
- Si el grup té més ajustaments a la pestanya Expert, un **«+» a la capçalera** l'obre directament en aquell grup. Amb el mode expert apagat, la pestanya Expert només hi és mentre es mira i s'amaga en sortir-ne.
- Si totes les files d'una targeta s'amaguen, s'amaga la targeta. Les notes grises i els blocs buits no compten.

- Dins d'una targeta, no repetiu el seu nom a l'etiqueta: la llista principal va sense etiqueta.
- Al tauler estret, dos camps numèrics de costat no hi caben: poseu-los l'un sota l'altre.
- Un botó al costat d'un camp de text, només amb icona i amplada fixa. Les proves han de mirar que cada botó es veu, no només que existeix.

Imatges: `imatges/targetes-clar.png`, `imatges/targetes-fosc.png`, `imatges/seccio-sortida.png`.

## 4. Botons

- **Plans:** sense marc, amb fons gris suau; més fort en passar el ratolí; tenyit amb l'accent quan estan activats (`flat_style()`).
- **Tots amb icona.**
- **Icona i text centrats** (`CentredButton`). El botó amb menú (`split_button`) centra respecte del botó sencer i no trepitja la fletxa.
- Opcions de costat (tres a cinc, com els tipus de llum o la qualitat): **icona damunt del text**, lletra de 10 px i la mateixa amplada.
- Un botó amb text llarg o variable (coordenades, «Desa com a predefinit…») fa servir `QSizePolicy.Ignored`, perquè no eixampli el tauler.
- El botó pot dir la dada: el de localització mostra «16,4090° S, 71,5370° O», i «Localització…» quan no n'hi ha.
- Apliqueu l'estil pla **a les pàgines i als botons**, no a tot el tauler: sobre la barra de pestanyes esborra les fletxes.

## 5. Mode expert i disposició

- Pestanya **Expert** amb **tot** el que es pot modificar, agrupat en targetes plegables («Pestanya ▸ Grup») i amb **cercador** (obre els grups on troba coses).
- Cada fila: nom, punt taronja i botó de restablir si no té el valor per defecte, i al **marge dret** l'**ull**, pla.
- L'ull decideix si l'ajustament es veu a la seva pestanya. **Tots els elements s'han de poder amagar**, també els que són dades del programa.
- La **vista bàsica** per defecte és curta. Les disposicions es poden desar amb nom. Si canvia la vista bàsica, substitueix la per defecte que l'usuari tenia desada, no les que tenen nom.
- La disposició només decideix què es veu; no canvia cap valor.
- Descriviu cada ajustament **una sola vegada** en un registre (`params.py`): d'allà surten la pestanya Expert, l'ull, el restabliment i el desat. Al dibuix només es guarda el que no té el valor per defecte.

Imatge: `imatges/expert-ull.png`.

## 6. Textos

- Etiquetes curtes: «Alçada», no «Alçada dels cims» (el grup ja diu de què).
- Les explicacions van al **quadre d'ajuda** (tooltip), no en línies grises sota els controls. Les notes visibles, només per avisar d'alguna cosa.
- Vocabulari: «**vista prèvia**» (no «previsualització»), «**Captura**» (no «Render») per al botó; en castellà «vista previa» i «captura».
- Quan es canvia una paraula, es canvia a tot arreu: botons, quadres d'ajuda, missatges i ajuda.

## 7. Icones (`codi/icons.py`)

- Vectorials, dibuixades amb `QPainter` en una caixa de 48; sense emoji ni imatges.
- Tinta del tema (`views.theme.icon_ink`) i un detall en el color d'accent.
- Desactivada: **tota** la icona al 35 % (si només s'apaga la tinta, sembla activa).
- Una icona per **grup** i una per botó. Les fines i amb la punta petita no es llegeixen: comproveu-les a la mida real.

## 8. Barra d'eines

- Primer, obrir el panell, i un separador.
- Després les accions de vista i els interruptors de sincronització, en aquest ordre: vista prèvia, seguir la càmera, sincronitzar canvis, actualitzar.
- Un altre separador i les finestres: materials, llums, biblioteca.
- Els botons **no apareixen ni desapareixen**: el que no es pot fer es veu desactivat.
- Una barra flotant s'ha d'ajustar als seus botons (Qt els talla sense fletxa).
- Els interruptors viuen a la barra. L'excepció és la finestra de vista prèvia, que els repeteix amb les **mateixes ordres** (`QAction`), perquè sempre diguin el mateix.

Imatge: `imatges/barra-eines.png`.

## Finestres amb una imatge (vista prèvia)

- De dalt a baix: la **barra** de controls (una sola fila), la **imatge**, una línia grisa amb les dades (què es veu a l'esquerra, què farà la captura a la dreta) i, **a baix de tot**, la línia de missatges.
- Opcions de costat dins la barra (la qualitat): els mateixos botons i icones del tauler, amb la **icona al costat** del text. En una finestra estreta, els textos prescindibles s'amaguen i queda la icona amb el quadre d'ajuda.
- Fila de controls: una **barra** (franja grisa suau i arrodonida) amb **tots els controls de la mateixa alçada** (32 px, icones de 20 px), sense fons propi fins que s'hi passa el ratolí, i separadors fins entre grups. Només l'acció principal de cada estat va **tenyida amb l'accent**. A l'esquerra, «Tauler» (torna al tauler; si la finestra el tapa, s'aparta) i «?» (la manera de fer servir el ratolí va al seu quadre d'ajuda). Codi: `BAR_STYLE` a `render_studio/preview.py`.
- El **botó dret** sobre la imatge ofereix les mateixes accions de desar i copiar.
- Navegació com a la vista 3D; **Ctrl** reserva el zoom i el desplaçament de la pròpia imatge.

Imatge: `imatges/finestra-vista-previa.png`.

## 9. Comportament

- **Roda del ratolí:** només canvia un camp triat (amb focus); si no, desplaça la pàgina. Copieu `codi/wheel_guard.py` i crideu `wheel_guard.watch(self)` al final del constructor de cada finestra i diàleg. IngeTrazo ho portarà per a tot el programa (incidència #1483); les dues coses són compatibles.
- **Transparència:** el tauler d'escacs és de la finestra (quadrats de mida i lloc fixos), no de cada imatge.
- **Accions principals** també a mà al tauler, encara que siguin a la barra d'eines. No traieu botons sense consultar-ho.

## 10. Paranys coneguts (Qt i PySide)

| Parany | Solució |
|---|---|
| `option.icon` és una referència: si el buides, perds la icona | copieu-lo: `QIcon(option.icon)` |
| Un `QGroupBox` reserva amplada per a tot el títol | redefiniu `minimumSizeHint` |
| Un nom llarg en un desplegable eixampla el tauler | `AdjustToMinimumContentsLengthWithIcon` |
| Inserir un fitxer abans de «Tria un fitxer…» torna a obrir el diàleg | bloquegeu els senyals **abans** d'inserir |
| La vora suau de l'ombra no es veu amb EEVEE | `use_shadow_jitter` |
| La capçalera del panell es refà en reordenar | traieu els botons quan rebi `DeferredDelete` |
| Fora de pantalla les lletres són un 20 % més amples | mesureu amplades amb les lletres reals (`WA_DontShowOnScreen`) |
| Fora de pantalla Qt no propaga la roda simulada ni hi ha focus | comproveu que l'esdeveniment queda sense acceptar |
| Que un botó tingui icona no vol dir que es dibuixi | comproveu-ho als píxels |
| La traducció de l'arbre de widgets torna a traduir un text ja traduït («None» → «Cap» → «Tapa») | no feu servir paraules curtes la traducció de les quals sigui una altra clau anglesa |

## 11. Manera de treballar

- Ensenyeu **captures** de cada canvi (clar i, si toca, fosc; amplada normal i mínima) i digueu si són de dins o de fora del programa.
- Proves automàtiques per a cada canvi. Instal·leu només amb el vistiplau, amb còpia de seguretat, i passeu les proves sobre la còpia instal·lada.
- No tanqueu IngeTrazo si hi ha feina sense desar.

## 12. Convencions de codi i textos

- Cada extensió és una carpeta amb `__init__.py` (`__version__`, `setup(app)`), `i18n.py` i `locales/<idioma>.json`. La clau de cada text és l'**anglès**.
- Capçalera `# SPDX-License-Identifier: GPL-3.0-or-later`.
- Cada canvi del dibuix és **un sol pas** de desfer.
- Si es fa servir una part interna d'IngeTrazo, que hi hagi sortida quan canviï (com fa `header_tools.py`).
- Sense marques comercials d'altres programes als textos que es veuen ni al catàleg.
- Cap dada personal ni camí de l'ordinador al repositori: és **públic**.
