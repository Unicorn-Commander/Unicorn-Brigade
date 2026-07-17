/**
 * VoiceCallButton - Phone icon button to initiate voice calls
 *
 * Features:
 * - Phone icon to initiate call
 * - Disabled state when voice service unavailable
 * - Loading state while connecting
 * - Tooltip with call status
 */

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Phone, PhoneCall, Loader2, PhoneOff } from 'lucide-react';
import PropTypes from 'prop-types';
import { apiFetch } from '../services/http';

const VoiceCallButton = ({
  onClick,
  isConnecting = false,
  isConnected = false,
  disabled = false,
  size = 'md',
  className = ''
}) => {
  const [voiceAvailable, setVoiceAvailable] = useState(null);
  const [showTooltip, setShowTooltip] = useState(false);

  // Check voice service availability on mount
  useEffect(() => {
    const checkAvailability = async () => {
      try {
        // Passive availability probe — never redirect the page on 401, just
        // report the service unavailable.
        const response = await apiFetch('/voice/health', { redirectOn401: false });
        setVoiceAvailable(response.ok);
      } catch {
        setVoiceAvailable(false);
      }
    };

    checkAvailability();
  }, []);

  const isDisabled = disabled || voiceAvailable === false || isConnecting;

  // Size variants
  const sizeClasses = {
    sm: 'w-8 h-8',
    md: 'w-10 h-10',
    lg: 'w-12 h-12'
  };

  const iconSizes = {
    sm: 'w-4 h-4',
    md: 'w-5 h-5',
    lg: 'w-6 h-6'
  };

  // Determine icon and styles based on state
  const getButtonContent = () => {
    if (isConnecting) {
      return (
        <Loader2 className={`${iconSizes[size]} animate-spin`} />
      );
    }

    if (isConnected) {
      return (
        <PhoneCall className={`${iconSizes[size]}`} />
      );
    }

    return (
      <Phone className={`${iconSizes[size]}`} />
    );
  };

  const getButtonStyles = () => {
    if (isConnected) {
      return 'bg-green-500 hover:bg-green-600 text-white shadow-lg shadow-green-500/30';
    }

    if (isConnecting) {
      return 'bg-amber-500 text-white cursor-wait';
    }

    if (isDisabled) {
      return 'bg-slate-700/50 text-slate-400 cursor-not-allowed';
    }

    return 'bg-slate-800/60 hover:bg-unicorn-600 text-slate-300 hover:text-white border border-slate-700/50 hover:border-unicorn-500/50';
  };

  const getTooltipMessage = () => {
    if (voiceAvailable === false) {
      return 'Voice service unavailable';
    }
    if (isConnecting) {
      return 'Connecting...';
    }
    if (isConnected) {
      return 'In call - Click to open';
    }
    return 'Start voice call';
  };

  return (
    <div className="relative">
      <motion.button
        onClick={onClick}
        disabled={isDisabled}
        aria-label={getTooltipMessage()}
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        className={`
          ${sizeClasses[size]}
          ${getButtonStyles()}
          rounded-xl flex items-center justify-center
          transition-all duration-200
          ${className}
        `}
        whileHover={!isDisabled ? { scale: 1.05 } : {}}
        whileTap={!isDisabled ? { scale: 0.95 } : {}}
      >
        {getButtonContent()}

        {/* Pulse animation when connected */}
        {isConnected && (
          <motion.span
            className="absolute inset-0 rounded-xl bg-green-500"
            initial={{ opacity: 0.5, scale: 1 }}
            animate={{ opacity: 0, scale: 1.3 }}
            transition={{ duration: 1.5, repeat: Infinity }}
          />
        )}
      </motion.button>

      {/* Tooltip */}
      {showTooltip && (
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 4 }}
          className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 text-xs text-white bg-slate-800 rounded-md whitespace-nowrap z-50 border border-slate-700/50"
        >
          {getTooltipMessage()}
          <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-1 border-4 border-transparent border-t-slate-800" />
        </motion.div>
      )}
    </div>
  );
};

VoiceCallButton.propTypes = {
  onClick: PropTypes.func.isRequired,
  isConnecting: PropTypes.bool,
  isConnected: PropTypes.bool,
  disabled: PropTypes.bool,
  size: PropTypes.oneOf(['sm', 'md', 'lg']),
  className: PropTypes.string
};

export default VoiceCallButton;
