import { useEffect, useState } from 'react';
import {
  LiveKitRoom as LKRoom,
  VideoConference,
  RoomAudioRenderer,
  useRoomContext,
  AudioTrack,
  VideoTrack
} from '@livekit/components-react';
import { Room, RoomEvent, Track } from 'livekit-client';
import { apiFetch } from '../services/http';

// Legacy LiveKit endpoints live at /api/livekit (NOT under /api/v1), so pass
// origin-absolute URLs to apiFetch to keep the exact paths while still
// attaching auth headers + credentials.
const livekitUrl = (path) => `${window.location.origin}${path}`;

const LiveKitRoom = ({ isVideoEnabled, isAudioEnabled, agentName }) => {
  const [token, setToken] = useState('');
  const [roomUrl, setRoomUrl] = useState('');

  useEffect(() => {
    // Get LiveKit token from backend
    const fetchToken = async () => {
      try {
        const response = await apiFetch(livekitUrl('/api/livekit/token'), {
          method: 'POST',
          redirectOn401: false,
          body: JSON.stringify({
            roomName: `agent-${agentName}`,
            participantName: 'user',
            canPublish: true,
            canSubscribe: true
          })
        });

        const data = await response.json();
        setToken(data.token);
        setRoomUrl(data.url || 'wss://localhost:7880'); // Default to local LiveKit server
      } catch (error) {
        console.error('Failed to fetch LiveKit token:', error);
        // Use demo token for development
        setToken('demo-token');
        setRoomUrl('wss://localhost:7880');
      }
    };

    if (agentName) {
      fetchToken();
    }
  }, [agentName]);

  if (!token) {
    return (
      <div className="h-64 glass rounded-lg flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-unicorn-500 mx-auto mb-4"></div>
          <p className="text-slate-400">Connecting to voice/video...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-64 glass rounded-lg overflow-hidden">
      <LKRoom
        serverUrl={roomUrl}
        token={token}
        audio={isAudioEnabled}
        video={isVideoEnabled}
        connect={true}
        options={{
          adaptiveStream: true,
          dynacast: true,
          publishDefaults: {
            videoCodec: 'vp9',
            simulcast: true,
          }
        }}
      >
        <div className="h-full flex">
          {/* Video Area */}
          {isVideoEnabled ? (
            <div className="flex-1 relative bg-slate-900">
              <VideoConference />
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center bg-slate-900">
              <div className="text-center">
                <div className="w-24 h-24 rounded-full bg-gradient-to-br from-unicorn-500 to-cyan-500 flex items-center justify-center mx-auto mb-4">
                  <span className="text-3xl font-bold text-white">
                    {agentName?.charAt(0).toUpperCase()}
                  </span>
                </div>
                <p className="text-slate-400">Voice Call Active</p>
                <p className="text-sm text-slate-400 mt-1">with {agentName}</p>
              </div>
            </div>
          )}

          {/* Audio Renderer */}
          <RoomAudioRenderer />
        </div>
      </LKRoom>
    </div>
  );
};

// Fallback component for when LiveKit isn't available
const LiveKitFallback = ({ isVideoEnabled, isAudioEnabled, agentName }) => {
  return (
    <div className="h-64 glass rounded-lg flex items-center justify-center">
      <div className="text-center">
        {isAudioEnabled || isVideoEnabled ? (
          <>
            <div className="w-20 h-20 rounded-full bg-gradient-to-br from-unicorn-500 to-cyan-500 flex items-center justify-center mx-auto mb-4 animate-pulse">
              <span className="text-2xl font-bold text-white">
                {agentName?.charAt(0).toUpperCase()}
              </span>
            </div>
            <p className="text-slate-300">
              {isVideoEnabled ? 'Video' : 'Voice'} Call Simulation
            </p>
            <p className="text-sm text-slate-400 mt-1">
              LiveKit server not connected
            </p>
          </>
        ) : (
          <p className="text-slate-400">Enable voice or video to start</p>
        )}
      </div>
    </div>
  );
};

// Export the component with fallback
const LiveKitWrapper = (props) => {
  const [hasLiveKit, setHasLiveKit] = useState(true);

  useEffect(() => {
    // Check if LiveKit server is available (passive probe — no 401 redirect)
    apiFetch(livekitUrl('/api/livekit/health'), { redirectOn401: false })
      .then(res => setHasLiveKit(res.ok))
      .catch(() => setHasLiveKit(false));
  }, []);

  return hasLiveKit ? <LiveKitRoom {...props} /> : <LiveKitFallback {...props} />;
};

export default LiveKitWrapper;