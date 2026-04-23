# Price Agent

Price Agent is a pure crawler-based price comparison system. It uses FastAPI as the backend service and Playwright crawlers to collect public product data from shopping and local service platforms.

The current version is configured to avoid third-party product APIs. `api_mode` is forced to `false`, so the system runs through crawler workflows even if API-related environment variables exist.

## Features

- FastAPI backend service.
- Playwright-based crawler tools.
- Standardized product comparison response model.
- Frontend entry page in `index.html`.
- Postman collection and local environment files.
- Configurable crawler timeout, delay, proxy, headless mode, and cookie directory.
- Default stable mode: Taobao-only crawling.

## Project Structure

```text
price-agent/
+-- app/
|   +-- agent/          # Agent planning, analysis, reflection, and engine logic
|   +-- api/            # FastAPI routes
|   +-- models/         # Pydantic request and response models
|   +-- services/       # Compare service and cache service
|   +-- tools/          # Platform crawler implementations
|   +-- config.py       # Runtime settings
|   +-- main.py         # FastAPI application entry
+-- postman/            # Postman collection and local environment
+-- cookies/            # Runtime crawler cookies
+-- debug_output/       # Debug artifacts
+-- index.html          # Frontend page
+-- requirements.txt    # Python dependencies
+-- start.bat           # Windows startup script
+-- .env.example        # Environment variable example
+-- README.md           # Original project notes
```

## Requirements

- Python 3.10 or newer is recommended.
- Chromium browser installed through Playwright.
- Redis is optional depending on cache usage, but `REDIS_URL` is available in configuration.

## Installation

Create and activate a virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Install Playwright Chromium:

```bash
playwright install chromium
```

Create local environment configuration:

```bash
copy .env.example .env
```

Do not commit `.env`, crawler cookies, screenshots, or debug output to GitHub.

## Configuration

Common environment variables:

| Variable | Description | Default |
| --- | --- | --- |
| `LLM_PROVIDER` | LLM provider name. | `glm5` |
| `GLM5_API_KEY` | GLM API key, if LLM features are used. | empty |
| `OPENAI_API_KEY` | OpenAI API key, if LLM features are used. | empty |
| `DEEPSEEK_API_KEY` | DeepSeek API key, if LLM features are used. | empty |
| `REDIS_URL` | Redis connection string. | `redis://localhost:6379/0` |
| `CRAWLER_TIMEOUT` | Crawler timeout in seconds. | `30` |
| `CRAWLER_DELAY` | Delay between crawler requests in seconds. | `2` |
| `CRAWLER_PROXY` | Optional proxy URL. | empty |
| `TAOBAO_COOKIE` | Optional Taobao cookie string. | empty |
| `MEITUAN_LAT` | Default Meituan latitude. | `39.9042` |
| `MEITUAN_LNG` | Default Meituan longitude. | `116.4074` |
| `API_MODE` | API mode flag. Ignored by code and forced to crawler mode. | `false` |

Runtime defaults in `app/config.py`:

- `api_mode = false`
- `taobao_only_mode = true`
- `crawler_headless = true`
- `crawler_max_retries = 3`
- `crawler_cookies_dir = cookies`

## Run

On Windows, start the API service with:

```bash
start.bat
```

Or run FastAPI directly:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

For development with reload:

```bash
python -m uvicorn app.main:app --reload
```

Open the API documentation:

```text
http://localhost:8000/docs
```

Open `index.html` in a browser to use the local frontend.

## API Usage

Health check:

```bash
curl http://localhost:8000/health
```

Get platform capabilities:

```bash
curl http://localhost:8000/api/v1/capabilities
```

Get supported platforms:

```bash
curl http://localhost:8000/api/v1/platforms
```

Run a price comparison:

```bash
curl -X POST http://localhost:8000/api/v1/compare ^
  -H "Content-Type: application/json" ^
  -d "{\"query\":\"iPhone 15\",\"type\":\"shopping\",\"platforms\":[\"taobao\"]}"
```

Example request body:

```json
{
  "query": "iPhone 15",
  "type": "shopping",
  "platforms": ["taobao"]
}
```

Response model:

```json
{
  "query": "iPhone 15",
  "type": "shopping",
  "products": [],
  "best_deal": null,
  "summary": null,
  "generated_at": "2026-04-23T00:00:00"
}
```

## Postman

Import these files into Postman:

- `postman/price-agent.postman_collection.json`
- `postman/price-agent.local.postman_environment.json`

Suggested test order:

1. `Health`
2. `Capabilities`
3. `Compare - Shopping (Taobao)`

## Debugging Crawlers

Run a crawler debug command:

```bash
python debug_crawler.py taobao "iPhone 15"
```

Run with a visible browser:

```bash
python debug_crawler.py taobao "iPhone 15" --no-headless
```

Run with screenshot output:

```bash
python debug_crawler.py taobao "iPhone 15" --screenshot
```

Other crawler scripts in the repository are development and debugging utilities. Keep generated HTML snapshots, screenshots, cookies, and debug output out of version control unless they are intentionally added as test fixtures.

## GitHub Upload Checklist

Before uploading this project to GitHub:

1. Confirm `.env` is not committed.
2. Confirm `cookies/`, `debug_output/`, `__pycache__/`, screenshots, and local HTML snapshots are ignored unless intentionally needed.
3. Keep `.env.example` committed as the configuration template.
4. Include `requirements.txt`, `index.html`, `app/`, `postman/`, and this documentation file.
5. Test startup with `python -m uvicorn app.main:app --reload`.
6. Test `GET /health` and `GET /api/v1/capabilities`.

## Notes

This project depends on public page crawling. Platform page structures, login requirements, anti-bot behavior, and selectors may change over time. Treat crawler stability as an operational concern and keep platform-specific logic isolated in `app/tools/`.
