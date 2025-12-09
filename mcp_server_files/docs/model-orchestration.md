# Model Profiles & Orchestration

This document describes the unified model registry and orchestration system used by both the **Web Dashboard** and **Jexida CLI**.

## Overview

The Jexida platform supports multiple AI models from different sources:

- **External Models**: Cloud-based APIs (OpenAI GPT-5, O-Series, GPT-4.1)
- **Local Models**: Self-hosted via Ollama (llama3, phi3, etc.)

Both the web UI and CLI share a **central registry** and can select models or orchestration strategies uniformly.

## Key Concepts

### Model Profile

A **ModelProfile** defines a single AI model with its capabilities and configuration:

```python
ModelProfile(
    id="gpt-5-nano",                    # Unique identifier
    display_name="GPT-5 Nano",          # Human-readable name
    source=ModelSource.EXTERNAL,        # LOCAL or EXTERNAL
    provider=ModelProvider.OPENAI,      # OLLAMA, OPENAI, AZURE_OPENAI
    model_id="gpt-5-nano",              # API model identifier
    group="🚀 GPT-5 Series (Latest)",   # UI grouping
    tier=ModelTier.BUDGET,              # BUDGET, STANDARD, PREMIUM, FLAGSHIP
    supports_temperature=False,          # Whether temp param works
    supports_tools=True,                 # Function calling support
    ...
)
```

### Strategy

A **ModelStrategy** wraps one or more models for orchestration:

| Strategy Type | Description | Example |
|--------------|-------------|---------|
| `single` | Direct 1:1 mapping to a model | `single:gpt-5-nano` |
| `cascade` | Ordered list, try cheap first | `cascade:cloud-cheapest-first` |
| `router` | (Future) Classification-based | `router:task-based` |

### Cascade Strategies

Cascades try models in order until one succeeds:

```
cascade:cloud-cheapest-first
  ↓ gpt-5-nano (try first - cheapest)
  ↓ gpt-5-mini (escalate if needed)
  ↓ gpt-5     (full power)
  ↓ o1        (ultimate reasoning)
```

## Configuration

### External Models (OpenAI)

Configure in `.env`:

```bash
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-5-nano  # Default model
```

### Local Models (Ollama)

1. Ensure Ollama is running on your MCP server
2. Use the discover endpoint or CLI command to find models:

**Web API:**
```bash
curl -X POST "http://localhost:8080/api/assistant/strategies/discover-local?ollama_host=http://localhost:11434"
```

**CLI:**
```
JEXIDA> /model
```

## API Endpoints

### List Strategies

```
GET /api/assistant/strategies
```

Returns:
```json
{
  "strategies": [...],
  "active_strategy_id": "single:gpt-5-nano",
  "groups": [
    "🔀 Auto / Orchestration",
    "🚀 GPT-5 Series (Latest)",
    "🧠 O-Series (Reasoning)",
    "⭐ GPT-4 Series",
    "🖥️ Local Models"
  ]
}
```

### Get Active Strategy

```
GET /api/assistant/strategies/active
```

### Set Active Strategy

```
POST /api/assistant/strategies/active?strategy_id=cascade:cloud-cheapest-first
```

### Discover Local Models

```
POST /api/assistant/strategies/discover-local?ollama_host=http://192.168.1.224:11434
```

## Web Dashboard Usage

### Select a Model

1. Open the **Assistant** page
2. Click the **Model** dropdown
3. Choose from:
   - **🔀 Auto / Orchestration**: Cascade strategies
   - **🚀 GPT-5 Series**: Latest OpenAI models
   - **🧠 O-Series**: Reasoning-focused models
   - **⭐ GPT-4 Series**: Previous generation
   - **🖥️ Local Models**: Ollama models (after discovery)

### Temperature Control

- Shows only for models that support it (GPT-4 series)
- Hidden for GPT-5, O-series, and cascade strategies
- Slider: 0 (precise) → 2 (creative)

## CLI Usage

### List Available Models & Strategies

```
JEXIDA> /model
```

Shows grouped list with current selection marked.

### Switch to a Model

```
JEXIDA> /model gpt-5-nano
```

Or with full strategy ID:

```
JEXIDA> /model set single:gpt-4.1
```

### Switch to a Cascade Strategy

```
JEXIDA> /model set cascade:cloud-cheapest-first
JEXIDA> /model set cascade:local-first
JEXIDA> /model set cascade:reasoning
```

## Example Flows

### Web: Use Auto-Cascade

1. Open Assistant page
2. Select "Auto — Cheapest First (Cloud)"
3. Send a query
4. System tries `gpt-5-nano` first, escalates if needed

### CLI: Use Local-First

```
JEXIDA> /model set cascade:local-first
🔄 Strategy changed to Auto — Local First

JEXIDA> Plan a multi-step Azure deployment...
[Uses local model first, falls back to cloud if needed]
```

### Web: Use Specific Model

1. Select "GPT-4.1 — Premium · Temp: ✓"
2. Adjust temperature slider (0.3 for precise, 0.9 for creative)
3. Send query

## Built-in Strategies

| Strategy ID | Display Name | Models |
|------------|--------------|--------|
| `cascade:cloud-cheapest-first` | Auto — Cheapest First (Cloud) | gpt-5-nano → gpt-5-mini → gpt-5 → o1 |
| `cascade:local-first` | Auto — Local First | [local models] → gpt-5-nano → gpt-5-mini |
| `cascade:reasoning` | Auto — Reasoning Focus | o3-mini → o4-mini → o1 |
| `single:gpt-5-nano` | GPT-5 Nano | gpt-5-nano only |
| `single:local:llama3:latest` | Llama 3 | llama3:latest only |

## Adding Custom Strategies

In `unified_registry.py`:

```python
registry.create_cascade_strategy(
    strategy_id="cascade:my-custom",
    display_name="My Custom Cascade",
    model_ids=["local:phi3:latest", "gpt-5-nano", "gpt-5"],
    description="Local first, then cloud escalation",
    group="🔀 Auto / Orchestration",
)
```

## Model Groups (UI)

| Group | Icon | Description |
|-------|------|-------------|
| Auto / Orchestration | 🔀 | Cascade and router strategies |
| GPT-5 Series (Latest) | 🚀 | Current gen OpenAI models |
| O-Series (Reasoning) | 🧠 | Reasoning-focused models |
| GPT-4 Series | ⭐ | Previous gen (with temp support) |
| Local Models | 🖥️ | Ollama/self-hosted models |

## Tier Labels

| Tier | Label | Description |
|------|-------|-------------|
| flagship | Most Capable | Maximum performance |
| premium | Premium | High capability |
| standard | Balanced | Good balance |
| budget | Fast & Cheap | Cost-efficient |

## Troubleshooting

### Local models not showing

1. Ensure Ollama is running: `ollama serve`
2. Call discover endpoint with correct host
3. Check server logs for connection errors

### Strategy not found

- Use `/model` to list valid strategy IDs
- Strategy IDs have format: `type:identifier`
  - `single:model-id`
  - `cascade:strategy-name`

### Temperature not working

- Only GPT-4.x series supports temperature
- GPT-5 and O-series use fixed temperature (1.0)
- Cascade strategies hide temp slider

