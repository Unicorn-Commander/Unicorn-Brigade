/**
 * LiveKitRoom — the legacy voice/video pane (the /api/livekit endpoints).
 *
 * Kept as a self-contained pane: it mints its own token, connects, and falls
 * back to a plain "not connected" card when the LiveKit server is not there.
 * The chat page's voice calls use VoiceCallModal + useVoiceCall instead.
 */
import { useEffect, useState } from 'react';
import { LiveKitRoom as LKRoom, VideoConference, RoomAudioRenderer } from '@livekit/components-react';
import { PhoneOff } from 'lucide-react';
import { apiFetch } from '../services/http';
import { Spinner, StatusDot } from './ui';

// Legacy LiveKit endpoints live at /api/livekit (NOT under /api/v1), so pass
// origin-absolute URLs to apiFetch to keep the exact paths while still
// attaching auth headers + credentials.
const livekitUrl = (path) => `${window.location.origin}${path}`;

const Initial = ({ name, pulse = false }) => (
  <span
    aria-hidden="true"
    className={`flex h-20 w-20 items-center justify-center rounded-full bg-gradient-accent text-title text-on-accent ${pulse ? 'animate-pulse' : ''}`}
  >
    {name?.charAt(0).toUpperCase() || '?'}
  </span>
);

const LiveKitRoom = ({ isVideoEnabled, isAudioEnabled, agentName }) => {
  const [token, setToken] = useState('');
  const [roomUrl, setRoomUrl] = useState('');

  useEffect(() => {
    if (!agentName) return;
    let cancelled = false;
    apiFetch(livekitUrl('/api/livekit/token'), {
      method: 'POST',
      redirectOn401: false,
      body: JSON.stringify({ roomName: `agent-${agentName}`, participantName: 'user', canPublish: true, canSubscribe: true }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (cancelled) return;
        setToken(data.token);
        setRoomUrl(data.url || 'wss://localhost:7880');
      })
      .catch(() => {
        if (cancelled) return;
        // Demo token for local development without a LiveKit server.
        setToken('demo-token');
        setRoomUrl('wss://localhost:7880');
      });
    return () => {
      cancelled = true;
    };
  }, [agentName]);

  if (!token) {
    return (
      <div className="flex h-64 items-center justify-center rounded-card border border-border bg-card" role="status">
        <p className="flex items-center gap-2 text-body text-muted">
          <Spinner label="Connecting" />
          Connecting to voice…
        </p>
      </div>
    );
  }

  return (
    <div className="h-64 overflow-hidden rounded-card border border-border bg-card">
      <LKRoom
        serverUrl={roomUrl}
        token={token}
        audio={isAudioEnabled}
        video={isVideoEnabled}
        connect
        options={{ adaptiveStream: true, dynacast: true, publishDefaults: { videoCodec: 'vp9', simulcast: true } }}
      >
        <div className="flex h-full">
          {isVideoEnabled ? (
            <div className="relative flex-1 bg-surface">
              <VideoConference />
            </div>
          ) : (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 bg-surface text-center">
              <Initial name={agentName} />
              <p className="flex items-center gap-2 text-body text-fg">
                <StatusDot status="responding" size="md" />
                Voice call live
              </p>
              <p className="text-body-sm text-muted">with {agentName}</p>
            </div>
          )}
          <RoomAudioRenderer />
        </div>
      </LKRoom>
    </div>
  );
};

// Fallback component for when LiveKit isn't available
const LiveKitFallback = ({ isVideoEnabled, isAudioEnabled, agentName }) => (
  <div className="flex h-64 items-center justify-center rounded-card border border-border bg-card" role="status">
    <div className="flex flex-col items-center gap-3 text-center">
      {isAudioEnabled || isVideoEnabled ? (
        <>
          <Initial name={agentName} pulse />
          <p className="text-body text-fg">{isVideoEnabled ? 'Video' : 'Voice'} call simulation</p>
          <p className="flex items-center gap-2 text-body-sm text-muted">
            <PhoneOff aria-hidden="true" className="h-4 w-4" />
            The LiveKit server isn’t connected
          </p>
        </>
      ) : (
        <p className="text-body text-muted">Enable voice or video to start</p>
      )}
    </div>
  </div>
);

// Export the component with fallback
const LiveKitWrapper = (props) => {
  const [hasLiveKit, setHasLiveKit] = useState(true);

  useEffect(() => {
    // Passive probe — no 401 redirect
    let cancelled = false;
    apiFetch(livekitUrl('/api/livekit/health'), { redirectOn401: false })
      .then((res) => !cancelled && setHasLiveKit(res.ok))
      .catch(() => !cancelled && setHasLiveKit(false));
    return () => {
      cancelled = true;
    };
  }, []);

  return hasLiveKit ? <LiveKitRoom {...props} /> : <LiveKitFallback {...props} />;
};

export default LiveKitWrapper;
