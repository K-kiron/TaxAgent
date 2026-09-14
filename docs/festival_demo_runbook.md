# TaxAgent Festival Demo Runbook

This demo has two layers:

- Public static demo: safe default, no model call, no profile persistence.
- Private live demo: optional, PIN-gated, localhost-only, intended for staff-guided use.

## Local Static Demo

Windows PowerShell:

```powershell
.venv\Scripts\python.exe -m uvicorn taxagent.web.app:app --host 127.0.0.1 --port 8055
```

Linux/macOS:

```bash
bash infra/run_ui.sh
```

Open:

```text
http://127.0.0.1:8055
```

The public static demo works even if the model server is not running.

## Private Live Demo

Keep vLLM bound to localhost:

```bash
bash infra/serve_35b_mvp.sh
```

Start the UI with live mode and a temporary PIN.

Windows PowerShell:

```powershell
$env:TAXAGENT_DEMO_LIVE_ENABLED="1"
$env:TAXAGENT_DEMO_PIN="<choose-a-temporary-pin>"
$env:TAXAGENT_DEMO_MAX_CONCURRENT="1"
$env:TAXAGENT_DEMO_MAX_CHARS="800"
.venv\Scripts\python.exe -m uvicorn taxagent.web.app:app --host 127.0.0.1 --port 8055
```

Linux/macOS:

```bash
TAXAGENT_DEMO_LIVE_ENABLED=1 \
TAXAGENT_DEMO_PIN="<choose-a-temporary-pin>" \
TAXAGENT_DEMO_MAX_CONCURRENT=1 \
TAXAGENT_DEMO_MAX_CHARS=800 \
bash infra/run_ui.sh
```

## Public URL Through A Tunnel

Expose only the UI port:

```bash
cloudflared tunnel --url http://127.0.0.1:8055
```

or:

```bash
ngrok http 127.0.0.1:8055
```

Never tunnel or expose the model port:

```text
Do not expose http://127.0.0.1:8011
Do not run vLLM on 0.0.0.0 for this demo
Do not use router port forwarding to the PC
```

Treat the tunnel URL as public. The PIN is the live-mode gate; the static demo remains safe if the URL spreads.

## Safety Checks

Check the public app surface:

```bash
curl http://127.0.0.1:8055/api/demo-config
curl -i http://127.0.0.1:8055/docs
curl -i http://127.0.0.1:8055/openapi.json
curl -i http://127.0.0.1:8055/api/profile/test
```

Expected:

- `/api/demo-config` returns JSON without the PIN.
- `/docs`, `/openapi.json`, and `/api/profile/test` return `404`.
- `/api/chat` returns `503` unless live mode is explicitly enabled.

Windows port check:

```powershell
netstat -ano | findstr ":8011"
netstat -ano | findstr ":8055"
```

Linux port check:

```bash
ss -ltnp | grep -E ':8011|:8055'
```

Expected:

- `8011` is bound to `127.0.0.1` only.
- `8055` is bound to `127.0.0.1` only.
- The tunnel points to `127.0.0.1:8055`, never `8011`.

## After The Event

- Stop the tunnel.
- Stop the UI server.
- Stop vLLM if it was used.
- Remove the temporary `TAXAGENT_DEMO_PIN` from shell history if it was sensitive.
- Do not keep attendee-provided sensitive tax facts; the web demo does not write profiles.
