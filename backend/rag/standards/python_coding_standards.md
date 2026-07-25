# Python Coding Standards

This document defines the coding standards enforced by CodeGuardian's Quality Agent.
Violations are reported as quality findings on pull requests.

---

## 1. Naming Conventions

### 1.1 Modules and Packages

- Use short, all-lowercase names.
- Use underscores to separate words: `user_auth.py`, not `UserAuth.py` or `userauth.py`.
- Package directories follow the same rule: `data_pipeline/`, not `DataPipeline/`.

### 1.2 Classes

- Use PascalCase (CapitalizedWords): `HttpClient`, `SecurityAgent`, `RawFinding`.
- Avoid abbreviations unless universally understood (`HTTP`, `URL`, `ID` are acceptable).
- Exception classes must end with `Error`: `ScannerTimeoutError`, `LLMConfigError`.

### 1.3 Functions and Methods

- Use snake_case: `run_scanner()`, `get_or_create_collection()`.
- Prefix internal/private helpers with a single underscore: `_parse_response()`.
- Boolean-returning functions should read as questions: `is_valid()`, `has_findings()`.
- Avoid generic names (`do_stuff`, `handle`, `process`) without a qualifying noun.

### 1.4 Variables and Constants

- Local variables and parameters: snake_case (`file_path`, `retry_count`).
- Module-level constants: UPPER_SNAKE_CASE (`MAX_RETRIES`, `DEFAULT_TIMEOUT_SECONDS`).
- Avoid single-character names outside of comprehensions and trivial loop counters.
- Boolean variables should read as assertions: `is_active`, `has_error`, `should_retry`.

### 1.5 Type Aliases and TypedDicts

- Type aliases use PascalCase: `RunnerFn`, `ScanResult`.
- TypedDict classes use PascalCase: `ReviewState`, `PRMetadata`.

---

## 2. Function Length and Complexity

### 2.1 Maximum Function Length

- A single function or method should not exceed **40 lines** of logic (excluding blank
  lines, decorators, and the docstring).
- If a function exceeds 40 lines, it must be decomposed into smaller, well-named helpers.

### 2.2 Cyclomatic Complexity

- A function should have a cyclomatic complexity of **10 or less**.
- Deeply nested conditionals (more than 3 levels) must be refactored using early returns,
  guard clauses, or helper extraction.

### 2.3 Parameter Count

- Functions should accept **5 or fewer positional parameters**.
- Use keyword-only arguments (after `*`) or a configuration dataclass when more parameters
  are needed.
- Avoid boolean flag parameters that switch behavior; prefer two clearly named methods.

---

## 3. Project-Specific Style Rules

### 3.1 Error Handling

- Every external call (network, subprocess, file I/O) must have explicit error handling.
- Never use bare `except:` or `except Exception:` without re-raising or logging.
- Typed exception hierarchies are preferred over generic exceptions. Define a base
  error class per module/subsystem (`ScannerError`, `LLMError`) and specific subclasses.
- Errors must include enough context to diagnose without reproducing: include the
  operation attempted, relevant identifiers, and the underlying cause.

### 3.2 Import Organization

- Group imports in this order, separated by blank lines:
  1. Standard library
  2. Third-party packages
  3. Local/project imports
- Use absolute imports from the package root: `from backend.tools.results import RawFinding`.
- Never use wildcard imports (`from module import *`).
- Sort imports alphabetically within each group.

### 3.3 Type Annotations

- All public functions and methods must have complete type annotations (parameters and
  return type).
- Use `from __future__ import annotations` at the top of every module to enable
  postponed evaluation.
- Prefer modern syntax: `list[str]` over `List[str]`, `str | None` over `Optional[str]`.
- Internal helpers may omit annotations when the types are obvious from context, but
  annotate anything non-trivial.

### 3.4 Docstrings

- Public classes and public functions require a one-line docstring at minimum.
- Multi-line docstrings use the imperative mood in the summary line: "Return the ...",
  "Parse the ...", not "Returns the ..." or "This function parses ...".
- Internal helpers (`_prefixed`) do not require docstrings unless the logic is non-obvious.
- Do not repeat type annotations in the docstring; the type system already documents them.
