# CodeGuardian AI — Architecture

```mermaid
flowchart TB
    %% Entry
    GH[GitHub PR Event<br/>webhook delivery] -->|HMAC-signed POST| WH[Webhook Receiver<br/>FastAPI]
    WH -->|background task| RS[Review Service]

    %% Orchestration
    RS -->|shallow clone<br/>depth=2, 60s timeout| WS[Workspace Checkout<br/>temp directory]
    RS -->|git diff HEAD~1| DIFF[Diff Parser<br/>per-file hunk ranges]
    RS --> SUP[Supervisor Agent<br/>LangGraph orchestrator]

    %% Fan-out
    SUP -->|parallel| SEC[Security Agent]
    SUP -->|parallel| QUA[Quality Agent]
    SUP -->|parallel| TGA[Test-Gap Agent]
    SUP -->|parallel| DOC[Documentation Agent]

    %% Security Agent internals
    SEC --> SEM[Semgrep]
    SEC --> BAN[Bandit]
    SEC --> GLK[Gitleaks]
    SEC -->|raw findings only| LLM1[LLM Triage<br/>fingerprint-locked]

    %% Quality Agent internals
    QUA --> RAG[RAG Retrieval<br/>ChromaDB]
    QUA -->|grounded review| LLM2[LLM Review<br/>passage-anchored]
    QUA --> VAL[Validation Gates<br/>AST symbol, counts,<br/>naming, passage index]

    %% Test-Gap Agent internals
    TGA --> AST1[AST Analysis<br/>function extraction]
    TGA --> TST[Test Discovery<br/>existing test scan]
    TGA -->|untested functions| LLM3[LLM Draft<br/>test stubs]

    %% Documentation Agent internals
    DOC --> AST2[AST Docstring Check]
    DOC -->|missing/outdated| LLM4[LLM Draft<br/>docstrings]

    %% Aggregation
    SEC --> AGG[Aggregator<br/>deduplicate + severity-rank]
    QUA --> AGG
    TGA --> AGG
    DOC --> AGG

    %% Output
    AGG --> RPT[Report Builder]
    RPT --> PRC[PR Comment<br/>GitHub API]
    RPT --> DB[(PostgreSQL<br/>reviews, findings,<br/>agent runs)]
    DB --> DASH[React Dashboard<br/>Tailwind CSS]

    %% Auto-fix
    RPT -->|fixable findings| AFX[Auto-Fix Service]
    AFX -->|creates branch| AFB[Fix Branch<br/>approval-gated]

    %% Rate limiting
    LLM1 -.- THR[Process-wide Throttle<br/>semaphore + 1.5s interval]
    LLM2 -.- THR
    LLM3 -.- THR
    LLM4 -.- THR

    %% Styling
    classDef scanner fill:#e8f4e8,stroke:#2d7d2d
    classDef llm fill:#fff3e0,stroke:#e65100
    classDef gate fill:#e3f2fd,stroke:#1565c0
    classDef storage fill:#f3e5f5,stroke:#6a1b9a

    class SEM,BAN,GLK scanner
    class LLM1,LLM2,LLM3,LLM4 llm
    class VAL,DIFF gate
    class DB,RAG storage
```

## Data Flow Summary

1. **Trigger**: GitHub delivers a `pull_request` webhook (HMAC-verified).
2. **Checkout**: Shallow clone (depth=2) into a temp directory; diff extracted via `git diff HEAD~1`.
3. **Fan-out**: Supervisor dispatches all 4 agents in parallel.
4. **Scan**: Security Agent runs 3 deterministic scanners; findings scoped to diff hunks.
5. **Triage**: LLM explains/ranks scanner findings — fingerprint-locked (cannot invent findings).
6. **Review**: Quality Agent retrieves coding standards via RAG, reviews diff, validates via 6 gates.
7. **Gaps**: Test-Gap Agent identifies untested functions via AST analysis, drafts test stubs.
8. **Docs**: Documentation Agent flags missing docstrings, drafts replacements.
9. **Aggregate**: Supervisor deduplicates, severity-ranks, builds the PR comment.
10. **Persist**: Findings stored in PostgreSQL; surfaced in the React dashboard.
11. **Auto-fix**: Fixable findings can generate a branch (requires explicit human approval).

## Key Design Principles

| Principle | Implementation |
|-----------|---------------|
| LLM never originates findings | Security: fingerprint-locked triage. Quality: passage + symbol + gate anchoring. |
| Deterministic verification | 6 validation gates: passage index, symbol existence, file scope, countable claims, naming conventions, diff containment |
| Graceful degradation | Each agent reports OK or DEGRADED; one failure never blocks the others |
| Human stays in control | Auto-fix branch requires explicit approval before merge |
| Rate-limit resilience | Process-wide semaphore + 1.5s minimum interval between LLM calls |

## Security Agent Detail

```mermaid
flowchart LR
    WS[Workspace] --> S1[Semgrep<br/>SAST rules]
    WS --> S2[Bandit<br/>Python security]
    WS --> S3[Gitleaks<br/>secret detection]

    S1 --> NRM[Path Normalization<br/>workspace-relative]
    S2 --> NRM
    S3 --> NRM

    NRM --> SCOPE[Diff Scoping<br/>keep only findings<br/>in changed hunks]

    SCOPE --> TRIAGE[LLM Triage]

    TRIAGE --> FP[Fingerprint Check<br/>drop if not in raw set]

    FP --> OUT[Triaged Findings<br/>severity + explanation]

    style SCOPE fill:#e3f2fd,stroke:#1565c0
    style FP fill:#ffcdd2,stroke:#c62828
```

## Quality Agent Detail

```mermaid
flowchart LR
    DIFF[PR Diff] --> FACTS[AST Structural Facts<br/>functions, classes, lengths]
    FACTS --> QUERY[Retrieval Query]
    QUERY --> CHROMA[(ChromaDB<br/>coding standards)]
    CHROMA --> PASSAGES[Retrieved Passages]

    DIFF --> LLM[LLM Review<br/>diff + passages]
    PASSAGES --> LLM

    LLM --> G1[Gate 1: Passage Index<br/>must cite retrieved passage]
    G1 --> G2[Gate 2: Symbol Named<br/>non-empty]
    G2 --> G3[Gate 3: File in PR<br/>changed files only]
    G3 --> G4[Gate 4: Symbol Exists<br/>AST lookup]
    G4 --> G5[Gate 5: Countable Claims<br/>line count, param count]
    G5 --> G6[Gate 6: Naming Claims<br/>snake_case / PascalCase<br/>verified against AST]
    G6 --> OUT[Accepted Findings]

    style G1 fill:#e3f2fd,stroke:#1565c0
    style G2 fill:#e3f2fd,stroke:#1565c0
    style G3 fill:#e3f2fd,stroke:#1565c0
    style G4 fill:#e3f2fd,stroke:#1565c0
    style G5 fill:#e3f2fd,stroke:#1565c0
    style G6 fill:#e3f2fd,stroke:#1565c0
```
