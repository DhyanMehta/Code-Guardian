import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Shield, LogOut, Menu, X, FolderGit2, User } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../common/Button';
import { GithubIcon } from '../common/GithubIcon';

export function Navbar() {
  const { user, isLoading, busy, loginWithGitHub, logout, actionError } = useAuth();
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const from = location.state?.from;
  const returnTo = from ? from.pathname + (from.search || '') + (from.hash || '') : undefined;

  const isReposActive = location.pathname.startsWith('/repos');
  const isProfileActive = location.pathname.startsWith('/profile');

  return (
    <header className="sticky top-0 z-40 border-b border-neutral-800/80 bg-neutral-950/90 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
        {/* Brand Logo */}
        <div className="flex items-center gap-6">
          <Link
            to={user ? '/repos' : '/'}
            className="flex items-center gap-2.5 text-sm font-semibold tracking-tight text-neutral-100 hover:text-white transition-colors group"
          >
            <div className="w-8 h-8 rounded-lg bg-primary-500/10 border border-primary-500/25 flex items-center justify-center group-hover:border-primary-400/50 group-hover:bg-primary-500/15 transition-all duration-150">
              <Shield className="w-4.5 h-4.5 text-primary-400 group-hover:scale-105 transition-transform" />
            </div>
            <span className="font-bold tracking-tight text-base">
              CodeGuardian <span className="text-primary-400 font-mono text-xs px-1.5 py-0.5 rounded bg-primary-500/15 border border-primary-500/30 ml-0.5">AI</span>
            </span>
          </Link>

          {/* Desktop Nav Items */}
          {user && (
            <nav className="hidden md:flex items-center gap-1 pl-4 border-l border-neutral-800">
              <Link
                to="/repos"
                className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-150 ${
                  isReposActive
                    ? 'bg-neutral-800/90 text-primary-300 font-semibold shadow-2xs border border-neutral-700/60'
                    : 'text-neutral-400 hover:text-neutral-100 hover:bg-neutral-850/50'
                }`}
              >
                <FolderGit2 className="w-4 h-4" />
                <span>Repositories</span>
              </Link>
            </nav>
          )}
        </div>

        {/* Right Action / Profile */}
        <div className="flex items-center gap-3">
          {user ? (
            <>
              {/* Desktop User Section */}
              <div className="hidden sm:flex items-center gap-2">
                <Link
                  to="/profile"
                  aria-label="Profile settings"
                  className={`flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-sm border transition-all duration-150 ${
                    isProfileActive
                      ? 'bg-neutral-850 border-primary-500/40 text-neutral-100'
                      : 'bg-neutral-900/80 hover:bg-neutral-850 border-neutral-800 hover:border-neutral-700 text-neutral-300 hover:text-neutral-100'
                  }`}
                >
                  {user.avatar_url ? (
                    <img
                      src={user.avatar_url}
                      alt=""
                      className="w-6 h-6 rounded-full ring-1 ring-neutral-700"
                    />
                  ) : (
                    <User className="w-4 h-4 text-neutral-400" />
                  )}
                  <span className="font-mono text-xs font-medium">{user.github_login}</span>
                </Link>

                <button
                  type="button"
                  aria-label="Sign out"
                  disabled={busy}
                  onClick={() => void logout()}
                  title="Sign out"
                  className="p-2 rounded-lg text-neutral-400 hover:text-severity-critical hover:bg-neutral-900 border border-transparent hover:border-neutral-800 transition-colors disabled:opacity-50 cursor-pointer"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </div>

              {/* Mobile Menu Hamburger */}
              <button
                type="button"
                aria-label={mobileMenuOpen ? 'Close navigation menu' : 'Open navigation menu'}
                onClick={() => setMobileMenuOpen(prev => !prev)}
                className="md:hidden p-2 rounded-lg text-neutral-400 hover:text-neutral-100 hover:bg-neutral-850 transition-colors"
              >
                {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
            </>
          ) : (
            <Button
              variant="github"
              size="sm"
              disabled={isLoading || busy}
              onClick={() => void loginWithGitHub(returnTo)}
            >
              <GithubIcon className="w-4 h-4 shrink-0" />
              <span>Sign in with GitHub</span>
            </Button>
          )}
        </div>
      </div>

      {/* Mobile Drawer */}
      {user && mobileMenuOpen && (
        <div className="md:hidden border-t border-neutral-800 bg-neutral-950 px-4 py-3 space-y-2">
          <Link
            to="/repos"
            onClick={() => setMobileMenuOpen(false)}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium ${
              isReposActive ? 'bg-neutral-850 text-primary-300 font-semibold' : 'text-neutral-300'
            }`}
          >
            <FolderGit2 className="w-4 h-4" />
            <span>Repositories</span>
          </Link>
          <Link
            to="/profile"
            aria-label="Profile settings"
            onClick={() => setMobileMenuOpen(false)}
            className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm ${
              isProfileActive ? 'bg-neutral-850 text-primary-300 font-semibold' : 'text-neutral-300'
            }`}
          >
            {user.avatar_url && (
              <img src={user.avatar_url} alt="" className="w-5 h-5 rounded-full" />
            )}
            <span className="font-mono text-xs">{user.github_login}</span>
          </Link>
          <div className="pt-2 border-t border-neutral-900">
            <button
              type="button"
              aria-label="Sign out"
              disabled={busy}
              onClick={() => {
                setMobileMenuOpen(false);
                void logout();
              }}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-severity-critical hover:bg-neutral-900 transition-colors"
            >
              <LogOut className="w-4 h-4" />
              <span>Sign out</span>
            </button>
          </div>
        </div>
      )}

      {/* Persistent Action Error Banner */}
      {actionError && (
        <div className="bg-severity-medium-bg/50 border-b border-severity-medium-border">
          <p role="alert" className="max-w-7xl mx-auto px-4 sm:px-6 py-2.5 text-sm text-severity-medium flex items-center gap-2">
            <span>⚠</span> {actionError}
          </p>
        </div>
      )}
    </header>
  );
}
