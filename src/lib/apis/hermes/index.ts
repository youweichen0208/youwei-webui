import { WEBUI_API_BASE_URL } from '$lib/constants';
import { createParser } from 'eventsource-parser';

export type Session = { id: string; title?: string; source?: string; model?: string };
export type Message = { role: string; content: string; id?: string };
export type Skill = { name: string; description: string; category?: string };
export type Job = {
	id: string;
	name: string;
	prompt: string;
	schedule: { kind: string; expr?: string; display?: string };
	schedule_display: string;
	deliver: string;
	enabled: boolean;
	state: string;
	next_run_at?: string;
	last_run_at?: string;
	last_status?: string;
	last_error?: string;
};
export type RunEvent = {
	event: string;
	run_id?: string;
	session_id?: string;
	delta?: string;
	output?: string;
	text?: string;
	already_streamed?: boolean;
	tool?: string;
	preview?: string;
	command?: string;
	request_id?: string;
	choices?: string[];
	choice?: string;
	error?: boolean | string;
	status?: string;
	usage?: Record<string, number>;
	runtime?: Record<string, unknown>;
	approval?: RunEvent;
};
export const terminal = new Set(['completed', 'cancelled', 'failed', 'interrupted']);

export class HermesError extends Error {
	constructor(
		message: string,
		public status: number
	) {
		super(message);
	}
}

export async function hermes<T = any>(
	path: string,
	body?: unknown,
	method?: string,
	key?: string,
	signal?: AbortSignal
): Promise<T> {
	const response = await fetch(`${WEBUI_API_BASE_URL}/hermes/${path}`, {
		method: method ?? (body === undefined ? 'GET' : 'POST'),
		signal,
		headers: {
			Authorization: `Bearer ${localStorage.token}`,
			'Content-Type': 'application/json',
			...(key ? { 'Idempotency-Key': key } : {})
		},
		body: body === undefined ? undefined : JSON.stringify(body)
	});
	const data = await response.json().catch(() => ({}));
	if (!response.ok)
		throw new HermesError(
			typeof data.detail === 'string' ? data.detail : 'Hermes 请求失败',
			response.status
		);
	return data;
}

// Native /runs emits data-only SSE; tolerate CRLF, multiline JSON and split UTF-8 frames.
export function eventParser(receive: (event: RunEvent) => void) {
	return createParser((event) => {
		if (event.type !== 'event' || event.data === '[DONE]') return;
		const payload = JSON.parse(event.data);
		if (typeof payload.event === 'string') receive(payload);
	});
}

export async function events(run: string, receive: (event: RunEvent) => void, signal: AbortSignal) {
	const response = await fetch(
		`${WEBUI_API_BASE_URL}/hermes/runs/${encodeURIComponent(run)}/events`,
		{
			headers: { Authorization: `Bearer ${localStorage.token}` },
			signal
		}
	);
	if (!response.ok || !response.body) throw new Error('事件流连接失败，请刷新运行状态');
	const reader = response.body.getReader();
	const decoder = new TextDecoder();
	const parser = eventParser(receive);
	try {
		while (true) {
			const { done, value } = await reader.read();
			if (done) {
				parser.feed(decoder.decode());
				break;
			}
			parser.feed(decoder.decode(value, { stream: true }));
		}
	} finally {
		await reader.cancel().catch(() => {});
		reader.releaseLock();
	}
}

export async function waitStopped(run: string) {
	for (let n = 0; n < 60; n++) {
		const status = await hermes(`runs/${encodeURIComponent(run)}`);
		if (terminal.has(status.status)) return status;
		await new Promise((resolve) => setTimeout(resolve, 500));
	}
	throw new Error('Hermes 仍在停止，请稍后刷新；新消息尚未发送');
}
