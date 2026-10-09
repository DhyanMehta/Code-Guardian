import { Link, useLocation } from 'react-router-dom';
import { Shield, LogOut } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../common/Button';
import { GithubIcon } from '../common/GithubIcon';
export function Navbar() {
  const { user, isLoading, busy, loginWithGitHub, logout, actionError } = useAuth();
  const location = useLocation();
  const from = location.state?.from;
  const returnTo = from ? from.pathname + (from.search || '') + (from.hash || '') : undefined;
  return <header className="sticky top-0 z-40 border-b border-neutral-800 bg-neutral-950/95 backdrop-blur-xs">
    <div className="max-w-7xl mx-auto px-4 sm:px-6 min-h-14 py-3 flex flex-wrap gap-3 items-center justify-between">
      <Link to={user ? '/repos' : '/'} className="flex items-center gap-2 text-sm font-semibold"><Shield className="w-5 h-5 text-primary-400" />CodeGuardian <span className="text-primary-400">AI</span></Link>
      <div className="flex flex-wrap items-center gap-3 text-sm">{user ? <><Link to="/repos">Repositories</Link>{user.avatar_url && <img src={user.avatar_url} alt="" className="w-7 h-7 rounded-full" />}<Link to="/profile" aria-label="Profile settings">{user.github_login}</Link><button aria-label="Sign out" disabled={busy} onClick={() => void logout()}><LogOut className="w-4 h-4" /></button></> : <Button variant="github" size="sm" disabled={isLoading || busy} onClick={() => void loginWithGitHub(returnTo)}><GithubIcon className="w-4 h-4" />Sign in with GitHub</Button>}</div>
    </div>{actionError && <p role="alert" className="max-w-7xl mx-auto px-6 pb-3 text-sm text-severity-medium">{actionError}</p>}
  </header>;
}
