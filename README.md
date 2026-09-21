# Jev Tester UI

A small local web page for trying the [TypeSafe](https://typesafe.ai/) Jev API (`/v1/systemone`).
Build Choice, Score, and Yes/No (Noul) questions in a form, run them, and read the answers as bars, scales, and gauges instead of raw JSON.

## Run

```bash
python3 server.py
```

Open http://127.0.0.1:8765. Python 3.9+ standard library only, nothing to install.

The server reads the API key from the first of these it finds, in the environment or in `~/.env`:

- `TYPESAFE_API_KEY`
- `TPYEAFE_JEV_API_KEY_FROM_YI_20260921`

The key stays in the Python process. The page talks to `/api/*` on localhost, and the server adds the key when it forwards to `https://api.typesafe.ai`.

## Use

- Pick an example from the header, or start from **Blank**.
- Any text field takes plain text or JSON. Valid JSON objects and arrays are sent as JSON.
- **Edit as JSON** shows the full request body. Switching back parses it into the form.
- `Cmd/Ctrl + Enter` runs. Raw request and response JSON sit under each result.

## Test

```bash
python3 -m unittest discover -s tests
```

The tests check that the key is loaded correctly, sent upstream as a bearer token, passed through on errors, and never served to the browser.
