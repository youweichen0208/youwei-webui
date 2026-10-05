import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { mount, unmount, tick } from 'svelte';
import { writable } from 'svelte/store';

vi.mock('$app/stores', () => ({ page: writable({ url: new URL('https://example.test/') }) }));
vi.mock('$lib/constants', () => ({ WEBUI_API_BASE_URL: '/api/v1' }));
import { page } from '$app/stores';
import SidebarNav from './SidebarNav.svelte';

const paths = () => vi.mocked(fetch).mock.calls.map(([url]) => String(url).split('/hermes/')[1]);
const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });
const navigate = async (path: string) => {
	(page as ReturnType<typeof writable>).set({ url: new URL(path, 'https://example.test') });
	await settle();
};
const settle = async () => {
	for (let i = 0; i < 10; i++) {
		await tick();
		await new Promise((r) => setTimeout(r, 0));
	}
};
let component: ReturnType<typeof mount> | undefined;
let target: HTMLDivElement;

beforeEach(() => {
	localStorage.token = 'test-owner';
	vi.stubGlobal(
		'fetch',
		vi.fn(async (url) => {
			const path = String(url).split('/hermes/')[1];
			return response(
				path === 'config'
					? { enabled: true }
					: path === 'jobs'
						? { jobs: [{ enabled: true }] }
						: { data: [{ id: 's1', title: 'Recent session' }] }
			);
		})
	);
	target = document.createElement('div');
	document.body.append(target);
	(page as ReturnType<typeof writable>).set({ url: new URL('https://example.test/') });
});
afterEach(async () => {
	if (component) await unmount(component);
	target.remove();
	vi.unstubAllGlobals();
});

async function render(path = '/') {
	await navigate(path);
	component = mount(SidebarNav, { target });
	await settle();
}

describe('Agent sidebar lazy details', () => {
	it('chat loads only config, retains navigation and omits unknown counts', async () => {
		await render();
		expect(paths()).toEqual(['config']);
		expect(target.querySelectorAll('nav a')).toHaveLength(4);
		expect(target.querySelectorAll('a span')).toHaveLength(0);
	});
	it('loads on client entry and deduplicates renders and workbench subroutes', async () => {
		await render();
		await navigate('/agent');
		await navigate('/agent/skills');
		await navigate('/agent?session=s1');
		expect(paths()).toEqual(['config', 'sessions?limit=5', 'skills', 'jobs']);
		expect(target.textContent).toContain('Recent session');
		await navigate('/c/chat');
		expect(target.textContent).not.toContain('Recent session');
		expect(target.querySelectorAll('a span')).toHaveLength(0);
	});
	it('loads on direct workbench navigation', async () => {
		await render('/agent/cron');
		expect(paths()).toEqual(['config', 'sessions?limit=5', 'skills', 'jobs']);
	});
	it('does not match similar non-workbench paths', async () => {
		await render('/agent-other');
		expect(paths()).toEqual(['config']);
	});
	it('cancels on leave and ignores stale responses after reentry', async () => {
		await render();
		let finish!: (value: Response) => void;
		vi.mocked(fetch).mockImplementationOnce(
			() =>
				new Promise((resolve) => {
					finish = resolve;
				})
		);
		await navigate('/agent');
		const signal = vi.mocked(fetch).mock.calls[1][1]?.signal;
		await navigate('/');
		expect(signal?.aborted).toBe(true);
		await navigate('/agent');
		finish(response({ data: [{ id: 'old', title: 'STALE' }] }));
		await settle();
		expect(target.textContent).not.toContain('STALE');
		expect(target.textContent).toContain('Recent session');
	});
	it('cancels all pending requests on destruction', async () => {
		await render();
		vi.mocked(fetch).mockImplementation(() => new Promise(() => {}));
		await navigate('/agent');
		await unmount(component!);
		component = undefined;
		expect(
			vi
				.mocked(fetch)
				.mock.calls.slice(1)
				.every(([, init]) => init?.signal?.aborted)
		).toBe(true);
	});
	it('does not duplicate requests while details are pending', async () => {
		await render();
		vi.mocked(fetch).mockImplementation(() => new Promise(() => {}));
		await navigate('/agent');
		await navigate('/agent/skills');
		await navigate('/agent/cron');
		expect(paths()).toEqual(['config', 'sessions?limit=5', 'skills', 'jobs']);
	});
	it('disabled workbench never fetches details', async () => {
		vi.mocked(fetch).mockResolvedValue(response({ enabled: false }));
		await render('/agent');
		expect(paths()).toEqual(['config']);
		expect(target.querySelector('nav')).toBeNull();
	});
	it('aborts pending config on destruction without follow-up requests', async () => {
		let finish!: (value: Response) => void;
		vi.mocked(fetch).mockImplementation(
			() =>
				new Promise((resolve) => {
					finish = resolve;
				})
		);
		await render('/agent');
		const signal = vi.mocked(fetch).mock.calls[0][1]?.signal;
		await unmount(component!);
		component = undefined;
		expect(signal?.aborted).toBe(true);
		finish(response({ enabled: true }));
		await settle();
		expect(paths()).toEqual(['config']);
	});
	it.each([401, 403, 503])('config failure %s leaves chat unaffected', async (status) => {
		vi.mocked(fetch).mockResolvedValue(response({}, status));
		await render('/agent');
		expect(paths()).toEqual(['config']);
		expect(target.querySelector('nav')).toBeNull();
	});
	it('detail failures keep navigation available without invented counts or polling', async () => {
		await render();
		vi.mocked(fetch).mockResolvedValue(response({}, 503));
		await navigate('/agent');
		expect(target.querySelectorAll('nav a')).toHaveLength(4);
		expect(target.querySelectorAll('a span')).toHaveLength(0);
		await navigate('/agent/skills');
		expect(paths()).toHaveLength(4);
	});
	it('config resolving after route departure never starts details', async () => {
		let finish!: (value: Response) => void;
		vi.mocked(fetch).mockImplementation(
			() =>
				new Promise((resolve) => {
					finish = resolve;
				})
		);
		await render('/agent');
		await navigate('/');
		finish(response({ enabled: true }));
		await settle();
		expect(paths()).toEqual(['config']);
	});
});
