/**
 * OIDC callback — lands here after Keycloak. The backend delivers the result
 * one of four ways (cookie + ?login=success, a JWT in the query, a JWT in the
 * fragment, or ?error=…); this page finishes the sign-in and moves on, or
 * says plainly what went wrong and offers to start again.
 */
import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { CheckCircle, LogIn } from 'lucide-react';
import authService from '../services/authService';
import useAuth from '../hooks/useAuth';
import { humanize } from '../utils/errors';
import { Button, ErrorState, LoadingState } from '../components/ui';
import { AuthFrame } from './Login';

const KNOWN = {
  access_denied: 'Sign-in was cancelled or denied by your identity provider.',
  timeout: 'The sign-in took too long to complete.',
  invalid_state: 'That sign-in link has expired.',
  login_required: 'Your session ended before sign-in finished.',
};

export default function AuthCallback() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState('processing'); // processing | success | error
  const [detail, setDetail] = useState(null);

  useEffect(() => {
    const loginStatus = searchParams.get('login');
    const error = searchParams.get('error');
    const queryToken = searchParams.get('access_token');
    const queryExpires = searchParams.get('expires_in');

    // Parse URL fragment (#access_token=... etc)
    const hashParams = new URLSearchParams((window.location.hash || '').replace(/^#/, ''));
    const hashToken = hashParams.get('access_token');
    const hashExpires = hashParams.get('expires_in');

    const token = queryToken || hashToken;
    const expiresIn = queryExpires || hashExpires;

    if (token) {
      authService.setJwt(token, expiresIn);
      // Refresh tokens live only in the backend HttpOnly cookie — never
      // persisted to JS-readable storage.
      // Clear the token from the URL so it does not leak into history / referrers.
      window.history.replaceState({}, document.title, '/auth/callback?login=success');
      useAuth.getState().loadUser();
      setStatus('success');
      const t = setTimeout(() => navigate('/dashboard', { replace: true }), 800);
      return () => clearTimeout(t);
    }

    if (loginStatus === 'success') {
      // Cookie-based session already set by the backend.
      useAuth.getState().loadUser();
      setStatus('success');
      const t = setTimeout(() => navigate('/dashboard', { replace: true }), 800);
      return () => clearTimeout(t);
    }

    if (error) {
      const raw = decodeURIComponent(error);
      setStatus('error');
      setDetail(KNOWN[raw] || humanize({ message: raw }, { what: 'signing in' }));
      return undefined;
    }

    // Still processing: the backend should redirect with ?login=success or ?error=…
    setStatus('processing');
    const timeout = setTimeout(() => {
      setStatus('error');
      setDetail(KNOWN.timeout);
    }, 10000);
    return () => clearTimeout(timeout);
  }, [searchParams, navigate]);

  const retry = () => {
    setStatus('processing');
    setDetail(null);
    authService.login().catch(() => {
      setStatus('error');
      setDetail('Couldn’t reach the sign-in service. Try again in a moment.');
    });
  };

  return (
    <AuthFrame title="Unicorn Brigade" subtitle="The AI Agent Factory">
      {status === 'processing' && (
        <div role="status" aria-live="polite">
          <p className="text-heading text-fg-strong">Signing you in…</p>
          <p className="mt-1 text-body text-muted">Finishing the handshake with your identity provider.</p>
          <div className="mt-4">
            <LoadingState variant="text" count={3} label="Signing you in" />
          </div>
        </div>
      )}
      {status === 'success' && (
        <div role="status" aria-live="polite" className="flex flex-col items-center text-center">
          <span aria-hidden="true" className="flex h-12 w-12 items-center justify-center rounded-pane border border-ok/30 bg-ok/10 text-ok">
            <CheckCircle className="h-6 w-6" />
          </span>
          <p className="mt-3 text-heading text-fg-strong">Signed in</p>
          <p className="mt-1 text-body text-muted">Taking you to the dashboard…</p>
        </div>
      )}
      {status === 'error' && (
        <>
          <ErrorState compact title="Sign-in didn’t complete" detail={detail} onRetry={retry} retryLabel="Try again" />
          <div className="mt-2 flex justify-center">
            <Button variant="link" size="sm" icon={LogIn} onClick={() => navigate('/login', { replace: true })}>
              Back to sign-in
            </Button>
          </div>
        </>
      )}
    </AuthFrame>
  );
}
