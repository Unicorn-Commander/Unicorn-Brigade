/**
 * VoiceCallModal - Full-featured voice call interface modal
 *
 * Features:
 * - Agent avatar with pulse animation when speaking
 * - Call controls: mute/unmute, end call
 * - Visual audio level indicators
 * - Connection status display
 * - Call duration timer
 * - Gradient background with smooth transitions
 * - Audio device selection
 */

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X,
  Mic,
  MicOff,
  Phone,
  PhoneOff,
  Volume2,
  Settings,
  ChevronDown,
  Loader2,
  AlertCircle,
  Wifi,
  WifiOff
} from 'lucide-react';
import PropTypes from 'prop-types';
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useConnectionState,
  useTracks,
  useParticipants
} from '@livekit/components-react';
import { Track, ConnectionState } from 'livekit-client';
import useVoiceCall, { CallState } from '../hooks/useVoiceCall';

// Audio level visualizer component
const AudioVisualizer = ({ level = 0, isActive = false, size = 'md' }) => {
  const bars = size === 'lg' ? 5 : 3;

  return (
    <div className="flex items-end justify-center space-x-1">
      {[...Array(bars)].map((_, i) => {
        const barHeight = isActive
          ? Math.min(100, Math.max(20, level * 100 + Math.random() * 20))
          : 20;
        const delay = i * 0.1;

        return (
          <motion.div
            key={i}
            className={`rounded-full ${isActive ? 'bg-green-400' : 'bg-slate-600'}`}
            style={{
              width: size === 'lg' ? 4 : 3,
              minHeight: size === 'lg' ? 8 : 6
            }}
            animate={{
              height: isActive ? `${barHeight * (size === 'lg' ? 0.4 : 0.3)}px` : '8px'
            }}
            transition={{
              duration: 0.15,
              delay,
              ease: 'easeOut'
            }}
          />
        );
      })}
    </div>
  );
};

// Connection status badge
const ConnectionBadge = ({ state }) => {
  const getStateConfig = () => {
    switch (state) {
      case CallState.CONNECTING:
        return {
          label: 'Connecting',
          color: 'text-amber-400',
          bg: 'bg-amber-400/10',
          icon: <Loader2 className="w-3 h-3 animate-spin" />
        };
      case CallState.CONNECTED:
        return {
          label: 'Connected',
          color: 'text-green-400',
          bg: 'bg-green-400/10',
          icon: <Wifi className="w-3 h-3" />
        };
      case CallState.RECONNECTING:
        return {
          label: 'Reconnecting',
          color: 'text-amber-400',
          bg: 'bg-amber-400/10',
          icon: <Loader2 className="w-3 h-3 animate-spin" />
        };
      case CallState.ERROR:
        return {
          label: 'Connection Error',
          color: 'text-red-400',
          bg: 'bg-red-400/10',
          icon: <AlertCircle className="w-3 h-3" />
        };
      default:
        return {
          label: 'Disconnected',
          color: 'text-slate-400',
          bg: 'bg-slate-400/10',
          icon: <WifiOff className="w-3 h-3" />
        };
    }
  };

  const config = getStateConfig();

  return (
    <div className={`flex items-center space-x-1.5 px-2 py-1 rounded-full ${config.bg}`}>
      <span className={config.color}>{config.icon}</span>
      <span className={`text-xs font-medium ${config.color}`}>{config.label}</span>
    </div>
  );
};

// Main modal component
const VoiceCallModal = ({
  isOpen,
  onClose,
  agent,
  onCallStart,
  onCallEnd
}) => {
  const [showSettings, setShowSettings] = useState(false);

  const {
    callState,
    error,
    isMuted,
    isAgentSpeaking,
    localAudioLevel,
    remoteAudioLevel,
    formattedDuration,
    audioDevices,
    selectedAudioDevice,
    serverUrl,
    token,
    startCall,
    endCall,
    toggleMute,
    changeAudioDevice,
    isConnecting,
    isConnected,
    isIdle,
    hasError
  } = useVoiceCall({
    agentId: agent?.id,
    agentName: agent?.displayName || agent?.name,
    onAgentSpeaking: () => console.log('Agent speaking'),
    onAgentListening: () => console.log('Agent listening')
  });

  // Auto-start call when modal opens
  useEffect(() => {
    if (isOpen && isIdle && agent) {
      startCall();
      onCallStart?.();
    }
  }, [isOpen, isIdle, agent, startCall, onCallStart]);

  // Handle close
  const handleClose = useCallback(() => {
    if (isConnected || isConnecting) {
      endCall();
      onCallEnd?.();
    }
    onClose();
  }, [isConnected, isConnecting, endCall, onCallEnd, onClose]);

  // Handle end call button
  const handleEndCall = useCallback(() => {
    endCall();
    onCallEnd?.();
    onClose();
  }, [endCall, onCallEnd, onClose]);

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
      >
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="absolute inset-0 bg-black/80 backdrop-blur-sm"
          onClick={handleClose}
        />

        {/* Modal */}
        <motion.div
          initial={{ opacity: 0, scale: 0.9, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.9, y: 20 }}
          transition={{ type: 'spring', damping: 25, stiffness: 300 }}
          className="relative w-full max-w-sm rounded-3xl overflow-hidden"
        >
          {/* Background gradient */}
          <div className="absolute inset-0 bg-gradient-to-br from-slate-900 via-unicorn-900/30 to-slate-900" />
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(139,92,246,0.15),transparent_50%)]" />

          {/* Content */}
          <div className="relative p-6">
            {/* Header */}
            <div className="flex items-center justify-between mb-8">
              <ConnectionBadge state={callState} />
              <button
                onClick={handleClose}
                className="p-2 rounded-full hover:bg-white/10 transition-colors"
              >
                <X className="w-5 h-5 text-slate-400" />
              </button>
            </div>

            {/* Agent Avatar */}
            <div className="flex flex-col items-center mb-8">
              {/* Avatar with pulse animation */}
              <div className="relative mb-4">
                {/* Pulse rings when agent is speaking */}
                {isAgentSpeaking && (
                  <>
                    <motion.div
                      className="absolute inset-0 rounded-full bg-unicorn-500/30"
                      initial={{ scale: 1, opacity: 0.5 }}
                      animate={{ scale: 1.5, opacity: 0 }}
                      transition={{ duration: 1.5, repeat: Infinity }}
                    />
                    <motion.div
                      className="absolute inset-0 rounded-full bg-unicorn-500/20"
                      initial={{ scale: 1, opacity: 0.5 }}
                      animate={{ scale: 1.8, opacity: 0 }}
                      transition={{ duration: 1.5, repeat: Infinity, delay: 0.3 }}
                    />
                  </>
                )}

                {/* Avatar container */}
                <motion.div
                  className={`
                    w-28 h-28 rounded-full flex items-center justify-center
                    bg-gradient-to-br from-unicorn-600 to-unicorn-500
                    shadow-xl shadow-unicorn-500/25
                    ${isAgentSpeaking ? 'ring-4 ring-unicorn-400/50' : ''}
                  `}
                  animate={isAgentSpeaking ? { scale: [1, 1.05, 1] } : {}}
                  transition={{ duration: 0.5, repeat: isAgentSpeaking ? Infinity : 0 }}
                >
                  <span className="text-5xl">{agent?.avatar || '🦄'}</span>
                </motion.div>

                {/* Speaking indicator */}
                {isConnected && (
                  <div className="absolute -bottom-1 left-1/2 -translate-x-1/2">
                    <AudioVisualizer
                      level={remoteAudioLevel}
                      isActive={isAgentSpeaking}
                      size="lg"
                    />
                  </div>
                )}
              </div>

              {/* Agent name */}
              <h2 className="text-xl font-semibold text-white mb-1">
                {agent?.displayName || agent?.name || 'Agent'}
              </h2>
              <p className="text-sm text-slate-400">
                {agent?.title || agent?.domain || 'AI Assistant'}
              </p>

              {/* Call duration */}
              {isConnected && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="mt-3 px-3 py-1 rounded-full bg-white/5 text-slate-300 text-sm font-mono"
                >
                  {formattedDuration}
                </motion.div>
              )}

              {/* Status text */}
              {isConnecting && (
                <motion.p
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="mt-3 text-sm text-slate-400"
                >
                  Connecting to {agent?.displayName || 'agent'}...
                </motion.p>
              )}

              {hasError && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="mt-3 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/20"
                >
                  <p className="text-sm text-red-400">{error || 'Connection failed'}</p>
                </motion.div>
              )}
            </div>

            {/* LiveKit Room (for audio rendering) */}
            {isConnected && serverUrl && token && (
              <LiveKitRoom
                serverUrl={serverUrl}
                token={token}
                connect={true}
                audio={true}
                video={false}
              >
                <RoomAudioRenderer />
              </LiveKitRoom>
            )}

            {/* Controls */}
            <div className="flex items-center justify-center space-x-4">
              {/* Mute button */}
              <motion.button
                onClick={toggleMute}
                disabled={!isConnected}
                className={`
                  w-14 h-14 rounded-full flex items-center justify-center
                  transition-all duration-200
                  ${isMuted
                    ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                    : 'bg-white/10 text-white hover:bg-white/20 border border-white/10'
                  }
                  disabled:opacity-40 disabled:cursor-not-allowed
                `}
                whileHover={isConnected ? { scale: 1.05 } : {}}
                whileTap={isConnected ? { scale: 0.95 } : {}}
              >
                {isMuted ? (
                  <MicOff className="w-6 h-6" />
                ) : (
                  <Mic className="w-6 h-6" />
                )}
              </motion.button>

              {/* End call button */}
              <motion.button
                onClick={handleEndCall}
                className="w-16 h-16 rounded-full bg-red-500 hover:bg-red-600 text-white flex items-center justify-center shadow-lg shadow-red-500/30 transition-colors"
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
              >
                <PhoneOff className="w-7 h-7" />
              </motion.button>

              {/* Settings button */}
              <motion.button
                onClick={() => setShowSettings(!showSettings)}
                className={`
                  w-14 h-14 rounded-full flex items-center justify-center
                  bg-white/10 text-white hover:bg-white/20 border border-white/10
                  transition-all duration-200
                  ${showSettings ? 'bg-white/20' : ''}
                `}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
              >
                <Settings className="w-6 h-6" />
              </motion.button>
            </div>

            {/* Local audio indicator */}
            {isConnected && !isMuted && (
              <div className="flex items-center justify-center mt-4 space-x-2">
                <Volume2 className="w-4 h-4 text-slate-500" />
                <AudioVisualizer level={localAudioLevel} isActive={!isMuted} />
                <span className="text-xs text-slate-500">Your microphone</span>
              </div>
            )}

            {/* Settings panel */}
            <AnimatePresence>
              {showSettings && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="mt-6 overflow-hidden"
                >
                  <div className="p-4 rounded-xl bg-white/5 border border-white/10">
                    <p className="text-xs text-slate-400 uppercase tracking-wider mb-3">
                      Audio Device
                    </p>

                    <div className="relative">
                      <select
                        value={selectedAudioDevice || ''}
                        onChange={(e) => changeAudioDevice(e.target.value)}
                        className="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-sm text-white appearance-none cursor-pointer focus:outline-none focus:border-unicorn-500"
                      >
                        {audioDevices.map((device) => (
                          <option key={device.deviceId} value={device.deviceId}>
                            {device.label || `Microphone ${device.deviceId.slice(0, 8)}`}
                          </option>
                        ))}
                      </select>
                      <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};

VoiceCallModal.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  agent: PropTypes.shape({
    id: PropTypes.string.isRequired,
    name: PropTypes.string,
    displayName: PropTypes.string,
    avatar: PropTypes.string,
    title: PropTypes.string,
    domain: PropTypes.string
  }),
  onCallStart: PropTypes.func,
  onCallEnd: PropTypes.func
};

export default VoiceCallModal;
