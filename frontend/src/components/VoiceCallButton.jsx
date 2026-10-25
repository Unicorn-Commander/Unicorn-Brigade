/**
 * VoiceCallButton — the phone control in the chat header.
 *
 * An <IconButton> whose accessible name and tooltip say what pressing it does
 * right now: start a call, open the call in progress, or why it can't
 * (the voice service is not available on this server). Probes /voice/health
 * once, passively — a 401 there never redirects the page.
 */
import { useEffect, useState } from 'react';
import { Phone, PhoneCall } from 'lucide-react';
import PropTypes from 'prop-types';
import { apiFetch } from '../services/http';
import { IconButton, Tooltip } from './ui';

const VoiceCallButton = ({ onClick, isConnecting = false, isConnected = false, disabled = false, size = 'md', className = '' }) => {
  const [voiceAvailable, setVoiceAvailable] = useState(null);

  useEffect(() => {
    let cancelled = false;
    apiFetch('/voice/health', { redirectOn401: false })
      .then((r) => !cancelled && setVoiceAvailable(r.ok))
      .catch(() => !cancelled && setVoiceAvailable(false));
    return () => {
      cancelled = true;
    };
  }, []);

  const unavailable = voiceAvailable === false;
  const isDisabled = disabled || unavailable || isConnecting;
  const label = unavailable
    ? 'Voice calls aren’t available on this server'
    : isConnecting
      ? 'Connecting the call…'
      : isConnected
        ? 'In a call — open it'
        : disabled
          ? 'Voice call (wait for the reply to finish)'
          : 'Start a voice call';

  const button = (
    <IconButton
      icon={isConnected ? PhoneCall : Phone}
      label={label}
      tooltip={!isDisabled}
      variant={isConnected ? 'primary' : 'secondary'}
      size={size}
      loading={isConnecting}
      disabled={isDisabled}
      onClick={onClick}
      className={`${isConnected ? 'ring-2 ring-ok/40' : ''} ${className}`}
    />
  );

  // A disabled button swallows pointer events, so the explanation rides on a wrapper.
  return isDisabled ? (
    <Tooltip content={label}>
      <span className="inline-flex" tabIndex={0} aria-label={label}>
        {button}
      </span>
    </Tooltip>
  ) : (
    button
  );
};

VoiceCallButton.propTypes = {
  onClick: PropTypes.func.isRequired,
  isConnecting: PropTypes.bool,
  isConnected: PropTypes.bool,
  disabled: PropTypes.bool,
  size: PropTypes.oneOf(['xs', 'sm', 'md', 'lg']),
  className: PropTypes.string,
};

export default VoiceCallButton;
