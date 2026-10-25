/**
 * useVoiceCall - Hook for managing voice call connections with LiveKit
 *
 * Handles room creation, token fetching, WebRTC connection lifecycle,
 * audio device selection, and error handling. `error` is always a sentence a
 * person can act on (utils/errors humanize), never a raw exception.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { Room, RoomEvent, ConnectionState, Track } from 'livekit-client';
import { apiFetch, apiJson } from '../services/http';
import { humanize } from '../utils/errors';

// Connection states for the UI
export const CallState = {
  IDLE: 'idle',
  CONNECTING: 'connecting',
  CONNECTED: 'connected',
  RECONNECTING: 'reconnecting',
  DISCONNECTING: 'disconnecting',
  DISCONNECTED: 'disconnected',
  ERROR: 'error',
};

/** What went wrong, in human words, by where in the dial sequence it failed. */
function describe(err, step) {
  const name = err?.name || '';
  if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
    return 'Microphone access was blocked. Allow the microphone for this site in your browser, then try again.';
  }
  if (name === 'NotFoundError' || name === 'OverconstrainedError') {
    return 'No microphone was found. Plug one in or pick another one in the settings, then try again.';
  }
  if (step === 'connect') {
    return 'Couldn’t reach the voice server. Check that LiveKit is running and reachable, then try again.';
  }
  if (step === 'room') return humanize(err, { what: 'setting up the voice room' });
  if (step === 'token') return humanize(err, { what: 'getting a voice token' });
  return humanize(err, { what: 'connecting the call' });
}

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

  // LiveKit room reference (+ the backend room id, readable from cleanup paths)
  const roomRef = useRef(null);
  const roomIdRef = useRef(null);
  const localAudioTrackRef = useRef(null);

  // Fetch available audio devices
  const fetchAudioDevices = useCallback(async () => {
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const audioInputs = devices.filter((d) => d.kind === 'audioinput');
      setAudioDevices(audioInputs);
      setSelectedAudioDevice((current) => current || audioInputs[0]?.deviceId || null);
    } catch {
      setAudioDevices([]);
    }
  }, []);

  // Initialize audio devices on mount
  useEffect(() => {
    if (!navigator.mediaDevices?.enumerateDevices) return undefined;
    fetchAudioDevices();
    navigator.mediaDevices.addEventListener?.('devicechange', fetchAudioDevices);
    return () => {
      navigator.mediaDevices.removeEventListener?.('devicechange', fetchAudioDevices);
    };
  }, [fetchAudioDevices]);

  // Create voice room on backend
  const createRoom = useCallback(
    () => apiJson('/voice/rooms', { method: 'POST', body: JSON.stringify({ agent_id: agentId, agent_name: agentName }) }),
    [agentId, agentName]
  );

  // Fetch participant token
  const fetchToken = useCallback((id) => apiJson(`/voice/rooms/${id}/token`), []);

  // Request agent to join room (non-blocking - the agent might join automatically)
  const requestAgentJoin = useCallback(async (id) => {
    try {
      return await apiJson(`/voice/rooms/${id}/agent/join`, { method: 'POST' });
    } catch {
      return null;
    }
  }, []);

  // Close room on backend (best-effort: a non-2xx here is not actionable)
  const closeRoom = useCallback(async (id) => {
    try {
      await apiFetch(`/voice/rooms/${id}`, { method: 'DELETE' });
    } catch {
      /* best effort */
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
  const setupRoomHandlers = useCallback(
    (room) => {
      room.on(RoomEvent.ConnectionStateChanged, (state) => {
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

      room.on(RoomEvent.Disconnected, () => {
        setCallState(CallState.DISCONNECTED);
        stopDurationTimer();
      });

      room.on(RoomEvent.TrackSubscribed, (track) => {
        if (track.kind === Track.Kind.Audio) {
          setIsAgentSpeaking(false);
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

      room.on(RoomEvent.TrackUnsubscribed, (track) => {
        if (track.kind === Track.Kind.Audio) {
          setIsAgentSpeaking(false);
          setRemoteAudioLevel(0);
        }
      });

      room.on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
        const agentSpeaking = speakers.some((s) => s.identity !== room.localParticipant?.identity);
        setIsAgentSpeaking(agentSpeaking);
        if (agentSpeaking) onAgentSpeaking?.();
        else onAgentListening?.();
      });
    },
    [startDurationTimer, stopDurationTimer, onAgentSpeaking, onAgentListening]
  );

  // Start voice call
  const startCall = useCallback(async () => {
    if (callState !== CallState.IDLE && callState !== CallState.DISCONNECTED && callState !== CallState.ERROR) return;

    setError(null);
    setCallState(CallState.CONNECTING);
    let step = 'room';

    try {
      // Create room on backend
      const roomData = await createRoom();
      const id = roomData.room_id || roomData.id;
      roomIdRef.current = id;
      setRoomId(id);
      setServerUrl(roomData.server_url);

      // Get participant token
      step = 'token';
      const tokenData = await fetchToken(id);
      setToken(tokenData.token);

      // Create LiveKit room
      step = 'connect';
      const room = new Room({
        adaptiveStream: true,
        dynacast: true,
        audioCaptureDefaults: {
          deviceId: selectedAudioDevice || undefined,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      roomRef.current = room;
      setupRoomHandlers(room);

      // Connect to room
      await room.connect(roomData.server_url, tokenData.token);

      // Enable microphone
      step = 'microphone';
      await room.localParticipant.setMicrophoneEnabled(true);
      localAudioTrackRef.current = room.localParticipant.getTrackPublication(Track.Source.Microphone)?.track;

      // Request agent to join
      await requestAgentJoin(id);
    } catch (err) {
      setError(describe(err, step));
      setCallState(CallState.ERROR);

      // Cleanup on error
      if (roomRef.current) {
        roomRef.current.disconnect();
        roomRef.current = null;
      }
      if (roomIdRef.current) {
        closeRoom(roomIdRef.current);
        roomIdRef.current = null;
      }
      stopDurationTimer();
    }
  }, [callState, createRoom, fetchToken, selectedAudioDevice, setupRoomHandlers, requestAgentJoin, closeRoom, stopDurationTimer]);

  // End voice call
  const endCall = useCallback(async () => {
    setCallState(CallState.DISCONNECTING);
    try {
      if (roomRef.current) {
        roomRef.current.disconnect();
        roomRef.current = null;
      }
      if (roomIdRef.current) {
        await closeRoom(roomIdRef.current);
      }
    } catch {
      /* best effort */
    } finally {
      roomIdRef.current = null;
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
  }, [closeRoom, stopDurationTimer]);

  // Toggle mute
  const toggleMute = useCallback(async () => {
    if (!roomRef.current?.localParticipant) return;
    try {
      const next = !isMuted;
      await roomRef.current.localParticipant.setMicrophoneEnabled(!next);
      setIsMuted(next);
    } catch {
      /* the control simply stays where it was */
    }
  }, [isMuted]);

  // Change audio device
  const changeAudioDevice = useCallback(async (deviceId) => {
    setSelectedAudioDevice(deviceId);
    if (roomRef.current?.localParticipant) {
      try {
        await roomRef.current.localParticipant.setMicrophoneEnabled(false);
        await roomRef.current.localParticipant.setMicrophoneEnabled(true, { deviceId });
      } catch {
        /* keep the previous device */
      }
    }
  }, []);

  // Check voice service availability (passive probe — no 401 redirect)
  const checkVoiceAvailability = useCallback(async () => {
    try {
      const response = await apiFetch('/voice/health', { redirectOn401: false });
      return response.ok;
    } catch {
      return false;
    }
  }, []);

  // Cleanup on unmount
  useEffect(
    () => () => {
      roomRef.current?.disconnect();
      stopDurationTimer();
    },
    [stopDurationTimer]
  );

  // Format duration as MM:SS
  const formatDuration = (seconds) => `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;

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
    hasError: callState === CallState.ERROR,
  };
}

export default useVoiceCall;
