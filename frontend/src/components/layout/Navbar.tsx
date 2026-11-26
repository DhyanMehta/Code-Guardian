import { useEffect, useId, useRef, useState, type MouseEvent } from 'react';
import { Link, matchPath, useLocation } from 'react-router-dom';
import { ChevronDown, FolderGit2, LogOut, Shield, User } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../common/Button';
import { GithubIcon } from '../common/GithubIcon';
import { diagnosticText } from '../reviews/diagnosticText';

const navLink = 'control-target control-focus flex items-center gap-2 rounded-lg px-3 py-1.5 text-control md:text-control-wide text-fg-secondary hover:bg-panel-raised hover:text-fg [&[aria-current]]:bg-panel-raised [&[aria-current]]:text-link transition-colors';

export function Navbar() {
  const { user, isLoading, busy, loginWithGitHub, logout, actionError } = useAuth();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuId = useId();
  const disclosure = useRef<HTMLDivElement>(null);
  const toggle = useRef<HTMLButtonElement>(null);
  const from = location.state?.from;
  const returnTo = from ? from.pathname + (from.search || '') + (from.hash || '') : undefined;

  const installationId = new URLSearchParams(location.search).get('installation_id');
  const scope = installationId === null ? '' : `?${new URLSearchParams({ installation_id: installationId })}`;
  const reposTo = `/repos${scope}`;
  const profileTo = `/profile${scope}`;
  const reposPage = matchPath('/repos', location.pathname);
  const inRepositories = matchPath('/repos/*', location.pathname) || matchPath('/reviews/:reviewId', location.pathname);
  const reposCurrent = reposPage ? 'page' : inRepositories ? 'location' : undefined;
  const profileCurrent = matchPath('/profile', location.pathname) ? 'page' : undefined;

  useEffect(() => {
    setMenuOpen(false);
  }, [location.key, user?.id]);

  useEffect(() => {
    if (!menuOpen) return;

    function dismissOutside(event: PointerEvent) {
      if (event.target instanceof Node && !disclosure.current?.contains(event.target)) {
        setMenuOpen(false);
      }
    }

    document.addEventListener('pointerdown', dismissOutside);
    return () => document.removeEventListener('pointerdown', dismissOutside);
  }, [menuOpen]);

  function dismissAndReturnFocus() {
    setMenuOpen(false);
    toggle.current?.focus();
  }

  function closeOnNavigation(event: MouseEvent<HTMLAnchorElement>) {
    if (event.button === 0 && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
      dismissAndReturnFocus();
    }
  }

  return (
    <header className="sticky top-0 z-40 border-b border-divider bg-canvas">
      <div className="relative mx-auto flex min-h-14 max-w-7xl items-center gap-2 px-4 py-1 sm:px-6 md:gap-6 lg:min-h-[3.75rem] xl:min-h-16">
        <Link
          to={user ? reposTo : '/'}
          className="control-target control-focus flex shrink-0 items-center gap-2 rounded-lg text-row-title tracking-tight text-fg hover:text-link"
        >
          <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-panel-raised text-link">
            <Shield aria-hidden="true" className="size-[18px]" />
          </span>
          <span className="whitespace-nowrap">CodeGuardian <span className="text-link">AI</span></span>
        </Link>

        {user ? (
          <>
            <nav aria-label="Primary" className="hidden md:block">
              <Link to={reposTo} aria-current={reposCurrent} className={navLink}>Repositories</Link>
            </nav>

            <div
              ref={disclosure}
              className="ml-auto min-w-0"
              onBlur={event => {
                if (menuOpen && event.relatedTarget && !event.currentTarget.contains(event.relatedTarget)) {
                  setMenuOpen(false);
                }
              }}
              onKeyDown={event => {
                if (menuOpen && event.key === 'Escape') {
                  event.preventDefault();
                  event.stopPropagation();
                  dismissAndReturnFocus();
                }
              }}
            >
              <button
                ref={toggle}
                type="button"
                aria-label={`Menu for ${user.github_login}`}
                aria-expanded={menuOpen}
                aria-controls={menuId}
                onClick={() => setMenuOpen(open => !open)}
                className={`control-target control-focus flex w-full cursor-pointer items-center gap-2 rounded-lg border px-2.5 py-1.5 text-control md:text-control-wide text-fg hover:bg-panel-raised transition-colors ${
                  profileCurrent || menuOpen ? 'border-control-border bg-panel-raised' : 'border-divider bg-panel'
                }`}
              >
                {user.avatar_url ? (
                  <img src={user.avatar_url} alt="" className="size-6 shrink-0 rounded-full" />
                ) : (
                  <User aria-hidden="true" className="size-5 shrink-0 text-fg-muted" />
                )}
                <span className="md:hidden">Menu</span>
                <span className="hidden min-w-0 max-w-48 truncate md:inline">{user.github_login}</span>
                <ChevronDown aria-hidden="true" className={`size-4 shrink-0 text-fg-muted ${menuOpen ? 'rotate-180' : ''}`} />
              </button>

              <nav
                id={menuId}
                aria-label="Account navigation"
                hidden={!menuOpen}
                className="absolute inset-x-4 top-full mt-1 max-h-[calc(100dvh-5rem)] overflow-auto rounded-xl border border-divider bg-panel p-2 shadow-xl sm:inset-x-6 md:left-auto md:w-72"
              >
                <p className="border-b border-divider px-3 pt-1.5 pb-2.5 text-meta md:text-meta-wide text-fg-muted">
                  Signed in as <span className="block text-row-title text-fg [overflow-wrap:anywhere]">{user.github_login}</span>
                </p>
                <ul className="mt-1 space-y-1">
                  <li className="md:hidden">
                    <Link to={reposTo} aria-current={reposCurrent} className={navLink} onClick={closeOnNavigation}>
                      <FolderGit2 aria-hidden="true" className="size-4 shrink-0" />
                      Repositories
                    </Link>
                  </li>
                  <li>
                    <Link to={profileTo} aria-current={profileCurrent} className={navLink} onClick={closeOnNavigation}>
                      <User aria-hidden="true" className="size-4 shrink-0" />
                      Profile settings
                    </Link>
                  </li>
                  <li className="border-t border-divider pt-1">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => {
                        dismissAndReturnFocus();
                        void logout();
                      }}
                      className="control-target control-focus flex w-full cursor-pointer items-center gap-2 rounded-lg px-3 py-1.5 text-left text-control md:text-control-wide text-status-failed enabled:hover:bg-action-danger disabled:cursor-not-allowed disabled:opacity-60 transition-colors"
                    >
                      <LogOut aria-hidden="true" className="size-4 shrink-0" />
                      Sign out
                    </button>
                  </li>
                </ul>
              </nav>
            </div>
          </>
        ) : (
          <Button
            variant="secondary"
            size="sm"
            className="ml-auto max-w-40 md:max-w-none"
            disabled={isLoading || busy}
            onClick={() => void loginWithGitHub(returnTo)}
          >
            <GithubIcon className="hidden size-4 shrink-0 min-[360px]:block" />
            <span>Sign in with GitHub</span>
          </Button>
        )}
      </div>

      {actionError && (
        <div className="border-t border-risk-medium/35 bg-risk-medium-bg">
          <p role="alert" className="mx-auto max-w-7xl px-4 py-2 text-support text-risk-medium sm:px-6 [overflow-wrap:anywhere]">
            {diagnosticText(actionError)}
          </p>
        </div>
      )}
    </header>
  );
}
