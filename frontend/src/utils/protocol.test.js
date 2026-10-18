import assert from 'node:assert/strict';
import test from 'node:test';

import { normalizeProtocol } from './protocol.js';

test('paid is canonical and the legacy ap2 label maps to it', () => {
  assert.equal(normalizeProtocol('paid'), 'paid');
  assert.equal(normalizeProtocol('ap2'), normalizeProtocol('paid'));
});
