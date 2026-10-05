import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('$lib/constants', () => ({ WEBUI_BASE_URL: '', WEBUI_API_BASE_URL: '/api/v1' }));
vi.mock('$lib/utils', () => ({ convertOpenApiToToolPayload: vi.fn(), resolveSchema: vi.fn() }));
vi.mock('./openai', () => ({ getOpenAIModelsDirect: vi.fn() }));

import { getModels } from './index';
import { getOpenAIModelsDirect } from './openai';
import { loadInitialState } from './startup';

function deferred<T>() {
	let resolve!: (value: T) => void;
	let reject!: (reason: unknown) => void;
	const promise = new Promise<T>((yes, no) => {
		resolve = yes;
		reject = no;
	});
	return { promise, resolve, reject };
}
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
afterEach(() => {
	vi.unstubAllGlobals();
	vi.restoreAllMocks();
});

describe('initial page requests', () => {
	it('starts session validation while public configuration is still pending', async () => {
		const config = deferred<Response>();
		const fetcher = vi.fn((url: string) =>
			url === '/api/config' ? config.promise : Promise.resolve(json({ id: 'owner' }))
		);
		vi.stubGlobal('fetch', fetcher);
		const pending = loadInitialState('test-token');
		expect(fetcher.mock.calls.map(([url]) => url)).toEqual(['/api/config', '/api/v1/auths/']);
		config.resolve(json({ name: 'Open WebUI' }));
		expect((await pending).session.user.id).toBe('owner');
	});
	it('does not request a session for anonymous visitors', async () => {
		const fetcher = vi.fn().mockResolvedValue(json({ status: true }));
		vi.stubGlobal('fetch', fetcher);
		expect((await loadInitialState(null)).session.user).toBeNull();
		expect(fetcher).toHaveBeenCalledTimes(1);
	});
	it('preserves public configuration when session validation rejects', async () => {
		vi.spyOn(console, 'error').mockImplementation(() => {});
		vi.stubGlobal(
			'fetch',
			vi.fn((url: string) =>
				Promise.resolve(
					url === '/api/config' ? json({ status: true }) : json({ detail: 'expired' }, 401)
				)
			)
		);
		expect(await loadInitialState('expired')).toEqual({
			backendConfig: { status: true },
			session: { user: null, error: 'expired' }
		});
	});
	it('propagates configuration errors while handling concurrent session failures', async () => {
		vi.spyOn(console, 'error').mockImplementation(() => {});
		vi.stubGlobal(
			'fetch',
			vi.fn().mockImplementation(() => Promise.resolve(json({ detail: 'unavailable' }, 503)))
		);
		await expect(loadInitialState('test-token')).rejects.toEqual({ detail: 'unavailable' });
	});
});

describe('model loading with fresh settings', () => {
	it('fetches server models immediately but waits for settings before direct connections', async () => {
		const settings = deferred<object | null>();
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ data: [{ id: 'server' }] })));
		vi.mocked(getOpenAIModelsDirect).mockResolvedValue({ data: [{ id: 'direct' }] });
		let completed = false;
		const pending = getModels('test-token', settings.promise).then((result) => {
			completed = true;
			return result;
		});
		expect(fetch).toHaveBeenCalledTimes(1);
		await new Promise((resolve) => setTimeout(resolve, 0));
		expect(completed).toBe(false);
		expect(getOpenAIModelsDirect).not.toHaveBeenCalled();
		settings.resolve({
			OPENAI_API_BASE_URLS: ['https://fixture.invalid'],
			OPENAI_API_KEYS: ['fixture-key'],
			OPENAI_API_CONFIGS: { 0: { enable: true } }
		});
		expect((await pending).map((model) => model.id)).toEqual(['server', 'direct']);
		expect(getOpenAIModelsDirect).toHaveBeenCalledWith('https://fixture.invalid', 'fixture-key');
	});
	it('keeps direct connections disabled when fresh configuration disallows them', async () => {
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ data: [{ id: 'server' }] })));
		expect(await getModels('test-token', Promise.resolve(null))).toEqual([{ id: 'server' }]);
		expect(getOpenAIModelsDirect).not.toHaveBeenCalled();
	});
	it('does not publish models when settings fail before the model response', async () => {
		const response = deferred<Response>();
		const settings = deferred<object | null>();
		vi.stubGlobal('fetch', vi.fn().mockReturnValue(response.promise));
		const pending = getModels('test-token', settings.promise);
		const assertion = expect(pending).rejects.toThrow('settings unavailable');
		settings.reject(new Error('settings unavailable'));
		response.resolve(json({ data: [{ id: 'server' }] }));
		await assertion;
	});
});
