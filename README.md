# comic-agent

`comic-agent` is a Python multi-agent pipeline that converts a plain text storyline into:

- structured panel metadata (`manifest.json`)
- generated panel images (`panels/*.png`)
- run logs (`run.log`)

## Requirements

- Python `3.11+`
- `OPENAI_API_KEY` environment variable for real image generation

If the OpenAI image API is unavailable, the panel agent falls back to deterministic placeholder PNGs.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

Create an input story file:

```bash
cat > story.txt <<'EOF'
A rookie detective and a sarcastic robot partner chase a neon thief through a rain-soaked city.
EOF
```

Run:

```bash
comic-agent run --input story.txt --output ./out --verbose
```

## CLI

```bash
comic-agent run \
  --input /path/to/story.txt \
  --output /path/to/output_dir \
  [--max-panels 12] \
  [--seed 123] \
  [--verbose]
```

You can also run via module:

```bash
python -m comic_agent.cli run --input story.txt --output ./out --verbose
```

## Output Structure

Example output directory:

```text
out/
  manifest.json
  run.log
  panels/
    panel-001.png
    panel-002.png
    ...
```

`manifest.json` includes scenes, characters, panel specs, bubble metadata, continuity results, and validation status.

## Agent Pipeline

1. `IngestAgent`: Reads storyline text.
2. `SceneAgent`: Splits text into scene beats.
3. `CharacterAgent`: Extracts key characters.
4. `StyleAgent`: Builds global visual style guidance.
5. `PanelAgent`: Produces panel specs and image files.
6. `ContinuityAgent`: Checks cross-panel consistency.
7. `ValidatorAgent`: Enforces rules; manager retries one deterministic revision pass if needed.

## Development

Run tests:

```bash
pytest
```

Lint:

```bash
ruff check .
```

Type check:

```bash
mypy src
```
