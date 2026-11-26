import { describe, expect, it } from 'vitest';
import { classifyPrActions, type PrActionInput } from '../components/dashboard/prActions';
import { item } from './fixtures';

const saved = item();
const base: PrActionInput = { history: 'ready', review: saved, head: 'head-1', mode: 'auto', busy: false, uncertain: false, writeDenied: false };
type Result = Partial<ReturnType<typeof classifyPrActions>>;
const cases: [string, Partial<PrActionInput>, Result][] = [
  ['completed matching', {}, { primary: 'link', destination: '/reviews/9', readLabel: 'View Review', revision: 'current', mutation: 'Run Another Review' }],
  ['running on an earlier revision', { review: { ...saved, id: 33, status: 'running', commit_sha: 'old' } }, { readLabel: 'View Progress', destination: '/reviews/33', revision: 'outdated', mutation: undefined }],
  ['queued', { review: { ...saved, status: 'pending' } }, { readLabel: 'View Queued Review', mutation: undefined }],
  ['failed', { review: { ...saved, status: 'failed' } }, { readLabel: 'Inspect Failed Review', mutation: 'Run Another Review' }],
  ['skipped', { review: { ...saved, status: 'skipped' } }, { readLabel: 'Inspect Skipped Review' }],
  ['outdated terminal', { head: 'new' }, { readLabel: 'View Previous Review', revision: 'outdated', mutation: 'Review Current Revision' }],
  ['missing review revision', { review: { ...saved, commit_sha: null } }, { revision: 'unknown', readLabel: 'View Review' }],
  ['missing head', { head: '' }, { revision: 'unknown' }],
  ['manual first request', { review: undefined, mode: 'manual' }, { primary: 'request', mutation: 'Review Pull Request', destination: undefined }],
  ['automatic eligibility', { review: undefined }, { primary: 'none', mutation: 'Request Review Now', destination: undefined }],
  ['loading without data', { review: undefined, history: 'loading' }, { primary: 'none', explanation: expect.stringContaining('Checking review history'), mutation: 'Request Review Now' }],
  ['refreshing cached result', { history: 'loading' }, { lastKnown: true, destination: '/reviews/9' }],
  ['bounded without result', { history: 'bounded', review: undefined }, { primary: 'older', recoveryLabel: 'Load older review history', mutation: 'Request Review Now' }],
  ['failed without result', { history: 'failed', review: undefined }, { primary: 'refresh', recoveryLabel: 'Retry history', destination: undefined }],
  ['failed with cached active run', { history: 'failed', review: { ...saved, status: 'running' } }, { primary: 'refresh', lastKnown: true, destination: '/reviews/9', mutation: undefined }],
  ['write forbidden', { writeDenied: true }, { primary: 'link', mutation: undefined, warning: expect.stringContaining('write access') }],
  ['read access lost', { history: 'denied', uncertain: true }, { destination: undefined, mutation: undefined, primary: 'none' }],
  ['pending write', { busy: true }, { disabled: true, mutation: 'Requesting review…', destination: '/reviews/9' }],
  ['uncertain write and failed read', { uncertain: true, history: 'failed' }, { primary: 'refresh', recoveryLabel: 'Check review history', disabled: true, destination: '/reviews/9' }],
];

describe('PR action policy', () => {
  it.each(cases)('%s', (_name, overrides, expected) => {
    expect(classifyPrActions({ ...base, ...overrides })).toMatchObject(expected);
  });
});
