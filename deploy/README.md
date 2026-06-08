# Deploy

How the live site at `https://$BOXD_VM_NAME.boxd.sh` is served.

- **`wc26-chat.service`** — FastAPI/uvicorn unit (port 8000, behind the boxd proxy) that
  serves the wall chart **and** the "Ask the model" transparency chat. Copy to
  `/etc/systemd/system/`, then `sudo systemctl enable --now wc26-chat`.
- Secrets live **outside** the repo:
  - `~/.config/wc26-chat.env` — `ANTHROPIC_API_KEY` for the chat agent (see
    `wc26-chat.env.example`; chmod 600).
  - `../.env` — `APIFOOTBALL_KEY` / `FOOTBALLDATA_KEY` for the data fetchers (gitignored).

## Regenerate the published chart after a model rerun
```bash
python3 model/fill_sheet.py        # refresh repo index.html with new predictions
python3 model/build_public.py      # write the button-stripped public copy
sudo systemctl restart wc26-chat   # (only needed if app code changed)
```
