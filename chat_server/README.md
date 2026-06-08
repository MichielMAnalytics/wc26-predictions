# Transparency chat (server-side agent)

A FastAPI server that serves the wall chart **and** a "How we predicted this"
chat widget. The widget (bottom-right of the page) opens an Anthropic tool-use
agent that answers visitor questions about how the predictions were produced —
grounded in the real model outputs so every number is exact and traceable.

## Pieces
- `app.py` — serves `../../site/index.html` with `widget.html` injected before
  `</body>` at request time (rebuilds of index.html keep the widget); exposes
  `POST /api/chat` as a Server-Sent-Events stream; serves other static files.
- `agent.py` — the agent: `claude-sonnet-4-6`, adaptive thinking, a manual
  streaming tool-use loop, and 8 read-only tools over `MODEL.md`,
  `data/model/*.csv`, and `data/predictions/*`. System prompt forbids inventing
  numbers — answers must come from tool results.
- `widget.html` — self-contained floating chat UI (scoped CSS/JS), styled to
  match the chart; streams text + per-tool status; minimal safe markdown.

## Run
Served by **`wc26-chat.service`** (systemd) on port 8000, which the boxd proxy
forwards to `https://$BOXD_VM_NAME.boxd.sh`. It replaced the old static
`wc26-sheet.service` (now disabled).

```bash
sudo systemctl restart wc26-chat.service
sudo systemctl status  wc26-chat.service
journalctl -u wc26-chat.service -f
```

Local dev:
```bash
set -a; . /home/boxd/.config/wc26-chat.env; set +a   # ANTHROPIC_API_KEY
../.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
```

## API key
Stored **only** server-side in `/home/boxd/.config/wc26-chat.env` (chmod 600,
outside the git repo) and loaded via the unit's `EnvironmentFile`. It is never
sent to the browser.

## Adding/changing tools
Add a `t_*` function in `agent.py`, register it in `TOOL_IMPLS` and `TOOLS`,
then restart the service. Keep tools read-only and returning real file data.
