# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Multifunctional-Mathematics is a Python mathematics toolkit (`MF_Mathematics`) covering 12 branches of pure and applied mathematics. A companion UI layer (`MF_UI`) provides graphical workspaces, plotting, and step-by-step calculation views.

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
- [`MF_UI/main_window.py`](MF_UI/main_window.py) — application entry point.
- [`MF_UI/calc/`](MF_UI/calc/) — per-topic workspaces and step viewers.
- [`MF_UI/plot/`](MF_UI/plot/) — 2D, 3D, complex, and vector field plotting.
- [`MF_UI/auth/user_system.py`](MF_UI/auth/user_system.py) — user authentication.

### Configuration

[`config.json`](config.json) defines runtime guardrails: math complexity limits (max ops, polynomial degree, matrix dimension), plot ranges, numerical precision caps, and AI usage quotas.

### Dependencies

- `numpy` — used across most modules for numerical computation.
- `sympy` — used in calculus, complex analysis, and anywhere symbolic manipulation is needed.

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

## Code review expectations

When reviewing code changes:
- All public functions must have docstrings (Chinese preferred, type hints required).
- Any `except Exception` block must include an error message explaining what went wrong.
- Check that no configurations are hardcoded; values like thresholds, colors, or limits must be read from `config.json`.
- Ensure UI and core logic separation: `MF_Mathematics` modules must not import `PySide6`.