# Translation workflow (lupdate / lrelease)

This document explains how to update and build translations for the `GEO-search-plugin` project.

## Local (Linux / macOS)

1. Ensure `lupdate`/`lrelease` are installed. On Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y qttools5-dev-tools qttools5-dev
```

2. Run the provided script:

```bash
bash scripts/update_translations.sh
```

This will run `lupdate` to update `.ts` files under `geo_search/i18n` and then run `lrelease` to create `.qm` files.

## Local (Windows)

1. Install Qt (Qt Linguist tools) and ensure `lupdate.exe` and `lrelease.exe` are on `PATH`.
2. Run PowerShell script:

```powershell
.\scripts\update_translations.ps1
```

### Windows: common lrelease locations

On Windows you may not have `lrelease.exe` on `PATH`. Common installation locations:

- OSGeo4W (QGIS installer / OSGeo): `C:\\OSGeo4W64\\apps\\Qt5\\bin\\lrelease.exe`
- QGIS Standalone installer (example): `C:\\Program Files\\QGIS 3.28\\bin\\lrelease.exe`

If you install Qt via the official Qt installer, `lrelease.exe` will be under the Qt installation `bin` directory for the Qt version you chose. If the tools are not on `PATH`, either add the containing folder to `PATH` or invoke the full path when running the PowerShell script.

## CI (GitHub Actions)

A workflow `.github/workflows/translations.yml` has been added. It runs on `ubuntu-latest`, installs `qttools5-dev-tools`, executes `lupdate` and `lrelease`, and fails if `.ts` files changed (to ensure translations are kept up to date). The compiled `.qm` files are uploaded as artifacts.

If the CI fails with "Translations or .ts files changed", run the local update script, review & commit changes, then push.

## Notes
- We added many `tr()` wrappers in Python code so new strings are extractable.
- Ideal workflow:
  1. Add/modify UI / strings in code
  2. Run `scripts/update_translations.sh` (or PS equivalent)
  3. Open `.ts` files with Qt Linguist and refine translations
  4. Commit `.ts` (and optionally generated `.qm`) and push
