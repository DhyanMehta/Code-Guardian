# Default Python Coding Standards

This document defines the default Python coding standards used by CodeGuardian's Quality Agent.
It is organized into four explicit categories separating deterministic AST enforcement from
AI-assisted advisory guidance.

---

## A. Deterministically Enforceable Rules (Python)

These rules are verified deterministically against Python AST and diff hunks without depending
on LLM reasoning:

- **Maximum Function Length (`maximum_function_length`):** A single Python function or method
  should not exceed **40 lines** of logic (excluding blank lines, decorators, and the docstring).
  Functions exceeding 40 logic lines must be decomposed into smaller, well-named helpers.
- **Maximum Positional Parameters (`maximum_positional_parameters`):** Python functions and
  methods should accept **5 or fewer positional parameters** (excluding `self`/`cls` on methods).
  Use keyword-only arguments (after `*`) or a configuration dataclass when more parameters are
  needed.
- **Postponed Annotations (`future_annotations_import`):** Use `from __future__ import annotations`
  at the top of every Python module to enable postponed evaluation of type annotations.

---

## B. AI-Assisted Advisory Guidance (Python)

These principles are evaluated by the Quality Agent's RAG-grounded LLM review when standards
context is available:

### B.1 Naming Conventions (PEP 8)

- **Modules and Packages:** Use short, all-lowercase names with underscores (`user_auth.py`,
  `data_pipeline/`), not `UserAuth.py` or `DataPipeline/`.
- **Classes and Exceptions:** Use PascalCase (`HttpClient`, `SecurityAgent`). Exception classes
  must end with `Error` (`ScannerTimeoutError`, `LLMConfigError`).
- **Functions and Methods:** Use `snake_case` (`run_scanner()`, `get_or_create_collection()`).
  Prefix internal helpers with a single underscore (`_parse_response()`). Boolean-returning
  functions should read as questions (`is_valid()`, `has_findings()`). Avoid generic names
  (`do_stuff`, `handle`, `process`) without a qualifying noun.
- **Variables and Constants:** Use `snake_case` for local variables and parameters, and
  `UPPER_SNAKE_CASE` for module-level constants (`MAX_RETRIES`, `DEFAULT_TIMEOUT_SECONDS`).
  Avoid single-character names outside comprehensions and trivial loop counters.

### B.2 Complexity, Control Flow, and Maintainability

- Aim for a cyclomatic complexity of **10 or less** per function.
- Refactor deeply nested conditionals (more than 3 levels) using early returns, guard clauses,
  or helper extraction.
- Avoid boolean flag parameters that switch behavior; prefer two clearly named functions.
- Prefer pure, single-responsibility helpers and avoid duplicating non-trivial logic across
  adjacent branches.

### B.3 Error Handling and Resilience

- Every external call (network, subprocess, file I/O, database) must have explicit error handling.
- Never use bare `except:` or swallow `except Exception:` silently without re-raising or logging.
- Prefer typed exception hierarchies over generic exceptions, and include operation context,
  identifiers, and underlying cause in error messages (never secrets or tokens).

### B.4 Imports, Types, and Docstrings (PEP 8 & PEP 257)

- Group imports in order separated by blank lines: (1) standard library, (2) third-party
  packages, (3) local project imports. Use absolute imports and never use wildcard imports
  (`from module import *`).
- All public Python functions and methods should have complete type annotations (parameters
  and return type), preferring modern syntax (`list[str]`, `str | None`).
- Public modules, classes, and functions require a concise PEP 257 docstring using imperative
  mood in the summary line ("Return the ...", "Parse the ...").

---

## C. Python-Specific Conventions Summary

- Follow PEP 8 naming, import ordering, and 4-space indentation conventions.
- Follow PEP 257 docstring conventions (documented in detail in Section B.4 and checked for
  missing/outdated signatures by the Documentation Agent).
- Keep module-level side effects minimal; initialize clients and database engines lazily.

---

## D. Guidance Not Currently Enforceable Deterministically

The following standards are **advisory only** and are **not** enforced deterministically by
AST predicates:

- Cyclomatic complexity thresholds, nesting depth, and boolean-flag parameter refactoring.
- Semantic naming quality (e.g., whether a function name is overly generic).
- Import sorting/grouping, error-handling completeness, and `except Exception` quality.
- PEP 257 docstring phrasing quality (imperative mood, clarity) beyond missing/outdated parameter
  detection.
