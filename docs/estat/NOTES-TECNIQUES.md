# Notes tècniques

Coses descobertes que no es dedueixen del codi. Són del moment en què es van apuntar (novembre de 2026): comproveu-les abans de fiar-vos-en.

## Components dinàmics dins un .skp

- Els atributs del component **de dalt** són al diccionari de la **definició** (centenars de claus), no al de la instància. Cal llegir els diccionaris de definició (openSKP #530, ja acceptada). Mentre l'openSKP que porta IngeTrazo no els tingui, l'extensió en porta el seu a `skp_dc_import/_vendor/openskp`.
- Un **fitxer de component** (de biblioteca) té els atributs de dalt al diccionari del **model**: el constructor embolcalla l'arrel en un component quan el model en té. El lector de fitxers antics en perdia part (corregit a la 0.6.1; el PR a openSKP d'aquella correcció no s'ha fet).
- Regles del motor original, contrastades redibuixant-hi: només un nombre positiu és cert; les claus `_inst__*` de la definició són plantilles; els noms només es resolen en la mateixa peça, els pares, els germans i els fills; `_lengthunits` és de cada peça, **no** s'hereta (sense, les fórmules es llegeixen en polzades); una peça amb subpeces torna a escala 1 i n'estira el contingut; les còpies no s'estiren i només es refan de l'original quan són noves.
- `ScaleTool` = màscara de nanses **amagades** (1 X, 2 Y, 4 Z, 8 XY, 16 XZ, 32 YZ, 64 uniforme).
- Diferència coneguda: la base d'un replà d'escala no s'estira a l'original quan canvia l'amplada.
- Per exportar perquè hi funcionin: còpies anomenades «<nom> copy NNN», els `_len*_nominal` al diccionari de la **definició**, i cal escriure també les peces ocultes o buides.
- Les eines de comparació són a `tests_su/`. Els bolcats i els models de prova de l'usuari **no es publiquen**.
- Les finestres reals de l'usuari van fallar on les sintètiques passaven (una peça 5 mm per davant de la cara de la paret, 0.3.9): proveu les funcions de finestres amb components reals quan sigui possible.

## Paranys que ja han costat caigudes

- No esborreu un `QLineEdit` mentre encara atén la tecla de retorn (`takeRow` + `deleteLater`, i apliqueu en diferit). Només petava amb l'IngeTrazo empaquetat, no des del codi font.
- Un .skp pot donar capes que no són text: filtreu-les, o el tauler de capes d'IngeTrazo peta mentre es pinta.
- `ExtensionApp.add_panel(name=…)` torna el tauler que **ja existeix**: canvieu-ne el contingut (`dock.setWidget`), no l'esborreu.
- Proves dins el programa: `QSettings.setDefaultFormat` i el nom d'organització afecten tot el procés; restaureu-los. Redirigir `APPDATA` **no** aïlla `QSettings` a Windows.

## Objectes de biblioteca i llums d'altres programes

- Les llums són components amb un diccionari de **definició** (`LightData`, XML; les mides, en polzades). La conversió a llums de Render Studio **ja és feta**.
- Els objectes de biblioteca (plantes, mobles) només porten un embolcall lleuger i un identificador: la geometria real no és al fitxer. Entren com a *stand-in*.
- El sol i les vistes són al diccionari del model, en JSON. Les vistes ja s'importen. **Pla acordat i no fet** per al sol: mode 0 = data, hora, fus, latitud i longitud → `scene.shadows`; mode 1 = vector, amb la convenció per verificar contra les ombres originals i tenint en compte el nord.

## Idea no començada: el *stand-in* al nucli

Ara és a l'extensió (`asset_manager/stand_in.py`): `ext["render_studio"]["hide_in_render"]`, la pintura anterior guardada i `group.material` translúcid.

1. Que `ReplaceComponentCommand.do()` restauri la pintura d'un *stand-in* en canviar-ne la definició (unes 5 línies).
2. Més net: un camp del nucli a `Group`, desat al `.igz`: la vista el dibuixa translúcid, substituir-lo el neteja i el **render intern d'IngeTrazo** també l'omet.

Mentrestant, «Substitueix-los tots…» de la Library desmarca abans de substituir.

## Models grans i congelacions

- Amb uns 600 000 cares hi ha uns 12 milions d'objectes de Python: una recollida de memòria completa (`gc.collect(2)`) tarda uns 8,5 s. `gc.freeze()` després de carregar el document la deixa en 1 ms. És candidat a PR al nucli; `tools/gc_tune/gc_tune.py` és l'extensió provisional.
- Altres causes trobades: triangular tota la selecció en Python a cada canvi (Dispersa), miniatures que aplanaven les còpies (corregit a la Library 0.3.1) i el desat automàtic (uns 12 s amb aquell model).
- A Render Studio, per sobre de 150 000 cares desplegades s'exporta amb jerarquia instanciada (si no, la vista prèvia no acaba mai).
- **No feu mai proves pesades dins la sessió oberta de l'usuari** sense demanar-ho: dues proves van congelar el programa uns minuts i van deixar 14 GB ocupats.
