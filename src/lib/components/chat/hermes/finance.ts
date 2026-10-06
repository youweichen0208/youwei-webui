// Display the tool's values; never calculate, repair, or infer missing financial data.
export type Metric = {
	value: number | null;
	reason: string | null;
	unit?: string;
	filed?: string;
	source_url?: string;
	tag?: string;
};
export type PriceRow = {
	date: string;
	open: number | null;
	high: number | null;
	low: number | null;
	close: number | null;
	adjusted_close: number | null;
	volume: number | null;
};
type Base = {
	symbol: string;
	source: string;
	fetched_at: string;
	pit: false;
	warnings: string[];
	period: Record<string, string | null>;
};
export type FinanceCard =
	| {
			kind: 'prices';
			data: Base & {
				rows: PriceRow[];
				currency: string;
				adjustment: string;
				metrics?: Record<string, Metric>;
				indicator_history?: { first: string; last: string; sample_size: number };
			};
	  }
	| { kind: 'indicators'; data: Base & { metrics: Record<string, Metric>; sample_size: number } }
	| {
			kind: 'financials';
			data: Base & {
				frequency: string;
				periods: { end: string; metrics: Record<string, Metric> }[];
			};
	  }
	| { kind: 'error'; message: string };

export const metricNames: Record<string, string> = {
	sma20: 'SMA 20',
	sma50: 'SMA 50',
	sma200: 'SMA 200',
	rsi14: 'RSI 14',
	period_return: '区间收益',
	annualized_volatility: '年化波动率',
	max_drawdown: '最大回撤',
	revenue: '营业收入',
	net_income: '净利润',
	assets: '资产',
	liabilities: '负债',
	operating_cash_flow: '经营现金流'
};
const indicators = [
	'sma20',
	'sma50',
	'sma200',
	'rsi14',
	'period_return',
	'annualized_volatility',
	'max_drawdown'
];
const tools = new Set([
	'trading_analysis',
	'trading_price_history',
	'trading_indicators',
	'trading_financials'
]);
const object = (v: unknown): v is Record<string, any> =>
	!!v && typeof v === 'object' && !Array.isArray(v);
const date = (v: unknown): v is string =>
	typeof v === 'string' &&
	/^\d{4}-\d{2}-\d{2}$/.test(v) &&
	Number.isFinite(Date.parse(v)) &&
	new Date(v).toISOString().slice(0, 10) === v;
const number = (v: unknown) => v === null || (typeof v === 'number' && Number.isFinite(v));
const metric = (v: unknown): v is Metric =>
	object(v) &&
	number(v.value) &&
	(v.value === null ? typeof v.reason === 'string' && !!v.reason : v.reason === null);

export function secLink(value: unknown): string | null {
	if (typeof value !== 'string') return null;
	try {
		const url = new URL(value);
		return url.protocol === 'https:' &&
			url.hostname === 'www.sec.gov' &&
			!url.username &&
			!url.password &&
			!url.port &&
			url.pathname.startsWith('/Archives/edgar/data/')
			? url.href
			: null;
	} catch {
		return null;
	}
}

export function parseFinance(tool: string, text: string): FinanceCard | null {
	if (!tools.has(tool)) return null;
	const invalid: FinanceCard = {
		kind: 'error',
		message: '完整金融数据不可用，请展开工具详情查看错误或截短信息。'
	};
	if (new TextEncoder().encode(text).length > 512 * 1024) return invalid;
	try {
		const d = JSON.parse(text);
		if (!object(d)) return invalid;
		if (typeof d.error === 'string') return { kind: 'error', message: d.error.slice(0, 300) };
		if (
			typeof d.symbol !== 'string' ||
			!/^[A-Z][A-Z0-9.-]{0,14}$/.test(d.symbol) ||
			typeof d.source !== 'string' ||
			typeof d.fetched_at !== 'string' ||
			!Number.isFinite(Date.parse(d.fetched_at)) ||
			d.pit !== false ||
			!Array.isArray(d.warnings) ||
			!d.warnings.every((w: unknown) => typeof w === 'string') ||
			!object(d.period)
		)
			return invalid;
		if (tool === 'trading_price_history' || tool === 'trading_analysis') {
			if (
				d.currency !== 'USD' ||
				typeof d.adjustment !== 'string' ||
				!date(d.period.start) ||
				!date(d.period.end_exclusive) ||
				!Array.isArray(d.rows) ||
				!d.rows.length ||
				d.rows.length > 1830 ||
				!d.rows.every(
					(r: unknown, i: number) =>
						object(r) &&
						date(r.date) &&
						r.date >= d.period.start &&
						r.date < d.period.end_exclusive &&
						(i === 0 || r.date > d.rows[i - 1].date) &&
						['open', 'high', 'low', 'close', 'adjusted_close', 'volume'].every((k) => number(r[k]))
				)
			)
				return invalid;
			if (
				(tool === 'trading_analysis' ||
					d.metrics !== undefined ||
					d.indicator_history !== undefined) &&
				(!object(d.metrics) ||
					Object.keys(d.metrics).length !== indicators.length ||
					!indicators.every((k) => metric(d.metrics[k])) ||
					d.sample_size !== d.rows.length ||
					!object(d.indicator_history) ||
					!date(d.indicator_history.start) ||
					!date(d.indicator_history.first) ||
					!date(d.indicator_history.last) ||
					d.indicator_history.start > d.period.start ||
					d.indicator_history.first < d.indicator_history.start ||
					d.indicator_history.first > d.rows[0].date ||
					d.indicator_history.last !== d.rows[d.rows.length - 1].date ||
					d.indicator_history.end_exclusive !== d.period.end_exclusive ||
					!Number.isInteger(d.indicator_history.sample_size) ||
					d.indicator_history.sample_size < d.sample_size ||
					d.indicator_history.sample_size > 1830)
			)
				return invalid;
			return { kind: 'prices', data: d as Extract<FinanceCard, { kind: 'prices' }>['data'] };
		}
		if (tool === 'trading_indicators') {
			if (
				!object(d.metrics) ||
				Object.keys(d.metrics).length !== indicators.length ||
				!indicators.every((k) => metric(d.metrics[k])) ||
				!Number.isInteger(d.sample_size) ||
				d.sample_size < 0 ||
				d.sample_size > 1830
			)
				return invalid;
			return {
				kind: 'indicators',
				data: d as Extract<FinanceCard, { kind: 'indicators' }>['data']
			};
		}
		if (
			!['quarterly', 'annual'].includes(d.frequency) ||
			!Array.isArray(d.periods) ||
			d.periods.length > (d.frequency === 'quarterly' ? 8 : 5) ||
			!d.periods.every(
				(p: unknown) =>
					object(p) &&
					date(p.end) &&
					object(p.metrics) &&
					Object.keys(p.metrics).length <= 20 &&
					Object.values(p.metrics).every(
						(m) =>
							metric(m) &&
							(m.value === null || (m.unit === 'USD' && date(m.filed) && !!secLink(m.source_url)))
					)
			)
		)
			return invalid;
		return { kind: 'financials', data: d as Extract<FinanceCard, { kind: 'financials' }>['data'] };
	} catch {
		return invalid;
	}
}

export function formatValue(value: number | null, name = ''): string {
	if (value === null) return '—';
	return ['period_return', 'annualized_volatility', 'max_drawdown'].includes(name)
		? new Intl.NumberFormat('zh-CN', { style: 'percent', maximumFractionDigits: 2 }).format(value)
		: new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(value);
}
