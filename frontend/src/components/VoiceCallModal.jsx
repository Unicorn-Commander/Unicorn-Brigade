/**
 * VoiceCallModal — a voice call with one agent, on the shared <Modal>.
 *
 * States, on the status vocabulary: connecting (warn, pulsing) · live (live
 * dot + duration) · reconnecting · failed (an <ErrorState> with the reason in
 * human words and Try again) · ended. The agent's real portrait is the face
 * of the call and pulses while the agent speaks. Controls are 44px: mute
 * (aria-pressed), end call, microphone settings.
 */
import { useCallback, useEffect, useState } from 'react';
import { Mic, MicOff, PhoneOff, Settings2, Volume2 } from 'lucide-react';
import PropTypes from 'prop-types';
import { LiveKitRoom, RoomAudioRenderer } from '@livekit/components-react';
import useVoiceCall, { CallState } from '../hooks/useVoiceCall';
import AgentAvatar from './AgentAvatar';
import { roleLine } from '../utils/agentClass';
import { Button, Chip, ErrorState, Field, IconButton, Modal, Select } from './ui';

const CALL_CHIP = {
  [CallState.CONNECTING]: { tone: 'warn', label: 'Connecting…', pulse: true },
  [CallState.CONNECTED]: { tone: 'live', label: 'Live', pulse: true },
  [CallState.RECONNECTING]: { tone: 'warn', label: 'Reconnecting…', pulse: true },
  [CallState.DISCONNECTING]: { tone: 'neutral', label: 'Ending…', pulse: false },
  [CallState.ERROR]: { tone: 'danger', label: 'Failed', pulse: false },
};
const chipFor = (state) => CALL_CHIP[state] || { tone: 'neutral', label: 'Not connected', pulse: false };

// Level bars: animate while the source is active, rest at a floor when not.
function AudioBars({ active, count = 5 }) {
  return (
    <span aria-hidden="true" className="flex h-6 items-end gap-0.5">
      {Array.from({ length: count }).map((_, i) => (
        <span
          key={i}
          style={{ animationDelay: `${i * 90}ms` }}
          className={`w-1 rounded-full ${active ? 'animate-audio-bar bg-ok' : 'h-2 bg-border-strong'}`}
        />
      ))}
    </span>
  );
}

const VoiceCallModal = ({ isOpen, onClose, agent, onCallStart, onCallEnd }) => {
  const [showSettings, setShowSettings] = useState(false);
  const {
    callState,
    error: failure,
    isMuted,
    isAgentSpeaking,
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
    hasError,
  } = useVoiceCall({ agentId: agent?.id, agentName: agent?.displayName || agent?.name });

  // Dial as soon as the dialog opens.
  useEffect(() => {
    if (isOpen && isIdle && agent) {
      startCall();
      onCallStart?.();
    }
  }, [isOpen, isIdle, agent, startCall, onCallStart]);

  const hangUp = useCallback(() => {
    if (isConnected || isConnecting) {
      endCall();
      onCallEnd?.();
    }
    onClose();
  }, [isConnected, isConnecting, endCall, onCallEnd, onClose]);

  const endAndClose = useCallback(() => {
    endCall();
    onCallEnd?.();
    onClose();
  }, [endCall, onCallEnd, onClose]);

  if (!isOpen) return null;

  const name = agent?.displayName || agent?.name || 'Agent';
  const chip = chipFor(callState);
  const speaking = isConnected && isAgentSpeaking;

  return (
    <Modal isOpen onClose={hangUp} size="sm" title={`Voice call · ${name}`} description={roleLine(agent)}>
      <div className="flex flex-col items-center text-center">
        <div className="relative mb-4 mt-2">
          {speaking && (
            <>
              <span aria-hidden="true" className="absolute inset-0 rounded-full bg-ok/30 animate-pulse-ring" />
              <span aria-hidden="true" className="absolute inset-0 rounded-full bg-ok/20 animate-pulse-ring-delayed" />
            </>
          )}
          <AgentAvatar
            agent={agent}
            size={112}
            rounded="rounded-full"
            status={isConnected ? 'responding' : hasError ? 'error' : 'idle'}
            className={`relative shadow-e3 ${speaking ? 'ring-4 ring-ok/50' : ''}`}
          />
        </div>

        <Chip tone={chip.tone} dot pulse={chip.pulse} size="md">
          {chip.label}
          {isConnected && <span className="font-mono tabular-nums">· {formattedDuration}</span>}
        </Chip>

        {isConnecting && <p className="mt-3 text-body-sm text-muted">Setting up the room and your microphone…</p>}

        {isConnected && (
          <div className="mt-4 flex items-center gap-2 text-caption text-muted" role="status">
            <Volume2 aria-hidden="true" className="h-4 w-4" />
            <AudioBars active={speaking} />
            <span>{speaking ? `${name} is speaking` : 'Listening'}</span>
          </div>
        )}

        {hasError && (
          <div className="mt-4 w-full rounded-card border border-danger/30 bg-danger/5">
            <ErrorState compact title="The call couldn’t connect" detail={failure} onRetry={startCall} retryLabel="Try again" />
          </div>
        )}

        {isConnected && serverUrl && token && (
          <LiveKitRoom serverUrl={serverUrl} token={token} connect audio video={false}>
            <RoomAudioRenderer />
          </LiveKitRoom>
        )}

        {/* Controls */}
        <div className="mt-6 flex items-center justify-center gap-3">
          <IconButton
            icon={isMuted ? MicOff : Mic}
            label={isMuted ? 'Unmute microphone' : 'Mute microphone'}
            variant={isMuted ? 'danger' : 'secondary'}
            size="lg"
            aria-pressed={isMuted}
            disabled={!isConnected}
            onClick={toggleMute}
          />
          <Button variant="danger" size="lg" icon={PhoneOff} onClick={endAndClose}>
            End call
          </Button>
          <IconButton
            icon={Settings2}
            label="Microphone settings"
            variant="secondary"
            size="lg"
            aria-expanded={showSettings}
            onClick={() => setShowSettings((v) => !v)}
          />
        </div>

        {isConnected && !isMuted && (
          <p className="mt-3 flex items-center gap-2 text-caption text-muted">
            <Mic aria-hidden="true" className="h-3.5 w-3.5" />
            Your microphone is live
          </p>
        )}

        {showSettings && (
          <div className="mt-5 w-full text-left animate-fade-in">
            <Field label="Microphone" help={audioDevices.length ? undefined : 'No microphones found. Allow microphone access in your browser.'}>
              <Select value={selectedAudioDevice || ''} onChange={(e) => changeAudioDevice(e.target.value)} disabled={!audioDevices.length}>
                {audioDevices.map((d) => (
                  <option key={d.deviceId} value={d.deviceId}>
                    {d.label || `Microphone ${d.deviceId.slice(0, 8)}`}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
        )}
      </div>
    </Modal>
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
    domain: PropTypes.string,
  }),
  onCallStart: PropTypes.func,
  onCallEnd: PropTypes.func,
};

export default VoiceCallModal;
