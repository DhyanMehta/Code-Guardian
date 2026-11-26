# Default Frontend (JavaScript and TypeScript) Coding Standards

This document defines the default JavaScript, TypeScript, JSX, and TSX coding standards
used by CodeGuardian's Quality Agent. Rules here apply strictly to JavaScript and
TypeScript files (`.js`, `.jsx`, `.ts`, `.tsx`).

---

## A. Deterministically Enforceable Rules (JavaScript & TypeScript)

These rules are evaluated deterministically via the TypeScript AST parser for exported
JavaScript and TypeScript functions/components:

- **Maximum Function Length (`maximum_function_length`):** An exported JavaScript or
  TypeScript function or component should not exceed **40 lines** of logic (excluding blank
  lines and comments).
- **Maximum Positional Parameters (`maximum_positional_parameters`):** Exported JavaScript
  or TypeScript functions should accept **5 or fewer positional parameters**; prefer an
  options/props object when more arguments are needed.

---

## B. AI-Assisted Advisory Guidance (JavaScript & TypeScript)

- **TypeScript Strictness:** Avoid `any`; model API payloads, component props, and union
  states with explicit interfaces, discriminated unions, or `unknown` with type guards.
- **React & State Hygiene:** Keep `useEffect` dependency arrays complete, clean up timers and
  subscriptions, and avoid mutating state or props directly.
- **Error Handling & Security:** Handle rejected promises explicitly, avoid `dangerouslySetInnerHTML`
  with untrusted input, and never embed API keys or secrets in client bundles.
- **Accessibility:** Use semantic HTML elements (`button`, `nav`, `main`), accessible labels,
  and keyboard-focusable controls.

---

## C. Language-Specific Conventions (JavaScript & TypeScript)

- Use `camelCase` for functions and variables, `PascalCase` for React components and types,
  and `UPPER_SNAKE_CASE` for module constants.
- Document exported functions and complex utilities with JSDoc (`@param`, `@returns`) matching
  the actual parameter list.

---

## D. Guidance Not Currently Enforceable Deterministically

- Cyclomatic complexity, React hook dependency correctness, semantic naming, and `any`
  usage remain advisory rather than deterministic AST predicates.
