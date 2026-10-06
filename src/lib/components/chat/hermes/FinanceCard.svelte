<script lang="ts">
	import PriceChart from './PriceChart.svelte';
	import { formatValue, metricNames, secLink, type FinanceCard } from './finance';
	export let card: FinanceCard;
	let field: 'close' | 'adjusted_close' = 'adjusted_close';
	let page = 0;
	$: if (card) page = 0;
</script>

{#if card.kind === 'error'}
	<p role="status" class="my-2 rounded-xl border border-amber-500/30 p-3 text-sm">{card.message}</p>
{:else}
	<section
		class="my-3 min-w-0 rounded-xl border border-gray-200 bg-gray-50/50 p-4 dark:border-gray-700 dark:bg-gray-900/40"
		aria-label={`${card.data.symbol} 金融数据`}
	>
		<div class="mb-3 flex flex-wrap items-center justify-between gap-2">
			<strong
				>{card.data.symbol} · {card.kind === 'prices'
					? '历史行情'
					: card.kind === 'indicators'
						? '技术指标'
						: 'SEC 财务'}</strong
			>
			{#if card.kind === 'prices'}
				<select
					aria-label="价格口径"
					bind:value={field}
					class="rounded-lg border border-gray-300 bg-transparent px-2 py-1 text-sm dark:border-gray-600"
				>
					<option value="adjusted_close">调整收盘价</option><option value="close">收盘价</option>
				</select>
			{/if}
		</div>
		{#if card.kind === 'prices'}
			<p class="mb-2 text-xs text-gray-500">
				{card.data.period.start}（含）至 {card.data.period.end_exclusive}（不含） · USD
			</p>
			<PriceChart rows={card.data.rows} {field} />
			<p class="mt-2 text-xs text-gray-500">{card.data.adjustment}</p>
			{#if card.data.metrics && card.data.indicator_history}
				<p class="my-3 text-xs text-gray-500">
					收益、回撤和波动率对应上方查询区间；SMA / RSI 使用 {card.data.indicator_history.first} 至 {card
						.data.indicator_history.last} 的 {card.data.indicator_history.sample_size} 个历史样本。
				</p>
				<dl class="grid grid-cols-2 gap-3 sm:grid-cols-3">
					{#each Object.entries(card.data.metrics) as [name, m]}<div>
							<dt class="text-xs text-gray-500">{metricNames[name] ?? name}</dt>
							<dd class="mt-1 font-medium tabular-nums">{formatValue(m.value, name)}</dd>
							{#if m.reason}<p class="break-words text-xs text-gray-500">{m.reason}</p>{/if}
						</div>{/each}
				</dl>
			{/if}
			<details class="mt-3 text-sm">
				<summary class="cursor-pointer">数据表 · {card.data.rows.length} 行</summary>
				<div class="overflow-x-auto">
					<table class="mt-2 w-full text-right text-xs">
						<thead
							><tr
								><th class="p-2 text-left">日期</th
								>{#each ['开盘', '最高', '最低', '收盘', '调整收盘', '成交量'] as name}<th
										class="whitespace-nowrap p-2">{name}</th
									>{/each}</tr
							></thead
						>
						<tbody
							>{#each card.data.rows.slice(page * 50, (page + 1) * 50) as row}<tr
									class="border-t border-gray-200 dark:border-gray-700"
									><td class="whitespace-nowrap p-2 text-left">{row.date}</td
									>{#each [row.open, row.high, row.low, row.close, row.adjusted_close, row.volume] as v}<td
											class="p-2">{formatValue(v)}</td
										>{/each}</tr
								>{/each}</tbody
						>
					</table>
				</div>
				{#if card.data.rows.length > 50}<div class="mt-2 flex items-center gap-3">
						<button class="disabled:opacity-40" disabled={page === 0} on:click={() => page--}
							>上一页</button
						><span>{page + 1} / {Math.ceil(card.data.rows.length / 50)}</span><button
							class="disabled:opacity-40"
							disabled={(page + 1) * 50 >= card.data.rows.length}
							on:click={() => page++}>下一页</button
						>
					</div>{/if}
			</details>
		{:else if card.kind === 'indicators'}
			<p class="mb-3 text-xs text-gray-500">
				{card.data.period.start ?? card.data.period.first ?? ''} 至 {card.data.period
					.end_exclusive ??
					card.data.period.last ??
					''} · {card.data.sample_size} 个价格样本
			</p>
			<dl class="grid grid-cols-2 gap-3 sm:grid-cols-3">
				{#each Object.entries(card.data.metrics) as [name, m]}<div>
						<dt class="text-xs text-gray-500">{metricNames[name] ?? name}</dt>
						<dd class="mt-1 font-medium tabular-nums">{formatValue(m.value, name)}</dd>
						{#if m.reason}<p class="break-words text-xs text-gray-500">{m.reason}</p>{/if}
					</div>{/each}
			</dl>
		{:else}
			<p class="mb-2 text-xs text-gray-500">
				{card.data.frequency === 'quarterly' ? '季度' : '年度'} · USD · 使用最新适用申报，缺失季度不推导
			</p>
			<div class="overflow-x-auto">
				<table class="w-full text-left text-sm">
					<thead
						><tr
							><th class="p-2">报告期末</th><th class="p-2">指标</th><th class="p-2">数值</th><th
								class="p-2">申报与来源</th
							></tr
						></thead
					><tbody>
						{#each card.data.periods as period}{#each Object.entries(period.metrics) as [name, m]}<tr
									class="border-t border-gray-200 dark:border-gray-700"
									><td class="whitespace-nowrap p-2">{period.end}</td><td class="p-2"
										>{metricNames[name] ?? name}</td
									><td class="p-2 tabular-nums"
										>{formatValue(m.value)}{#if m.reason}<p class="text-xs text-gray-500">
												{m.reason}
											</p>{/if}</td
									><td class="p-2"
										>{#if secLink(m.source_url)}<a
												href={secLink(m.source_url)}
												target="_blank"
												rel="noopener noreferrer"
												class="text-teal-600 underline dark:text-teal-400">{m.filed} · SEC</a
											>{/if}</td
									></tr
								>{/each}{/each}
					</tbody>
				</table>
			</div>
			{#if !card.data.periods.length}<p class="text-sm">无可用报告期。</p>{/if}
		{/if}
		<footer
			class="mt-4 space-y-1 border-t border-gray-200 pt-3 text-xs text-gray-500 dark:border-gray-700"
		>
			<p>{card.data.source} · 取得时间 {card.data.fetched_at}</p>
			<p>最新取得的历史数据，非正式时点快照。</p>
			{#each card.data.warnings as warning}<p>{warning}</p>{/each}
		</footer>
	</section>
{/if}
