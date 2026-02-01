/**
 * useVoiceCall - Hook for managing voice call connections with LiveKit
 *
 * Handles room creation, token fetching, WebRTC connection lifecycle,
 * audio device selection, and error handling.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { Room, RoomEvent, ConnectionState, Track, LocalParticipant } from 'livekit-client';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8100/api/v1';

// Connection states for the UI
export const CallState = {
  IDLE: 'idle',
  CONNECTING: 'connecting',
  CONNECTED: 'connected',
  RECONNECTING: 'reconnecting',
  DISCONNECTING: 'disconnecting',
  DISCONNECTED: 'disconnected',
  ERROR: 'error'
};

export function useVoiceCall({ agentId, agentName, onAgentSpeaking, onAgentListening }) {
  // Connection state
  const [callState, setCallState] = useState(CallState.IDLE);
  const [error, setError] = useState(null);
  const [roomId, setRoomId] = useState(null);
  const [serverUrl, setServerUrl] = useState(null);
  const [token, setToken] = useState(null);

  // Audio state
  const [isMuted, setIsMuted] = useState(false);
  const [isAgentSpeaking, setIsAgentSpeaking] = useState(false);
  const [localAudioLevel, setLocalAudioLevel] = useState(0);
  const [remoteAudioLevel, setRemoteAudioLevel] = useState(0);

  // Call duration
  const [callDuration, setCallDuration] = useState(0);
  const callStartTimeRef = useRef(null);
  const durationIntervalRef = useRef(null);

  // Audio devices
  const [audioDevices, setAudioDevices] = useState([]);
  const [selectedAudioDevice, setSelectedAudioDevice] = useState(null);

  // LiveKit room reference
  const roomRef = useRef(null);
  const localAudioTrackRef = useRef(null);

  // Fetch available audio devices
  const fetchAudioDevices = useCallback(async () => {
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const audioInputs = devices.filter(d => d.kind === 'audioinput');
      setAudioDevices(audioInputs);
      if (audioInputs.length > 0 && !selectedAudioDevice) {
        setSelectedAudioDevice(audioInputs[0].deviceId);
      }
    } catch (err) {
      console.error('Failed to enumerate audio devices:', err);
    }
  }, [selectedAudioDevice]);

  // Initialize audio devices on mount
  useEffect(() => {
    fetchAudioDevices();

    // Listen for device changes
    navigator.mediaDevices.addEventListener('devicechange', fetchAudioDevices);
    return () => {
      navigator.mediaDevices.removeEventListener('devicechange', fetchAudioDevices);
    };
  }, [fetchAudioDevices]);

  // Create voice room on backend
  const createRoom = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/voice/rooms`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent_id: agentId })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to create room: ${response.status}`);
      }

      const data = await response.json();
      return data;
    } catch (err) {
      console.error('Failed to create voice room:', err);
      throw err;
    }
  }, [agentId]);

  // Fetch participant token
  const fetchToken = useCallback(async (roomId) => {
    try {
      const response = await fetch(`${API_BASE}/voice/rooms/${roomId}/token`);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to get token: ${response.status}`);
      }

      const data = await response.json();
      return data;
    } catch (err) {
      console.error('Failed to fetch token:', err);
      throw err;
    }
  }, []);

  // Request agent to join room
  const requestAgentJoin = useCallback(async (roomId) => {
    try {
      const response = await fetch(`${API_BASE}/voice/rooms/${roomId}/agent/join`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to request agent join: ${response.status}`);
      }

      return await response.json();
    } catch (err) {
      console.error('Failed to request agent join:', err);
      // Non-blocking - agent might join automatically
    }
  }, []);

  // Close room on backend
  const closeRoom = useCallback(async (roomId) => {
    try {
      await fetch(`${API_BASE}/voice/rooms/${roomId}`, {
        method: 'DELETE'
      });
    } catch (err) {
      console.error('Failed to close room:', err);
    }
  }, []);

  // Start call duration timer
  const startDurationTimer = useCallback(() => {
    callStartTimeRef.current = Date.now();
    setCallDuration(0);

    durationIntervalRef.current = setInterval(() => {
      if (callStartTimeRef.current) {
        setCallDuration(Math.floor((Date.now() - callStartTimeRef.current) / 1000));
      }
    }, 1000);
  }, []);

  // Stop call duration timer
  const stopDurationTimer = useCallback(() => {
    if (durationIntervalRef.current) {
      clearInterval(durationIntervalRef.current);
      durationIntervalRef.current = null;
    }
    callStartTimeRef.current = null;
  }, []);

  // Setup room event handlers
  const setupRoomHandlers = useCallback((room) => {
    room.on(RoomEvent.ConnectionStateChanged, (state) => {
      console.log('Connection state changed:', state);

      switch (state) {
        case ConnectionState.Connecting:
          setCallState(CallState.CONNECTING);
          break;
        case ConnectionState.Connected:
          setCallState(CallState.CONNECTED);
          startDurationTimer();
          break;
        case ConnectionState.Reconnecting:
          setCallState(CallState.RECONNECTING);
          break;
        case ConnectionState.Disconnected:
          setCallState(CallState.DISCONNECTED);
          stopDurationTimer();
          break;
        default:
          break;
      }
    });

    room.on(RoomEvent.Disconnected, (reason) => {
      console.log('Disconnected:', reason);
      setCallState(CallState.DISCONNECTED);
      stopDurationTimer();
    });

    room.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
      console.log('Track subscribed:', track.kind, 'from', participant.identity);

      if (track.kind === Track.Kind.Audio) {
        // Agent audio track subscribed
        setIsAgentSpeaking(false);

        // Monitor agent audio level
        const monitorInterval = setInterval(() => {
          if (track.isMuted) {
            setRemoteAudioLevel(0);
            setIsAgentSpeaking(false);
          }
        }, 100);

        track.on('ended', () => {
          clearInterval(monitorInterval);
          setIsAgentSpeaking(false);
          setRemoteAudioLevel(0);
        });
      }
    });

    room.on(RoomEvent.TrackUnsubscribed, (track, publication, participant) => {
      console.log('Track unsubscribed:', track.kind, 'from', participant.identity);
      if (track.kind === Track.Kind.Audio) {
        setIsAgentSpeaking(false);
        setRemoteAudioLevel(0);
      }
    });

    room.on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
      const agentSpeaking = speakers.some(s => s.identity !== room.localParticipant?.identity);
      setIsAgentSpeaking(agentSpeaking);

      if (agentSpeaking && onAgentSpeaking) {
        onAgentSpeaking();
      } else if (!agentSpeaking && onAgentListening) {
        onAgentListening();
      }
    });

    room.on(RoomEvent.ParticipantConnected, (participant) => {
      console.log('Participant connected:', participant.identity);
    });

    room.on(RoomEvent.ParticipantDisconnected, (participant) => {
      console.log('Participant disconnected:', participant.identity);
    });

    room.on(RoomEvent.AudioPlaybackStatusChanged, () => {
      if (!room.canPlaybackAudio) {
        console.warn('Audio playback requires user interaction');
      }
    });

  }, [startDurationTimer, stopDurationTimer, onAgentSpeaking, onAgentListening]);

  // Start voice call
  const startCall = useCallback(async () => {
    if (callState !== CallState.IDLE && callState !== CallState.DISCONNECTED && callState !== CallState.ERROR) {
      console.warn('Call already in progress');
      return;
    }

    setError(null);
    setCallState(CallState.CONNECTING);

    try {
      // Create room on backend
      const roomData = await createRoom();
      setRoomId(roomData.room_id);
      setServerUrl(roomData.server_url);

      // Get participant token
      const tokenData = await fetchToken(roomData.room_id);
      setToken(tokenData.token);

      // Create LiveKit room
      const room = new Room({
        adaptiveStream: true,
        dynacast: true,
        audioCaptureDefaults: {
          deviceId: selectedAudioDevice,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });

      roomRef.current = room;
      setupRoomHandlers(room);

      // Connect to room
      await room.connect(roomData.server_url, tokenData.token);

      // Enable microphone
      await room.localParticipant.setMicrophoneEnabled(true);
      localAudioTrackRef.current = room.localParticipant.getTrackPublication(Track.Source.Microphone)?.track;

      // Request agent to join
      await requestAgentJoin(roomData.room_id);

    } catch (err) {
      console.error('Failed to start call:', err);
      setError(err.message || 'Failed to connect');
      setCallState(CallState.ERROR);

      // Cleanup on error
      if (roomRef.current) {
        roomRef.current.disconnect();
        roomRef.current = null;
      }
      if (roomId) {
        closeRoom(roomId);
      }
    }
  }, [
    callState,
    createRoom,
    fetchToken,
    selectedAudioDevice,
    setupRoomHandlers,
    requestAgentJoin,
    closeRoom,
    roomId
  ]);

  // End voice call
  const endCall = useCallback(async () => {
    setCallState(CallState.DISCONNECTING);

    try {
      // Disconnect from LiveKit
      if (roomRef.current) {
        roomRef.current.disconnect();
        roomRef.current = null;
      }

      // Close room on backend
      if (roomId) {
        await closeRoom(roomId);
      }
    } catch (err) {
      console.error('Error ending call:', err);
    } finally {
      setCallState(CallState.IDLE);
      setRoomId(null);
      setServerUrl(null);
      setToken(null);
      setIsMuted(false);
      setIsAgentSpeaking(false);
      setLocalAudioLevel(0);
      setRemoteAudioLevel(0);
      stopDurationTimer();
      setCallDuration(0);
      localAudioTrackRef.current = null;
    }
  }, [roomId, closeRoom, stopDurationTimer]);

  // Toggle mute
  const toggleMute = useCallback(async () => {
    if (!roomRef.current?.localParticipant) return;

    try {
      const newMuteState = !isMuted;
      await roomRef.current.localParticipant.setMicrophoneEnabled(!newMuteState);
      setIsMuted(newMuteState);
    } catch (err) {
      console.error('Failed to toggle mute:', err);
    }
  }, [isMuted]);

  // Change audio device
  const changeAudioDevice = useCallback(async (deviceId) => {
    setSelectedAudioDevice(deviceId);

    if (roomRef.current?.localParticipant) {
      try {
        // Re-enable microphone with new device
        await roomRef.current.localParticipant.setMicrophoneEnabled(false);
        await roomRef.current.localParticipant.setMicrophoneEnabled(true, {
          deviceId
        });
      } catch (err) {
        console.error('Failed to change audio device:', err);
      }
    }
  }, []);

  // Check voice service availability
  const checkVoiceAvailability = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/voice/health`);
      return response.ok;
    } catch {
      return false;
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (roomRef.current) {
        roomRef.current.disconnect();
      }
      stopDurationTimer();
    };
  }, [stopDurationTimer]);

  // Format duration as MM:SS
  const formatDuration = useCallback((seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }, []);

  return {
    // State
    callState,
    error,
    roomId,
    isMuted,
    isAgentSpeaking,
    localAudioLevel,
    remoteAudioLevel,
    callDuration,
    formattedDuration: formatDuration(callDuration),

    // Audio devices
    audioDevices,
    selectedAudioDevice,

    // LiveKit references (for advanced usage)
    room: roomRef.current,
    serverUrl,
    token,

    // Actions
    startCall,
    endCall,
    toggleMute,
    changeAudioDevice,
    checkVoiceAvailability,

    // Helpers
    isConnecting: callState === CallState.CONNECTING,
    isConnected: callState === CallState.CONNECTED,
    isReconnecting: callState === CallState.RECONNECTING,
    isDisconnecting: callState === CallState.DISCONNECTING,
    isIdle: callState === CallState.IDLE || callState === CallState.DISCONNECTED,
    hasError: callState === CallState.ERROR
  };
}

export default useVoiceCall;
