import { create } from 'zustand';

// Max windows open (non-minimized) at once. HTTP/1.1 caps ~6 streams/origin and
// the orchestration stream takes one, so keep a little headroom.
export const MAX_COMMS_WINDOWS = 4;

/**
 * Floating per-agent comms windows over the Command Center board. Windows are
 * keyed by agent id (re-opening focuses the existing one). Each window mounts
 * its own useAgentChat, so conversations are fully independent.
 */
export const useCommsStore = create((set, get) => ({
  windows: [], // [{ agent, x, y, z, minimized }]
  zTop: 10,

  // opts: { seed?: Message[], model?: string }. `seed` pre-loads a prior
  // conversation (e.g. promoting a briefing answer) and only applies when the
  // window is first created; re-opening just focuses the existing one.
  openWindow: (agent, opts = {}) =>
    set((state) => {
      const z = state.zTop + 1;
      const existing = state.windows.find((w) => w.agent.id === agent.id);
      if (existing) {
        return {
          zTop: z,
          windows: state.windows.map((w) =>
            w.agent.id === agent.id ? { ...w, minimized: false, z } : w
          ),
        };
      }
      const n = state.windows.length;
      const next = {
        agent,
        x: 140 + (n % 5) * 30,
        y: 96 + (n % 5) * 30,
        z,
        minimized: false,
        model: opts.model,
        seed: opts.seed,
      };
      let windows = [...state.windows, next];
      // Cap visible windows: minimize the least-recently-focused if over the cap.
      const open = windows.filter((w) => !w.minimized);
      if (open.length > MAX_COMMS_WINDOWS) {
        const lru = [...open].sort((a, b) => a.z - b.z)[0];
        windows = windows.map((w) => (w.agent.id === lru.agent.id ? { ...w, minimized: true } : w));
      }
      return { windows, zTop: z };
    }),

  focusWindow: (id) =>
    set((state) => {
      const z = state.zTop + 1;
      return {
        zTop: z,
        windows: state.windows.map((w) => (w.agent.id === id ? { ...w, z, minimized: false } : w)),
      };
    }),

  minimize: (id) =>
    set((state) => ({
      windows: state.windows.map((w) => (w.agent.id === id ? { ...w, minimized: true } : w)),
    })),

  close: (id) => set((state) => ({ windows: state.windows.filter((w) => w.agent.id !== id) })),

  setPos: (id, x, y) =>
    set((state) => ({
      windows: state.windows.map((w) => (w.agent.id === id ? { ...w, x, y } : w)),
    })),

  // Per-window model override (undefined = use the agent's own default model).
  setModel: (id, model) =>
    set((state) => ({
      windows: state.windows.map((w) => (w.agent.id === id ? { ...w, model: model || undefined } : w)),
    })),
}));

export default useCommsStore;
