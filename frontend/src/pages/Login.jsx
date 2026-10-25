/**
 * Sign in — SSO through Keycloak (which fronts Google, GitHub and Microsoft)
 * and, when the deployment allows native accounts, email + password.
 *
 * The providers and URLs are exactly what the page used before: one SSO
 * button that starts GET /auth/oidc/login; the provider marks are
 * informational (Keycloak offers them on its own page).
 */
import { forwardRef, useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Eye, EyeOff, LogIn, Mail, Shield, Sparkles, Users, Zap } from 'lucide-react';
import useAuth from '../hooks/useAuth';
import { BrigadeLogo } from '../components/UnicornBrigadeLogo';
import { apiJson } from '../services/http';
import { humanize } from '../utils/errors';
import { Button, Card, Chip, Field, IconButton, Input, LoadingState, Tabs, Tooltip } from '../components/ui';

const AUTH_TABS = [
  { id: 'sso', label: 'Single sign-on', icon: Users },
  { id: 'email', label: 'Email', icon: Mail },
];

/** Keycloak hands back error codes in the URL; say them in words. */
const URL_ERRORS = {
  access_denied: 'Sign-in was cancelled or denied by your identity provider.',
  timeout: 'The sign-in took too long to complete. Try again.',
  invalid_state: 'That sign-in link has expired. Start again.',
  login_required: 'Your session ended. Sign in again to continue.',
};
function describeUrlError(raw) {
  if (!raw) return null;
  const v = decodeURIComponent(raw);
  return URL_ERRORS[v] || humanize({ message: v }, { what: 'signing in' });
}

function GoogleMark() {
  return (
    <svg aria-hidden="true" className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="currentColor">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
    </svg>
  );
}
function GitHubMark() {
  return (
    <svg aria-hidden="true" className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
    </svg>
  );
}
function MicrosoftMark() {
  return (
    <svg aria-hidden="true" className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="currentColor">
      <path d="M11.4 24H0V8.6h11.4V24zM24 24H12.6V0H24v24z" />
    </svg>
  );
}

/**
 * A password input with a show/hide control. One element, so <Field> can wire
 * its id / aria-describedby / invalid straight onto the real <input>.
 */
export const PasswordInput = forwardRef(function PasswordInput({ className = '', ...props }, ref) {
  const [show, setShow] = useState(false);
  return (
    <div className="relative">
      <Input ref={ref} type={show ? 'text' : 'password'} className={`pr-12 ${className}`} {...props} />
      <span className="absolute right-1.5 top-1/2 -translate-y-1/2">
        <IconButton icon={show ? EyeOff : Eye} label={show ? 'Hide password' : 'Show password'} size="sm" aria-pressed={show} onClick={() => setShow((s) => !s)} />
      </span>
    </div>
  );
});

/** The shared auth frame: wordmark above, card in the middle, company line below. */
export function AuthFrame({ title, subtitle, children, footer }) {
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 flex flex-col items-center text-center">
          <BrigadeLogo size={64} className="shadow-e2" />
          <h1 className="mt-4 text-display">
            <span className="text-gradient">{title}</span>
          </h1>
          {subtitle && <p className="mt-1 text-body text-muted">{subtitle}</p>}
        </div>
        <Card padding="lg" className="shadow-e3">
          {children}
        </Card>
        {footer}
        <div className="mt-6 space-y-1 text-center text-caption text-muted">
          <p>
            Part of the <span className="font-medium text-fg">Unicorn Commander</span> ecosystem · sign-in by Keycloak
          </p>
          <p>
            Magic Unicorn Unconventional Technology &amp; Stuff Inc ·{' '}
            <a href="https://unicorncommander.com" target="_blank" rel="noopener noreferrer" className="text-accent underline-offset-4 hover:underline">
              unicorncommander.com
            </a>
          </p>
        </div>
      </div>
    </main>
  );
}

export function AuthAlert({ title, message }) {
  if (!message) return null;
  return (
    <div role="alert" className="mb-5 flex items-start gap-3 rounded-control border border-danger/30 bg-danger/10 p-3">
      <Shield aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-danger" />
      <div className="min-w-0">
        <p className="text-body-sm font-semibold text-fg-strong">{title}</p>
        <p className="mt-0.5 text-body-sm text-muted">{message}</p>
      </div>
    </div>
  );
}

export const FEATURES = [
  { icon: Sparkles, text: 'Build custom agents in conversation with Gunny' },
  { icon: Zap, text: 'Connect MCP servers and 20+ built-in tools' },
  { icon: Shield, text: 'Enterprise sign-in and per-organization isolation' },
];

export function FeatureList() {
  return (
    <ul className="mt-5 space-y-2 border-t border-border pt-5">
      {FEATURES.map((f) => (
        <li key={f.text} className="flex items-center gap-2.5 text-body-sm text-muted">
          <f.icon aria-hidden="true" className="h-4 w-4 shrink-0 text-accent" />
          {f.text}
        </li>
      ))}
    </ul>
  );
}

export default function Login() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { login, loginWithPassword, isAuthenticated, isLoading, error, clearError } = useAuth();

  const urlError = searchParams.get('error');
  const [tab, setTab] = useState('sso');
  const [form, setForm] = useState({ email: '', password: '' });
  const [fieldErrors, setFieldErrors] = useState({});
  const [formError, setFormError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [ssoBusy, setSsoBusy] = useState(false);
  // Deployment auth flags — when native register is disabled (SSO-managed),
  // the email tab and register links are hidden in favour of SSO.
  const [authConfig, setAuthConfig] = useState(null);
  const nativeAuthHidden = authConfig ? authConfig.native_register_enabled === false : false;

  useEffect(() => {
    if (isAuthenticated && !isLoading) navigate('/dashboard');
  }, [isAuthenticated, isLoading, navigate]);

  useEffect(() => {
    let cancelled = false;
    apiJson('/auth/config', { redirectOn401: false })
      .then((config) => {
        if (!cancelled) setAuthConfig(config);
      })
      .catch(() => {
        /* config unavailable — keep both tabs visible */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (nativeAuthHidden && tab === 'email') setTab('sso');
  }, [nativeAuthHidden, tab]);

  useEffect(() => {
    setFormError(null);
    setFieldErrors({});
    clearError();
  }, [tab, clearError]);

  const startSSO = async () => {
    setSsoBusy(true);
    try {
      await login(); // navigates away to /auth/oidc/login
    } catch {
      setSsoBusy(false);
    }
  };

  const onChange = (e) => {
    const { name, value } = e.target;
    setForm((f) => ({ ...f, [name]: value }));
    if (fieldErrors[name]) setFieldErrors((fe) => ({ ...fe, [name]: null }));
    if (formError) setFormError(null);
  };

  const submitEmail = async (e) => {
    e.preventDefault();
    const errs = {};
    if (!form.email.trim()) errs.email = 'Enter your email address.';
    if (!form.password) errs.password = 'Enter your password.';
    if (Object.keys(errs).length) {
      setFieldErrors(errs);
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      await loginWithPassword(form.email.trim(), form.password);
      navigate('/dashboard');
    } catch (err) {
      const status = err?.status ?? err?.response?.status;
      setFormError(status === 401 || status === 400 ? 'That email and password don’t match. Check both and try again.' : humanize(err, { what: 'signing in' }));
    } finally {
      setSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <AuthFrame title="Unicorn Brigade" subtitle="The AI Agent Factory">
        <p className="mb-3 text-body font-semibold text-fg-strong">Checking your session…</p>
        <LoadingState variant="text" count={3} label="Checking your session" />
      </AuthFrame>
    );
  }

  const alertMessage = formError || (error ? humanize({ message: error }, { what: 'signing in' }) : null) || describeUrlError(urlError);

  return (
    <AuthFrame title="Unicorn Brigade" subtitle="The AI Agent Factory" footer={null}>
      {!nativeAuthHidden && <Tabs variant="segmented" label="Sign-in method" idBase="auth-tab" tabs={AUTH_TABS} value={tab} onChange={setTab} className="mb-5 justify-center" />}

      <AuthAlert title="Couldn’t sign you in" message={alertMessage} />

      {tab === 'sso' && (
        <div role="tabpanel" aria-labelledby="auth-tab-sso">
          <Button size="lg" className="w-full" icon={LogIn} loading={ssoBusy} onClick={startSSO}>
            Continue with single sign-on
          </Button>
          <div className="mt-4 flex flex-wrap items-center justify-center gap-1.5">
            <span className="text-caption text-muted">Through Keycloak:</span>
            <Chip size="sm" icon={GoogleMark}>
              Google
            </Chip>
            <Chip size="sm" icon={GitHubMark}>
              GitHub
            </Chip>
            <Chip size="sm" icon={MicrosoftMark}>
              Microsoft
            </Chip>
          </div>
          {!nativeAuthHidden && (
            <p className="mt-5 text-center text-body-sm text-muted">
              New here?{' '}
              <Link to="/register" className="font-medium text-accent underline-offset-4 hover:underline">
                Create an account
              </Link>
            </p>
          )}
        </div>
      )}

      {tab === 'email' && !nativeAuthHidden && (
        <form onSubmit={submitEmail} className="space-y-4" role="tabpanel" aria-labelledby="auth-tab-email" noValidate>
          <Field label="Email" error={fieldErrors.email} htmlFor="login-email">
            <Input type="email" name="email" value={form.email} onChange={onChange} placeholder="you@example.com" autoComplete="email" disabled={submitting} size="lg" />
          </Field>
          <Field label="Password" error={fieldErrors.password} htmlFor="login-password">
            <PasswordInput name="password" value={form.password} onChange={onChange} placeholder="Your password" autoComplete="current-password" disabled={submitting} size="lg" />
          </Field>
          <div className="flex items-center justify-end">
            <Tooltip content="Password resets happen on your identity provider’s sign-in page">
              <Button type="button" variant="link" size="sm" onClick={startSSO}>
                Forgot your password?
              </Button>
            </Tooltip>
          </div>
          <Button type="submit" size="lg" className="w-full" icon={LogIn} loading={submitting}>
            Sign in
          </Button>
          <p className="text-center text-body-sm text-muted">
            New here?{' '}
            <Link to="/register" className="font-medium text-accent underline-offset-4 hover:underline">
              Create an account
            </Link>
          </p>
        </form>
      )}

      <FeatureList />
    </AuthFrame>
  );
}
