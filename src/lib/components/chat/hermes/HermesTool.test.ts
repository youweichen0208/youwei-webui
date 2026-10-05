import { afterEach, expect, it, vi } from 'vitest';
import { mount, unmount, tick } from 'svelte';
import HermesTool from './HermesTool.svelte';
const instances: ReturnType<typeof mount>[] = [];
afterEach(async () => {
	for (const c of instances.splice(0)) await unmount(c);
	document.body.innerHTML = '';
	vi.unstubAllGlobals();
});
const render = async (props: any) => {
	const target = document.createElement('div');
	document.body.append(target);
	instances.push(mount(HermesTool, { target, props }));
	await tick();
	return target;
};
it('shows interrupted tools without execute or approval controls', async () => {
	const target = await render({
		item: { name: 'youwei_platform', arguments: '{}', status: 'in_progress' },
		done: true
	});
	expect(target.textContent).toContain('已中断');
	expect(target.querySelector('button')).toBeNull();
});
it('restores metrics with missing reasons without fetching or trusting HTML', async () => {
	vi.stubGlobal('fetch', vi.fn());
	const metrics = Object.fromEntries(
		[
			'sma20',
			'sma50',
			'sma200',
			'rsi14',
			'period_return',
			'annualized_volatility',
			'max_drawdown'
		].map((k) => [k, { value: null, reason: 'requires_20_prices' }])
	);
	const props = JSON.parse(
		JSON.stringify({
			item: { name: 'trading_indicators', status: 'completed' },
			result: {
				output: [
					{
						text: JSON.stringify({
							symbol: 'AAPL',
							source: '<img src=x onerror=alert(1)>',
							fetched_at: '2026-10-06T00:00:00Z',
							pit: false,
							warnings: [],
							period: { start: '2026-10-01' },
							metrics,
							sample_size: 2
						})
					}
				]
			},
			done: true
		})
	);
	const target = await render(props);
	expect(target.textContent).toContain('SMA 20');
	expect(target.textContent).toContain('requires_20_prices');
	expect(target.textContent).toContain('非正式时点快照');
	expect(target.querySelector('img')).toBeNull();
	expect(fetch).not.toHaveBeenCalled();
});

it('renders combined analysis and its distinct warmup window after history restore', async () => {
	const metrics = Object.fromEntries(
		[
			'sma20',
			'sma50',
			'sma200',
			'rsi14',
			'period_return',
			'annualized_volatility',
			'max_drawdown'
		].map((k) => [k, { value: 1, reason: null }])
	);
	const data = {
		symbol: 'AAPL',
		source: 'Yahoo Finance',
		fetched_at: '2026-10-06T00:00:00Z',
		pit: false,
		warnings: [],
		currency: 'USD',
		adjustment: 'Adjusted closes',
		period: { start: '2026-10-01', end_exclusive: '2026-10-03' },
		rows: [
			{ date: '2026-10-02', open: 1, high: 1, low: 1, close: 1, adjusted_close: 1, volume: 1 }
		],
		sample_size: 1,
		metrics,
		indicator_history: {
			start: '2025-09-01',
			first: '2025-09-02',
			last: '2026-10-02',
			end_exclusive: '2026-10-03',
			sample_size: 275
		}
	};
	const target = await render({
		item: { name: 'trading_analysis', status: 'completed' },
		result: { output: [{ text: JSON.stringify(data) }] },
		done: true
	});
	expect(target.textContent).toContain('SMA 200');
	expect(target.textContent).toContain('275 个历史样本');
	expect(target.textContent).toContain('数据表 · 1 行');
});
