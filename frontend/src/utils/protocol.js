const PROTOCOL_ALIASES = Object.freeze({
  ap2: 'paid',
});

/**
 * Normalize protocol labels used by stored and live orchestration events.
 * `ap2` is retained as a read-only compatibility alias for older events.
 */
export function normalizeProtocol(protocol) {
  return PROTOCOL_ALIASES[protocol] ?? protocol;
}
