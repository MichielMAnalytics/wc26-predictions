"""
WC26 predictions site + transparency chat backend.

- GET  /            -> the existing wall chart (site/index.html) with the chat
                        widget injected before </body> at request time (so a
                        model rebuild that regenerates index.html keeps the widget).
- POST /api/chat    -> Server-Sent Events stream from the explainer agent.
- everything else   -> static files from site/.

The Anthropic API key lives only in the server environment (ANTHROPIC_API_KEY);
it is never sent to the browser.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse, JSONResponse

from agent import run_agent

SITE = Path(__file__).resolve().parent.parent.parent / "site"
INDEX = SITE / "index.html"
WIDGET = (Path(__file__).resolve().parent / "widget.html").read_text(encoding="utf-8")

app = FastAPI(title="WC26 predictions")


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    html = INDEX.read_text(encoding="utf-8")
    if "wc26-chat-root" not in html:  # idempotent inject
        html = html.replace("</body>", WIDGET + "\n</body>", 1)
    return HTMLResponse(html)


@app.post("/api/chat")
async def chat(request: Request) -> StreamingResponse:
    body = await request.json()
    user_message = (body.get("message") or "").strip()
    history = body.get("history") or []
    # keep only well-formed text turns, bound the history we trust
    clean: list[dict] = [
        {"role": m["role"], "content": m["content"]}
        for m in history
        if isinstance(m, dict)
        and m.get("role") in ("user", "assistant")
        and isinstance(m.get("content"), str)
    ][-12:]

    if not user_message:
        return JSONResponse({"error": "empty message"}, status_code=400)

    def sse():
        for ev in run_agent(clean, user_message):
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        sse(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# Static assets (CSS/images/etc.) live alongside index.html in site/.
@app.get("/{path:path}")
def static_files(path: str):
    target = (SITE / path).resolve()
    if SITE in target.parents and target.is_file():
        return FileResponse(target)
    return JSONResponse({"error": "not found"}, status_code=404)
