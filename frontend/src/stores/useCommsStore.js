import { create } from 'zustand';
import notify from '../utils/notify';

// Max windows open (non-minimized) at once. HTTP/1.1 caps ~6 streams/origin and
// the orchestration stream takes one, so keep a little headroom.
export const MAX_COMMS_WINDOWS = 4;

const topOf = (windows) => windows.filter((w) => !w.minimized).sort((a, b) => b.z - a.z)[0] || null;

/**
 * Floating per-agent comms windows over the Command Center board. Windows are
 * keyed by agent id (re-opening focuses the existing one). Each window mounts
 * its own useAgentChat, so conversations are fully independent.
 */
export const useCommsStore = create((set, get) => ({
  windows: [], // [{ agent, x, y, z, minimized, model, seed, seedKey }]
  zTop: 10,

  // opts: { seed?: Message[], model?: string }. `seed` pre-loads a prior
  // conversation (e.g. promoting a briefing answer) and only applies when the
  // window is first created; re-opening just focuses the existing one.
  openWindow: (agent, opts = {}) => {
    let tucked = null;
    set((state) => {
      const z = state.zTop + 1;
      const existing = state.windows.find((w) => w.agent.id === agent.id);
      if (existing) {
        return {
          zTop: z,
          windows: state.windows.map((w) =>
            w.agent.id === agent.id
              ? {
                  ...w,
                  minimized: false,
                  z,
                  // A promote carrying a seed re-seeds the window; bump seedKey so
                  // CommsWindow remounts with the new conversation (a mounted
                  // useAgentChat can't be re-seeded in place).
                  ...(opts.seed ? { seed: opts.seed, seedKey: (w.seedKey || 0) + 1 } : {}),
                  ...(opts.model ? { model: opts.model } : {}),
                }
              : w
          ),
        };
      }
      const n = state.windows.length;
      const next = { agent, x: 140 + (n % 5) * 30, y: 96 + (n % 5) * 30, z, minimized: false, model: opts.model, seed: opts.seed, seedKey: 0 };
      let windows = [...state.windows, next];
      // Cap visible windows: tuck the least-recently-focused into the tray.
      const open = windows.filter((w) => !w.minimized);
      if (open.length > MAX_COMMS_WINDOWS) {
        const lru = [...open].sort((a, b) => a.z - b.z)[0];
        tucked = lru.agent;
        windows = windows.map((w) => (w.agent.id === lru.agent.id ? { ...w, minimized: true } : w));
      }
      return { windows, zTop: z };
    });
    if (tucked) {
      notify.info(`Tucked ${tucked.displayName || tucked.name} into the tray — ${MAX_COMMS_WINDOWS} windows open at once.`, { id: 'comms-cap' });
    }
  },

  focusWindow: (id) =>
    set((state) => {
      const z = state.zTop + 1;
      return { zTop: z, windows: state.windows.map((w) => (w.agent.id === id ? { ...w, z, minimized: false } : w)) };
    }),

  minimize: (id) => set((state) => ({ windows: state.windows.map((w) => (w.agent.id === id ? { ...w, minimized: true } : w)) })),

  close: (id) => set((state) => ({ windows: state.windows.filter((w) => w.agent.id !== id) })),

  /** Close the top-most open window (Escape from the board). Returns true if one closed. */
  closeTop: () => {
    const top = topOf(get().windows);
    if (!top) return false;
    set((state) => ({ windows: state.windows.filter((w) => w.agent.id !== top.agent.id) }));
    return true;
  },

  setPos: (id, x, y) => set((state) => ({ windows: state.windows.map((w) => (w.agent.id === id ? { ...w, x, y } : w)) })),

  // Per-window model override (undefined = use the agent's own default model).
  setModel: (id, model) => set((state) => ({ windows: state.windows.map((w) => (w.agent.id === id ? { ...w, model: model || undefined } : w)) })),
}));

export default useCommsStore;
