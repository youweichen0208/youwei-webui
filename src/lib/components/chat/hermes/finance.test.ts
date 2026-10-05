import { describe, expect, it } from 'vitest';
import { parseFinance, secLink } from './finance';
import { buildOutputDisplayItems } from '../Messages/structuredOutput';

const base = {
	symbol: 'AAPL',
	source: 'Yahoo Finance via yfinance',
	fetched_at: '2026-10-06T00:00:00Z',
	pit: false,
	warnings: [],
	currency: 'USD',
	period: { start: '2026-10-01', end_exclusive: '2026-10-03' },
	adjustment: 'Separate OHLC and adjusted_close'
};
export const prices = {
	...base,
	rows: [
		{
			date: '2026-10-01',
			open: 100,
			high: 102,
			low: 99,
			close: 101,
			adjusted_close: 100,
			volume: 1000
		},
		{
			date: '2026-10-02',
			open: 101,
			high: 103,
			low: 100,
			close: 102,
			adjusted_close: null,
			volume: 2000
		}
	]
};
describe('verified financial data', () => {
	it('retains price gaps, source and non-PIT context', () => {
		const card = parseFinance('trading_price_history', JSON.stringify(prices));
		expect(card?.kind).toBe('prices');
		if (card?.kind === 'prices') expect(card.data.rows[1].adjusted_close).toBeNull();
	});
	it('does not turn malformed or nonfinancial output into a chart', () => {
		expect(parseFinance('web_search', JSON.stringify(prices))).toBeNull();
		expect(parseFinance('trading_price_history', '{truncated')?.kind).toBe('error');
		expect(
			parseFinance('trading_price_history', JSON.stringify({ ...prices, pit: true }))?.kind
		).toBe('error');
		expect(
			parseFinance(
				'trading_price_history',
				JSON.stringify({ ...prices, rows: [...prices.rows].reverse() })
			)?.kind
		).toBe('error');
	});
	it('shows missing indicators with reasons and rejects incomplete metrics', () => {
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
		expect(
			parseFinance('trading_indicators', JSON.stringify({ ...base, metrics, sample_size: 2 }))?.kind
		).toBe('indicators');
		expect(parseFinance('trading_indicators', JSON.stringify({ ...base, metrics: {} }))?.kind).toBe(
			'error'
		);
	});
	it('deduplicates rich tools and keeps their results attached after serialization', () => {
		const call = { type: 'hermes:tool_call', call_id: 'c1', name: 'trading_price_history' };
		const result = {
			type: 'hermes:tool_result',
			call_id: 'c1',
			output: [{ type: 'input_text', text: JSON.stringify(prices) }]
		};
		const items = buildOutputDisplayItems(JSON.parse(JSON.stringify([call, call, result, result])));
		expect(items).toHaveLength(1);
		expect(items[0].type).toBe('hermes_tool');
	});
	it('validates SEC filing links and preserves missing financial facts', () => {
		const metric = {
			value: 123456789,
			reason: null,
			unit: 'USD',
			filed: '2026-08-01',
			source_url: 'https://www.sec.gov/Archives/edgar/data/320193/fixture-index.html'
		};
		const financials = {
			...base,
			frequency: 'quarterly',
			periods: [
				{
					end: '2026-06-30',
					metrics: { revenue: metric, assets: { value: null, reason: 'not_available' } }
				}
			]
		};
		expect(parseFinance('trading_financials', JSON.stringify(financials))?.kind).toBe('financials');
		expect(secLink('javascript:alert(1)')).toBeNull();
		expect(secLink('https://www.sec.gov.evil.test/Archives/edgar/data/1')).toBeNull();
		expect(
			parseFinance(
				'trading_financials',
				JSON.stringify({
					...financials,
					periods: [
						{
							end: '2026-06-30',
							metrics: { revenue: { ...metric, source_url: 'javascript:alert(1)' } }
						}
					]
				})
			)?.kind
		).toBe('error');
	});
	it('accepts the supported maximum price rows but rejects oversized payloads', () => {
		const rows = Array.from({ length: 1830 }, (_, i) => ({
			...prices.rows[0],
			date: new Date(Date.UTC(2021, 0, 1 + i)).toISOString().slice(0, 10)
		}));
		expect(
			parseFinance(
				'trading_price_history',
				JSON.stringify({
					...prices,
					period: { start: '2021-01-01', end_exclusive: '2027-01-01' },
					rows
				})
			)?.kind
		).toBe('prices');
		expect(parseFinance('trading_price_history', 'x'.repeat(512 * 1024 + 1))?.kind).toBe('error');
	});
});

it('keeps warmed indicators separate from the requested analysis period', () => {
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
	const analysis = {
		...prices,
		metrics,
		sample_size: 2,
		indicator_history: {
			start: '2025-09-01',
			end_exclusive: '2026-10-03',
			first: '2025-09-02',
			last: '2026-10-02',
			sample_size: 275
		}
	};
	const card = parseFinance('trading_analysis', JSON.stringify(analysis));
	expect(card?.kind).toBe('prices');
	expect(parseFinance('trading_analysis', JSON.stringify({ ...analysis, metrics: {} }))?.kind).toBe(
		'error'
	);
	expect(
		parseFinance('trading_analysis', JSON.stringify({ ...analysis, sample_size: 275 }))?.kind
	).toBe('error');
	expect(
		parseFinance(
			'trading_analysis',
			JSON.stringify({
				...analysis,
				indicator_history: { ...analysis.indicator_history, end_exclusive: '2026-10-04' }
			})
		)?.kind
	).toBe('error');
});
