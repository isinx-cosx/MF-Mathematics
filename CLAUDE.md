# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Multifunctional-Mathematics is a Python mathematics toolkit (`MF_Mathematics`) covering 12 branches of pure and applied mathematics. A companion UI layer (`MF_UI`) provides graphical workspaces, plotting, and step-by-step calculation views. An AI service module (`MF_AI`) provides LLM-powered math assistance.

## Run tests

```bash
# Run all module tests (preferred entry point)
python -m MF_Mathematics.tests.test_all

# Simpler explicit runner
python -m MF_Mathematics.tests.test_runner

# Run a single module's self_test
python -m MF_Mathematics.number_theory.core_algorithms

# Run a package-level self_test (discovers all submodules)
python -c "import MF_Mathematics.number_theory; print(MF_Mathematics.number_theory.self_test())"

# Top-level self_test (all packages)
python -c "import MF_Mathematics; print(MF_Mathematics.self_test())"
```

There is no build step, linting configuration, or external test framework. Tests are `self_test()` functions inside each module file, using bare `assert` statements.

## Core architecture

### Unified return type: `MathObject`

Every public mathematical function returns a [`MathObject`](MF_Mathematics/core/math_object.py) dataclass with these fields:

| Field | Purpose |
|---|---|
| `result` | Primary result (number, expression string, dict, etc.) |
| `steps` | List of human-readable derivation steps |
| `meaning` | Conceptual interpretation |
| `error` | Error message string (empty = success; check `.ok`) |
| `module` / `action` | Auto-set by the `@register` decorator |

### Function registry

The [`registry`](MF_Mathematics/core/registry.py) module provides a decorator-based dispatch system:

- `@register(module="calculus", action="diff")` — decorates a function, registers it as `"calculus.diff"` in a global dict, and auto-injects `module`/`action` into the returned `MathObject`.
- `dispatch(module, action, *args, **kwargs)` — calls a registered function by key.
- `get_registered_functions(module=None)` — query registered functions.

### Package structure

Each mathematics sub-package under [`MF_Mathematics/`](MF_Mathematics/) follows the same pattern:
- `__init__.py` — re-exports public functions, provides `self_test()` that discovers and runs all submodule tests.
- Individual `.py` files — each contains `@register`-decorated functions and a `self_test()`.

The 12 mathematics sub-packages are:

| Package | Key topics |
|---|---|
| `algebra` | Expressions, equations, inequalities, functions, sequences, combinatorics |
| `calculus` | Limits, derivatives (implicit/parametric), integrals |
| `linear_algebra` | Vector spaces, linear transforms, eigenvalues |
| `probability` | Probability spaces, random variables, distributions, statistics, regression |
| `real_analysis` | Real numbers, sequence/function limits, differentiability, Riemann integral |
| `complex_analysis` | Holomorphic functions, C-R equations, complex integrals, residues, zeta |
| `numerical` | Interpolation, numerical integration, ODE solvers, error analysis |
| `functional_analysis` | Normed spaces, linear operators, spectral theory, dual spaces |
| `harmonic_analysis` | Fourier series/transform, convolutions, distributions |
| `measure_theory` | σ-algebras, measurable functions, Lebesgue integral, convergence theorems |
| `algebraic_topology` | Simplicial complexes, homotopy, homology/cohomology, Betti numbers |
| `number_theory` | GCD, modular arithmetic, prime sieves, continued fractions, zeta interface |

### UI layer (`MF_UI/`)

- [`MF_UI/calc_engine.py`](MF_UI/calc_engine.py) — bridges the UI to `MF_Mathematics` via the registry dispatch.
- [`MF_UI/main_window.py`](MF_UI/main_window.py) — application entry point. Toolbar: 计算 / 绘图 / AI / 搜索 / 历史 / 设置.
- [`MF_UI/calc/`](MF_UI/calc/) — per-topic workspaces (algebra, linear_algebra, numerical, probability). All four share `BaseCalcBlock` + `BaseWorkspace`. All four have three-level guard (REJECT/BLOCK/WARN) + AI acceleration.
- [`MF_UI/plot/`](MF_UI/plot/) — 5 plot modes: normal (2D), 3D, complex, vector_field, arbitrary (geometric drawing).
- [`MF_UI/plot/arbitrary/`](MF_UI/plot/arbitrary/) — GeoGebra-style geometric workspace (QGraphicsView). Shapes: point, segment, circle, vector, line, ellipse, rectangle, polygon. Undo/redo, grid snap, pan/zoom.
- [`MF_UI/plot/mpl_setup.py`](MF_UI/plot/mpl_setup.py) — shared matplotlib init (Qt5Agg backend + Chinese font detection).
- [`MF_UI/ai_dialog.py`](MF_UI/ai_dialog.py) — AI chat dialog (QThread streaming), opened from toolbar "AI" button.
- [`MF_UI/styles/`](MF_UI/styles/) — light.qss / dark.qss theme files.

### AI module (`MF_AI/`)

- [`MF_AI/config.py`](MF_AI/config.py) — Config singleton (env vars + .env + config.yaml priority chain).
- [`MF_AI/config.yaml`](MF_AI/config.yaml) — model mapping (Sonnet→deepseek-v4-pro), per-model params, api_base.
- [`MF_AI/client.py`](MF_AI/client.py) — AIClient (openai lib → httpx fallback), chat + stream_chat, role-based model resolution.
- [`MF_AI/models.py`](MF_AI/models.py) — ChatMessage / ChatRequest / ChatResponse dataclasses.
- [`MF_AI/exceptions.py`](MF_AI/exceptions.py) — AIError hierarchy (AIConfigError, AIAuthError, AIRateLimitError, AITimeoutError, AIResponseError).
- Public API: `from MF_AI import chat, stream_chat, set_api_key, set_model`.

### AI accelerator

[`MF_Mathematics/utils/ai_accelerator.py`](MF_Mathematics/utils/ai_accelerator.py) — wraps `MF_AI.chat()` for math-specific use cases:
- `generate_steps(question, expr)` — step-by-step math derivation (consumes "steps" quota, 5/day)
- `accelerate(expr, mode)` — AI-assisted complex computation (consumes "accelerations" quota, 3/day)
- `chat(question)` — free-form AI dialog (no quota)
- `QuotaManager` — daily usage tracking in `usage.json`
- Singleton: `get_accelerator()`

### Configuration

- [`config.json`](config.json) — runtime guardrails: math complexity limits, plot ranges, numerical precision caps.
- [`MF_AI/config.yaml`](MF_AI/config.yaml) — AI model mapping and parameters (user-editable).
- `.env` — API keys (AI_API_KEY, AI_BASE_URL, etc.), never committed.

### Dependencies

- `numpy` — used across most modules for numerical computation.
- `sympy` — used in calculus, complex analysis, and anywhere symbolic manipulation is needed.
- `PySide6` — Qt for Python, all UI code.
- `matplotlib` — used in 3D, complex, and vector_field plot modes.
- `openai` (optional) — preferred backend for MF_AI. Falls back to `httpx` if not installed.

## Code conventions

- All public math functions use the `@register(module="...", action="...")` decorator.
- Every `.py` module that contains `@register`-decorated functions also has a `self_test()` that exercises them with `assert` statements and prints `[PASS]`/`[FAIL]`.
- Error handling: catch exceptions inside the `@register`-decorated function and return `MathObject(error=str(e))` — never let exceptions propagate to callers.
- Docstrings are in Chinese with type annotations in English. Function signatures use `from __future__ import annotations`.
- Chinese comments and docstrings throughout the codebase.

## Frontend design guidelines

When generating or modifying PySide6 UI code:
- Prefer dark theme styles defined in `MF_UI/styles/dark.qss`.
- Use `QSS` for styling rather than inline `setStyleSheet` where possible.
- Layouts should be responsive to window resizing.
- All dialogs should be modal and centered on the parent window.
- Plot modes must NOT cross-import from each other (e.g., plot_3d/ must not import from basic/).

## Code review expectations

When reviewing code changes:
- All public functions must have docstrings (Chinese preferred, type hints required).
- Any `except Exception` block must include an error message explaining what went wrong.
- Check that no configurations are hardcoded; values like thresholds, colors, or limits must be read from `config.json` or `MF_AI/config.yaml`.
- Ensure UI and core logic separation: `MF_Mathematics` modules must not import `PySide6`.
- New AI features should use `MF_AI` client, not raw HTTP calls.

## Project file map (non-obvious locations)

| Path | Purpose |
|---|---|
| `_archive/` | Archived unused modules (latex_render.py, math_input.py, user_system.py) — safe to delete |
| `usage.json` | AI quota daily tracking (gitignored, runtime data) |
| `CODE_SCAN_REPORT.txt` | Last code audit report (2026-07-15) |
| `CODE_AUDIT_REPORT.txt` | Older audit report (may be stale) |
