# comic-agent

`comic-agent` is a Python multi-agent pipeline that converts a plain text storyline into:

- structured panel metadata (`manifest.json`)
- generated panel images (`panels/panel-*.png`, one image per panel)
- run logs (`run.log`)

## Summary

`comic-agent` takes a text story and runs it through a sequence of specialized agents that:

- infer scenes and beats from narrative text
- extract characters and style direction
- generate comic panel prompts/images (4 subpanels per panel image)
- attach panel speech-bubble or silent background-context metadata
- validate continuity and rule compliance
- export run outputs (`manifest.json`, panel images, and `panels.pdf`)

[Live Gallery (GitHub Pages)](https://baqiral-1.github.io/comic_agent/)

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
  [--max-panels N] \
  [--seed 123] \
  [--skip-image-generation] \
  [--verbose]
```

You can also run via module:

```bash
python -m comic_agent.cli run --input story.txt --output ./out --verbose
```

`--skip-image-generation` generates planning/manifest outputs only (no panel PNGs or PDF).
If `--max-panels` is omitted, scene/panel count is inferred automatically.

## Output Structure

Example output directory:

```text
out/
  manifest.json
  run.log
  panels.pdf
  panels/
    panel-001.png
    panel-002.png
    ...
```

If `--skip-image-generation` is used, output includes only `manifest.json` and `run.log`.

`manifest.json` includes scenes, characters, nested panel specs (4 subpanels per panel),
bubble metadata, optional `background_context_prompt` for silent subpanels, continuity
results, and validation status.

## Agent Pipeline

1. `IngestAgent`: Loads the input story file and normalizes whitespace.
   Produces a clean `StoryDocument` used by all downstream agents.
2. `SceneAgent`: Infers scene boundaries and beat-level actions from narrative text.
   Uses an LLM for scene segmentation with a deterministic fallback path.
3. `CharacterAgent`: Identifies primary story participants and basic profile traits.
   Provides character metadata used for panel planning and bubble speaker defaults.
4. `StyleAgent`: Derives a global comic style profile (tone, palette, camera language).
   Keeps visual direction consistent across all generated panels.
5. `PanelAgent`: Converts scenes/beats into nested `PanelSpec` entries (4 subpanels each)
   and generates one composite panel image per `panel_id`.
   Also creates speech-bubble metadata and optional `background_context_prompt` for
   no-dialogue subpanels.
6. `ContinuityAgent`: Applies lightweight continuity checks between adjacent panels.
   Flags potential scene-transition inconsistencies for validation.
7. `ValidatorAgent`: Enforces structural and content rules on generated panel specs.
   If validation fails, the manager applies one revision pass and revalidates.

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
