# comic-agent

`comic-agent` is a Python multi-agent pipeline that turns a text story into comic planning data and panel images.

- structured run manifest (`manifest.json`)
- panel images (`panels/panel-*.png`, one image per panel)
- optional panel PDF (`panels.pdf`)
- run logs (`run.log`)

[Live Gallery (GitHub Pages)](https://baqiral-1.github.io/comic_agent/)

## Summary

The pipeline ingests a story, infers scenes and characters, plans 4-subpanel comic panels, validates output quality, and exports artifacts for viewing or publishing.

## Agent Pipeline

1. `IngestAgent`: Reads the input file and normalizes story text.
2. `SceneAgent`: Uses an LLM to infer scene boundaries/beats with deterministic sentence-chunk fallback.
3. `CharacterAgent`: Uses an LLM to infer character profiles (name, role, description, traits, speech style) with heuristic fallback.
4. `StyleAgent`: Builds a global style guide (tone, palette, camera language) from scene mood.
5. `PanelAgent`: Generates one panel per scene, each panel containing exactly 4 subpanels with either dialogue bubbles or background context.
6. `ContinuityAgent`: Flags simple continuity risks between adjacent panels.
7. `ValidatorAgent`: Enforces structure/content/image checks and feeds one manager revision attempt for non-image issues.

## Requirements

- Python `3.11+`
- `OPENAI_API_KEY` for real LLM/image generation

Without `OPENAI_API_KEY`, the pipeline still runs using deterministic fallbacks and placeholder panel images.

## Run Modes

1. Full generation mode
   `OPENAI_API_KEY` set and no `--skip-image-generation`.
   Produces `manifest.json`, `run.log`, panel PNGs, and `panels.pdf`.
2. Planning-only mode
   Use `--skip-image-generation`.
   Produces `manifest.json` and `run.log` only.
3. Fallback image mode
   No `OPENAI_API_KEY` and no `--skip-image-generation`.
   Produces `manifest.json`, `run.log`, placeholder panel PNGs, and `panels.pdf`.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

Create input:

```bash
cat > story.txt <<'EOF'
A rookie detective and a sarcastic robot partner chase a neon thief through a rain-soaked city.
EOF
```

Run:

```bash
comic-agent run --input story.txt --output ./out --verbose
```

Module form:

```bash
python -m comic_agent.cli run --input story.txt --output ./out --verbose
```

## CLI

```bash
comic-agent run \
  --input /path/to/story.txt \
  --output /path/to/output_dir \
  [--max-panels N] \
  [--skip-image-generation] \
  [--verbose]
```

- `--max-panels` caps panel count at planning/render time.
- For scene inference, `--max-panels` is treated as a pacing target (soft guidance).
- `--skip-image-generation` skips image/PDF creation entirely.

## Environment Variables

- `OPENAI_API_KEY`: Enables OpenAI-backed scene/character/panel inference and real image generation.
- `COMIC_AGENT_IMAGE_WORKERS`: Parallel panel image generation worker count (default `1`).
- `COMIC_AGENT_IMAGE_SIZE`: Image API size string for generated panel images (default `1024x1024`).
- `COMIC_AGENT_PANEL_PLANNER_MODEL`: Override LLM model used by panel planning (default `gpt-4.1-mini`).
- `COMIC_AGENT_CHARACTER_TIMEOUT_SECONDS`: Timeout for character LLM inference in seconds (default `60`).

## Output Structure

Typical output directory:

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

When `--skip-image-generation` is enabled:

```text
out/
  manifest.json
  run.log
```

`manifest.json` contains:

- `scenes[]`: `scene_id`, `summary`, `beats[]`
- `characters[]`: `name`, `role`, `description`, `visual_traits[]`, `speech_style`
- `panel_specs[]`: `panel_id`, `scene_id`, `subpanels[]`
- `subpanels[]`: `sub_panel_id`, `description`, `prompt`, `characters_involved[]`, `bubbles[]`, optional `background_context_prompt`
- run outcomes: `panel_images[]`, `panel_pdf`, `continuity_issues[]`, `validation`, `revisions_attempted`

## Development

```bash
pytest
ruff check .
mypy src
```
