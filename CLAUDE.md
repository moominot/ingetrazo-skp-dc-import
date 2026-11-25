# Extensions d'IngeTrazo: Library, components dinàmics i .skp

Tres extensions que s'instal·len per separat: `asset_manager/` (**Render Studio Library**), `dc_tools/` (components dinàmics) i `skp_dc_import/` (importar i exportar .skp). Render Studio és a `moominot/ingetrazo-render-studio`.

## Com treballar amb l'usuari

- Escriu en **català**; respon sempre en català.
- Sovint no és davant l'ordinador: **ensenya captures** del que fas i digues si són de dins o de fora del programa.
- Digues clarament què **no** has comprovat.
- **No treguis botons ni funcions sense consultar-ho.**
- Commit, push, versions i *pull requests* cap a altres repositoris: només quan ho demani (en una sessió al núvol, la feina va a la branca de la sessió).
- El repositori és **públic**: cap dada personal, nom de client, camí de l'ordinador ni model real de l'usuari.

## Abans de tocar res

1. Llegeix la **guia d'estil**: [docs/estil/GUIA.md](docs/estil/GUIA.md) (obligatòria per a qualsevol canvi d'interfície; no autoritza a redissenyar res que no s'hagi demanat).
2. Llegeix [docs/estat/PENDENT.md](docs/estat/PENDENT.md) i [docs/dev/NUVOL.md](docs/dev/NUVOL.md) (proves, captures i publicació).

## Proves

```bash
bash tools/run_offline_tests.sh <carpeta amb el codi d'IngeTrazo>
```

## Notes

- [docs/estat/NOTES-TECNIQUES.md](docs/estat/NOTES-TECNIQUES.md): el que se sap dels .skp, els components dinàmics, les caigudes i els models grans. Llegeix-ho abans de tocar `dc_tools` o `skp_dc_import`.
- Moltes proves de `tests_su/` comparen amb bolcats del programa original que **no** són al repositori.
