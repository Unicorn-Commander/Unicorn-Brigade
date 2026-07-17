/**
 * Notification helper that honors the user's "Notifications" preference.
 *
 * Success/info toasts are suppressed when the preference is off — so the
 * Settings toggle controls something real. Errors are ALWAYS shown (a failure
 * the user can't see is worse than an unwanted toast), matching the rule that
 * we never hide problems.
 *
 * Drop-in for the react-hot-toast surface used across the app; extend adoption
 * to remaining `toast.*` call sites in a later pass.
 */

import { toast } from 'react-hot-toast';
import { getPreferences } from './preferences';

function notificationsEnabled() {
  return getPreferences().notifications !== false;
}

export const notify = {
  success: (message, opts) => (notificationsEnabled() ? toast.success(message, opts) : undefined),
  info: (message, opts) => (notificationsEnabled() ? toast(message, opts) : undefined),
  // Errors always surface, regardless of the preference.
  error: (message, opts) => toast.error(message, opts),
  loading: (message, opts) => toast.loading(message, opts),
  dismiss: (id) => toast.dismiss(id),
};

export default notify;
