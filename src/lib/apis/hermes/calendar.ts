import type { CalendarEventModel } from '$lib/apis/calendar';
import type { Job } from './index';

export const HERMES_CALENDAR = 'hermes-workbench';
// A live projection, not a second scheduler or a copy in the WebUI database.
export function jobEvents(
	jobs: Job[],
	user: string,
	start: string,
	end: string
): CalendarEventModel[] {
	const result: CalendarEventModel[] = [];
	for (const job of jobs) {
		for (const [kind, time] of [
			['last', job.last_run_at],
			['next', job.enabled ? job.next_run_at : undefined]
		]) {
			if (!time) continue;
			const ms = Date.parse(time);
			if (!Number.isFinite(ms) || ms < Date.parse(start) || ms >= Date.parse(end)) continue;
			result.push({
				id: `hermes:${job.id}:${kind}`,
				calendar_id: HERMES_CALENDAR,
				user_id: user,
				title: `${job.name}${kind === 'last' ? ' · ' + (job.last_status || '已运行') : ''}`,
				description: job.prompt,
				start_at: ms * 1e6,
				end_at: (ms + 60000) * 1e6,
				all_day: false,
				rrule: null,
				color: '#3b7dd8',
				location: job.deliver,
				data: null,
				meta: { hermes_job_id: job.id },
				is_cancelled: false,
				attendees: [],
				created_at: 0,
				updated_at: 0
			});
		}
	}
	return result;
}
