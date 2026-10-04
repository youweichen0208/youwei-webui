import { describe, expect, it, vi } from 'vitest';
vi.mock('$lib/constants', () => ({ WEBUI_API_BASE_URL: '/api/v1' }));
import { eventParser, type RunEvent, type Job } from './index';
import { jobEvents } from './calendar';

describe('native Hermes event stream', () => {
	it('handles split frames, comments, CRLF and multiple events', () => {
		const events: RunEvent[] = [];
		const parser = eventParser((e) => events.push(e));
		parser.feed(': keepalive\r\n\r\ndata: {"event":"message.');
		parser.feed('delta","delta":"你好"}\r\n\r\ndata: {"event":"approval.request",\n');
		parser.feed('data: "request_id":"r1","choices":["once","deny"]}\n\ndata: [DONE]\n\n');
		expect(events).toHaveLength(2);
		expect(events[0].delta).toBe('你好');
		expect(events[1].request_id).toBe('r1');
	});
	it('does not silently treat malformed output as a completed run', () => {
		const parser = eventParser(() => {});
		expect(() => parser.feed('data: invalid\n\n')).toThrow();
	});
});

describe('calendar projection', () => {
	const job: Job = {
		id: 'j',
		name: 'Report',
		prompt: 'Do work',
		schedule: { kind: 'cron', expr: '0 9 * * *' },
		schedule_display: 'Every day',
		deliver: 'local',
		enabled: true,
		state: 'scheduled',
		last_run_at: '2026-10-03T09:00:00Z',
		next_run_at: '2026-10-05T09:00:00Z',
		last_status: 'success'
	};
	it('projects observed last and next runs in nanoseconds, without inventing history', () => {
		const events = jobEvents([job], 'owner', '2026-10-01', '2026-11-01');
		expect(events).toHaveLength(2);
		expect(events[0].start_at).toBe(Date.parse(job.last_run_at!) * 1e6);
		expect(events[0].meta).toEqual({ hermes_job_id: 'j' });
	});
	it('omits disabled future runs and filters the visible range', () => {
		expect(jobEvents([{ ...job, enabled: false }], 'owner', '2026-10-04', '2026-11-01')).toEqual(
			[]
		);
	});
});
