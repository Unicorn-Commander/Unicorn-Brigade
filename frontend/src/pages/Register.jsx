/**
 * Create an account — native email + password registration. When the
 * deployment is SSO-managed (native_register_enabled = false) the form is
 * replaced by a pointer to single sign-on; the backend enforces the same gate
 * with a 403.
 */
import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Check, CheckCircle, LogIn, Shield, UserPlus } from 'lucide-react';
import useAuth from '../hooks/useAuth';
import { apiJson } from '../services/http';
import { humanize } from '../utils/errors';
import { Button, Field, Input, LoadingState } from '../components/ui';
import { AuthAlert, AuthFrame, FeatureList, PasswordInput } from './Login';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function passwordProblems(password) {
  const out = [];
  if (password.length < 8) out.push('at least 8 characters');
  if (!/[a-zA-Z]/.test(password)) out.push('a letter');
  if (!/[0-9]/.test(password)) out.push('a number');
  return out;
}

function strengthOf(password) {
  if (!password) return { score: 0, label: '' };
  let score = 0;
  if (password.length >= 8) score += 1;
  if (password.length >= 12) score += 1;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score += 1;
  if (/[0-9]/.test(password)) score += 1;
  if (/[^a-zA-Z0-9]/.test(password)) score += 1;
  const labels = ['', 'Weak', 'Fair', 'Good', 'Strong', 'Very strong'];
  const fills = ['', 'bg-danger-fill', 'bg-warn-fill', 'bg-warn-fill', 'bg-ok-fill', 'bg-ok-fill'];
  return { score, label: labels[score], fill: fills[score] };
}

export default function Register() {
  const navigate = useNavigate();
  const { register, login, isAuthenticated, isLoading, error, clearError } = useAuth();

  const [form, setForm] = useState({ name: '', email: '', password: '', confirmPassword: '' });
  const [fieldErrors, setFieldErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [ssoBusy, setSsoBusy] = useState(false);
  const [success, setSuccess] = useState(false);
  const [authConfig, setAuthConfig] = useState(null);
  const registerDisabled = authConfig ? authConfig.native_register_enabled === false : false;

  useEffect(() => {
    if (isAuthenticated && !isLoading) navigate('/dashboard');
  }, [isAuthenticated, isLoading, navigate]);

  useEffect(() => {
    clearError();
  }, [clearError]);

  useEffect(() => {
    let cancelled = false;
    apiJson('/auth/config', { redirectOn401: false })
      .then((config) => {
        if (!cancelled) setAuthConfig(config);
      })
      .catch(() => {
        /* config unavailable — leave the form visible; the backend still gates with a 403 */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const startSSO = async () => {
    setSsoBusy(true);
    try {
      await login();
    } catch {
      setSsoBusy(false);
    }
  };

  const onChange = (e) => {
    const { name, value } = e.target;
    setForm((f) => ({ ...f, [name]: value }));
    if (fieldErrors[name]) setFieldErrors((fe) => ({ ...fe, [name]: null }));
  };

  const validate = () => {
    const errs = {};
    if (!form.name.trim()) errs.name = 'Enter your name.';
    if (!form.email.trim()) errs.email = 'Enter your email address.';
    else if (!EMAIL_RE.test(form.email)) errs.email = 'That doesn’t look like an email address.';
    const problems = passwordProblems(form.password);
    if (problems.length) errs.password = `Use ${problems.join(', ')}.`;
    if (form.password !== form.confirmPassword) errs.confirmPassword = 'The passwords don’t match.';
    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!validate()) return;
    setSubmitting(true);
    clearError();
    try {
      await register(form.email.trim(), form.password, form.name.trim());
      setSuccess(true);
      setTimeout(() => navigate('/dashboard'), 1500);
    } catch {
      /* useAuth stores the error; shown below */
    } finally {
      setSubmitting(false);
    }
  };

  const strength = strengthOf(form.password);
  const matches = form.confirmPassword && form.password === form.confirmPassword && !fieldErrors.confirmPassword;

  if (success) {
    return (
      <AuthFrame title="Unicorn Brigade" subtitle="The AI Agent Factory">
        <div className="flex flex-col items-center text-center">
          <span aria-hidden="true" className="flex h-12 w-12 items-center justify-center rounded-pane border border-ok/30 bg-ok/10 text-ok">
            <CheckCircle className="h-6 w-6" />
          </span>
          <p className="mt-3 text-heading text-fg-strong">Account created</p>
          <p className="mt-1 text-body text-muted">Taking you to the dashboard…</p>
          <div className="mt-4 w-full">
            <LoadingState variant="text" count={2} label="Opening the dashboard" />
          </div>
        </div>
      </AuthFrame>
    );
  }

  return (
    <AuthFrame title={registerDisabled ? 'Unicorn Brigade' : 'Join Unicorn Brigade'} subtitle={registerDisabled ? 'Sign in with your organization account' : 'Create your account to get started'}>
      {registerDisabled ? (
        <div className="space-y-5">
          <div className="flex items-start gap-3 rounded-control border border-accent/25 bg-accent/10 p-3">
            <Shield aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
            <div>
              <p className="text-body-sm font-semibold text-fg-strong">Accounts are managed by your organization’s single sign-on</p>
              <p className="mt-0.5 text-body-sm text-muted">Sign in with your organization account and a Brigade profile is provisioned for you automatically.</p>
            </div>
          </div>
          <Button size="lg" className="w-full" icon={LogIn} loading={ssoBusy} onClick={startSSO}>
            Continue with single sign-on
          </Button>
        </div>
      ) : (
        <>
          <AuthAlert title="Couldn’t create your account" message={error ? humanize({ message: error }, { what: 'creating your account' }) : null} />
          <form onSubmit={submit} className="space-y-4" noValidate>
            <Field label="Full name" error={fieldErrors.name} htmlFor="reg-name">
              <Input name="name" value={form.name} onChange={onChange} placeholder="Your name" autoComplete="name" disabled={submitting} size="lg" />
            </Field>
            <Field label="Email" error={fieldErrors.email} htmlFor="reg-email">
              <Input type="email" name="email" value={form.email} onChange={onChange} placeholder="you@example.com" autoComplete="email" disabled={submitting} size="lg" />
            </Field>
            <Field label="Password" help={!fieldErrors.password && !form.password ? 'At least 8 characters, with a letter and a number.' : undefined} error={fieldErrors.password} htmlFor="reg-password">
              <PasswordInput name="password" value={form.password} onChange={onChange} placeholder="Choose a password" autoComplete="new-password" disabled={submitting} size="lg" />
            </Field>
            {form.password && (
              <div className="-mt-1 flex items-center gap-2" aria-live="polite">
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-elevated" role="meter" aria-valuemin={0} aria-valuemax={5} aria-valuenow={strength.score} aria-label="Password strength">
                  <div className={`h-full ${strength.fill} transition-[width] duration-base ease-standard`} style={{ width: `${(strength.score / 5) * 100}%` }} />
                </div>
                <span className="text-caption text-muted">{strength.label}</span>
              </div>
            )}
            <Field label="Confirm password" error={fieldErrors.confirmPassword} htmlFor="reg-confirm">
              <PasswordInput name="confirmPassword" value={form.confirmPassword} onChange={onChange} placeholder="Type it again" autoComplete="new-password" disabled={submitting} size="lg" />
            </Field>
            {matches && (
              <p className="-mt-2 inline-flex items-center gap-1 text-caption text-ok">
                <Check aria-hidden="true" className="h-3.5 w-3.5" />
                Passwords match
              </p>
            )}
            <Button type="submit" size="lg" className="w-full" icon={UserPlus} loading={submitting || isLoading}>
              Create account
            </Button>
          </form>
        </>
      )}

      <p className="mt-5 text-center text-body-sm text-muted">
        Already have an account?{' '}
        <Link to="/login" className="font-medium text-accent underline-offset-4 hover:underline">
          Sign in
        </Link>
      </p>

      <FeatureList />
    </AuthFrame>
  );
}
