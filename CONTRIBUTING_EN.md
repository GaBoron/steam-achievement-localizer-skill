# Contributing

This repository owns only the Codex skill and localization-project tooling. Submit translation data to [Steam Achievement Translation Library](https://github.com/GaBoron/steam-achievement-translation-library), and submit end-user install, backup, or restore behavior to [SATLI](https://github.com/GaBoron/SATLI).

Preserve these module boundaries:

- `scripts/steam_bkv_tool.py` composes commands only.
- `scripts/steam_localizer/bkv.py` owns Binary KeyValues and schema structure.
- `translations.py` owns translation sheets and research manifests.
- `library.py` owns read-only catalog and reference verification.
- `public_data.py` owns public achievement acquisition and provenance snapshots; `translation_json.py` owns the standalone JSON text contract.
- `project.py` owns the organized project layout and final artifacts.
- `steam.py` only locates local schemas.

Run before submitting:

```powershell
python -m compileall -q scripts tests
python -m unittest discover -s tests -v
python C:\Users\<user>\.codex\skills\.system\skill-creator\scripts\quick_validate.py .
```

Add focused unit tests for new behavior, keep source schemas read-only, reject invalid translations explicitly, and keep process files and final artifacts inside the project directory.
