# AIAT Assistant Implementation Bundle

## ChatGPT
1. Create Project `AIAT Research-to-LEAN Governor`.
2. Paste `01_CHATGPT_INSTALLATION/CANONICAL_PROJECT_INSTRUCTIONS.txt`.
3. Upload files listed in `CHATGPT_UPLOAD_MANIFEST.json`.
4. Run acceptance tests.
5. Invoke with `AIAT mission: ...`.

## Python
```bash
cd 03_PYTHON_RUNTIME
pip install -e .
pytest -q
aiat examples/momentum_mission.json
```

## Status
The runtime is an implementation scaffold. Actual validated NB00-NB10 quantitative functions must be wired into registered handlers before empirical completion.

LIVE_AUTHORITY = DENIED
