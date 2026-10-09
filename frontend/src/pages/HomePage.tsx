import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { safeReturnPath } from '../api/identity';
import { ShieldCheck, FileCheck2, FlaskConical, BookOpen, GitPullRequest, ArrowRight } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/common/Button';
import { GithubIcon } from '../components/common/GithubIcon';

export const HomePage: React.FC = () => {
  const { isAuthenticated, isLoading, busy, authError, refreshSession, loginWithGitHub } = useAuth();
  const location = useLocation();
  const from = location.state?.from;
  const returnTo = safeReturnPath(from ? from.pathname + (from.search || '') + (from.hash || '') : '/repos');
  if (authError) return <div role="alert">{authError} <button onClick={() => void refreshSession()}>Retry sign-in check</button></div>;

  // Redirect to /repos when authenticated
  if (isAuthenticated) {
    return <Navigate to={returnTo} replace />;
  }

  const agents = [
    {
      name: 'Security Agent',
      icon: ShieldCheck,
      color: 'text-primary-400',
      border: 'border-primary-500/30',
      description:
        'Executes Semgrep, Bandit, and Gitleaks deterministic scanners scoped to PR diff hunks. LLM performs fingerprint-locked triage and prioritization without originating findings.',
      tools: ['Semgrep (SAST)', 'Bandit (Python)', 'Gitleaks (Secrets)'],
    },
    {
      name: 'Quality Agent',
      icon: FileCheck2,
      color: 'text-secondary-400',
      border: 'border-secondary-500/30',
      description:
        "Reviews code against retrieved coding standards. Supported measurable rules are verified; other grounded suggestions are clearly labeled advisory.",
      tools: ['ChromaDB RAG', 'AST Gatekeeper', 'Standards Alignment'],
    },
    {
      name: 'Test-Gap Agent',
      icon: FlaskConical,
      color: 'text-tertiary-400',
      border: 'border-tertiary-500/30',
      description:
        'Analyzes changed functions and static test references to identify potential test gaps and draft starter unit tests. This is not execution coverage.',
      tools: ['AST Function Scan', 'Test Discovery', 'Draft Unit Stubs'],
    },
    {
      name: 'Documentation Agent',
      icon: BookOpen,
      color: 'text-neutral-300',
      border: 'border-neutral-700',
      description:
        'Inspects modified definitions for missing or incomplete docstrings, drafting accurate docstring replacements aligned to parameter signatures.',
      tools: ['AST Docstrings', 'Signature Verification', 'Draft Replacements'],
    },
  ];

  return (
    <div className="py-8 space-y-12">
      {/* Hero Section */}
      <section className="text-center max-w-3xl mx-auto space-y-4">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-neutral-900 border border-neutral-800 text-xs font-mono text-neutral-300">
          <span className="w-2 h-2 rounded-full bg-tertiary-500 animate-pulse" />
          <span>Multi-Agent LangGraph Orchestration</span>
        </div>

        <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-neutral-100 font-sans">
          Autonomous DevSecOps Code Reviews for GitHub
        </h1>

        <p className="text-base text-neutral-400 leading-relaxed max-w-2xl mx-auto">
          CodeGuardian AI orchestrates four specialist agents in parallel to review GitHub pull requests, delivering a single severity-ranked PR comment and optional approval-gated auto-fix branch.
        </p>

        <div className="pt-4 flex items-center justify-center gap-3">
          <Button variant="github"
            id="hero-github-signin-btn"
            size="lg"
            disabled={isLoading || busy}
            onClick={() => void loginWithGitHub(returnTo)}
          >
            <GithubIcon className="w-4 h-4" aria-hidden="true" />
            <span>Sign in with GitHub</span>
            <ArrowRight className="w-4 h-4 ml-1" aria-hidden="true" />
          </Button>
        </div>
      </section>

      {/* Specialist Agents Grid */}
      <section aria-labelledby="agents-overview-heading" className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between border-b border-neutral-800 pb-3">
          <div>
            <h2 id="agents-overview-heading" className="text-lg font-semibold text-neutral-100">
              Four Parallel Specialist Agents
            </h2>
            <p className="text-xs text-neutral-400 mt-0.5">
              Deterministic scanners and AST validation feed LLM triage — the model never originates findings.
            </p>
          </div>
          <span className="text-xs font-mono text-neutral-400 mt-2 sm:mt-0">
            Supervisor: LangGraph Aggregator
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {agents.map((agent) => {
            const Icon = agent.icon;
            return (
              <div
                key={agent.name}
                className="bg-neutral-900 border border-neutral-800 rounded-lg p-5 flex flex-col justify-between"
              >
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-md bg-neutral-850 border border-neutral-800 flex items-center justify-center">
                      <Icon className={`w-5 h-5 ${agent.color}`} aria-hidden="true" />
                    </div>
                    <h3 className="text-base font-semibold text-neutral-200">
                      {agent.name}
                    </h3>
                  </div>
                  <p className="text-xs text-neutral-400 leading-relaxed">
                    {agent.description}
                  </p>
                </div>

                <div className="mt-4 pt-3 border-t border-neutral-800/80 flex flex-wrap gap-1.5">
                  {agent.tools.map((tool) => (
                    <span
                      key={tool}
                      className="px-2 py-0.5 rounded-xs bg-neutral-800/80 text-[11px] font-mono text-neutral-300"
                    >
                      {tool}
                    </span>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Architectural Guarantee Section */}
      <section className="bg-neutral-900/60 border border-neutral-800 rounded-lg p-5 space-y-3">
        <div className="flex items-center gap-2">
          <GitPullRequest className="w-4 h-4 text-primary-400" aria-hidden="true" />
          <h2 className="text-sm font-semibold text-neutral-200 uppercase tracking-wider font-mono">
            Human-Gated Auto-Fix Workflow
          </h2>
        </div>
        <p className="text-xs text-neutral-400 leading-relaxed">
          Test-Gap and Documentation agents can generate fixable candidate patches on an isolated branch (<code className="text-primary-300 font-mono">codeguardian/fix-pr-N</code>). Security and Quality findings are advisory and never autofixed. Auto-fix branches never merge automatically and require explicit human approval via the dashboard.
        </p>
      </section>
    </div>
  );
};
