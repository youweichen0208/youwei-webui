<script lang="ts">
	import type { OutputItem } from '../Messages/structuredOutput';
	import { parseFinance } from './finance';
	import FinanceCard from './FinanceCard.svelte';
	export let item: OutputItem;
	export let result: OutputItem | undefined = undefined;
	export let done = true;
	$: text =
		typeof result?.output === 'string'
			? result.output
			: Array.isArray(result?.output)
				? result.output.map((p) => (typeof p?.text === 'string' ? p.text : '')).join('')
				: '';
	$: card = result ? parseFinance(item.name ?? '', text) : null;
	$: failed = (() => {
		try {
			return !!JSON.parse(text).error;
		} catch {
			return false;
		}
	})();
	$: state = result
		? failed
			? '失败'
			: '完成'
		: done || ['interrupted', 'failed', 'cancelled'].includes(item.status ?? '')
			? '已中断'
			: '执行中';
	$: args =
		typeof item.arguments === 'string' ? item.arguments : JSON.stringify(item.arguments ?? {});
</script>

<div class="my-2 min-w-0" aria-label="Hermes 工具过程">
	<details class="text-sm">
		<summary class="cursor-pointer break-words text-gray-600 dark:text-gray-400"
			>{item.name ?? 'Hermes 工具'} · <span role="status">{state}</span></summary
		>
		<div class="mt-2 space-y-2 rounded-lg bg-gray-100 p-3 dark:bg-gray-900">
			<p class="text-xs text-gray-500">由 Hermes 执行</p>
			<pre class="max-h-48 overflow-auto whitespace-pre-wrap break-all text-xs">{args?.slice(
					0,
					10000
				)}</pre>
			{#if text}<pre
					class="max-h-64 overflow-auto whitespace-pre-wrap break-all text-xs">{text.slice(
						0,
						20000
					)}{text.length > 20000 ? '\n…详情预览已截短；卡片使用完整结果。' : ''}</pre>{/if}
		</div>
	</details>
	{#if card}<FinanceCard {card} />{/if}
</div>
