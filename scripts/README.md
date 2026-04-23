# Scripts

This directory contains helper scripts that are not required for normal API startup.

Run scripts from the project root:

```bash
python scripts/debug/debug_crawler.py taobao "iPhone 15"
python scripts/login/login.py taobao qr
python scripts/tests/test_crawler.py
```

If a script cannot import `app`, set `PYTHONPATH` to the project root before running it:

```powershell
$env:PYTHONPATH = (Get-Location)
```

## Folders

- `debug/`: crawler experiments, selector debugging, and one-off diagnostics.
- `login/`: browser login and cookie helper scripts.
- `tests/`: manual test scripts used during crawler development.
