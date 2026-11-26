import { Navigate, useLocation } from 'react-router-dom';
import { ArrowRight, BookOpen, FileCheck2, FlaskConical, ShieldCheck } from 'lucide-react';
import { safeReturnPath } from '../api/identity';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/common/Button';
import { EntryPanel, entryAlert } from '../components/common/EntryPanel';
import { GithubIcon } from '../components/common/GithubIcon';
import { SectionCard } from '../components/common/SectionCard';
import { diagnosticText } from '../components/reviews/diagnosticText';

const specialists = [
  { name: 'Security Agent', icon: ShieldCheck, description: 'Uses recorded scanner results to prioritize security findings in pull request changes.' },
  { name: 'Quality Agent', icon: FileCheck2, description: 'Checks changes against coding standards and distinguishes verified rules from advisory suggestions.' },
  { name: 'Test Gaps Agent', icon: FlaskConical, description: 'Flags potential gaps using changed functions and static test references. Can draft starter tests.' },
  { name: 'Documentation Agent', icon: BookOpen, description: 'Identifies missing or incomplete docstrings and can draft replacements based on function signatures.' },
];

export function HomePage() {
  const { isAuthenticated, isLoading, busy, authError, refreshSession, loginWithGitHub } = useAuth();
  const { state } = useLocation();
  const from = state?.from;
  const returnTo = safeReturnPath(from ? from.pathname + (from.search || '') + (from.hash || '') : '/repos');
  if (authError) return <EntryPanel title="Check your GitHub session">
    <p role="alert" className={entryAlert}>{diagnosticText(authError)}</p>
    <Button variant="secondary" onClick={() => void refreshSession()}>Retry sign-in check</Button>
  </EntryPanel>;
  if (isAuthenticated) return <Navigate to={returnTo} replace />;

  return <div className="space-y-9 py-6 text-fg sm:py-10">
    <section className="grid items-center gap-8 border-b border-divider pb-8 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
      <div className="space-y-4">
        <h1 className="max-w-3xl text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl">Code review for GitHub pull requests</h1>
        <p className="max-w-prose text-body text-fg-secondary">Four specialists review pull request changes. Inspect severity-ranked findings in CodeGuardian and read the combined review comment on GitHub.</p>
        <Button id="hero-github-signin-btn" size="lg" disabled={isLoading || busy} onClick={() => void loginWithGitHub(returnTo)}>
          <GithubIcon aria-hidden="true" className="size-5 shrink-0" />Sign in with GitHub<ArrowRight aria-hidden="true" className="size-4 shrink-0" />
        </Button>
        {isLoading && <p role="status" className="text-support text-fg-muted">Checking your sign-in…</p>}
        {busy && <p role="status" className="text-support text-fg-muted">Opening GitHub sign-in…</p>}
      </div>
      <SectionCard className="space-y-4">
        <h2 className="text-section">From pull request to review</h2>
        <ol className="divide-y divide-divider text-support text-fg-secondary">
          <li className="py-3">Connect the repositories you want to review.</li>
          <li className="py-3">Review eligible changes automatically or start a review manually.</li>
          <li className="py-3">Inspect findings and decide whether to approve a proposed test or documentation fix.</li>
        </ol>
      </SectionCard>
    </section>
    <section aria-labelledby="agents-overview-heading" className="space-y-4">
      <h2 id="agents-overview-heading" className="text-section md:text-section-wide">Specialist agents</h2>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {specialists.map(({ name, icon: Icon, description }) => <SectionCard key={name} className="space-y-2">
          <div className="flex items-start gap-2">
            <Icon aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-link" />
            <h3 className="text-row-title">{name}</h3>
          </div>
          <p className="text-support text-fg-secondary">{description}</p>
        </SectionCard>)}
      </div>
    </section>
  </div>;
}
