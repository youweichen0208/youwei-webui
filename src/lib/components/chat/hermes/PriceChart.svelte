<script lang="ts">
	import { onMount } from 'svelte';
	import type { Chart } from 'chart.js';
	import type { PriceRow } from './finance';
	export let rows: PriceRow[];
	export let field: 'close' | 'adjusted_close' = 'adjusted_close';
	let canvas: HTMLCanvasElement;
	let chart: Chart<'line'> | undefined;
	let error = '';
	$: if (chart) {
		chart.data.labels = rows.map((r) => r.date);
		chart.data.datasets[0].data = rows.map((r) => r[field]);
		chart.data.datasets[0].label = field === 'close' ? '收盘价 USD' : '调整收盘价 USD';
		chart.update('none');
	}
	onMount(() => {
		let alive = true;
		let started = false;
		const load = async () => {
			if (started) return;
			started = true;
			try {
				const { default: Chart } = await import('chart.js/auto');
				if (!alive) return;
				chart = new Chart(canvas, {
					type: 'line',
					data: {
						labels: rows.map((r) => r.date),
						datasets: [
							{
								label: field === 'close' ? '收盘价 USD' : '调整收盘价 USD',
								data: rows.map((r) => r[field]),
								borderColor: '#0d9488',
								backgroundColor: '#0d9488',
								pointRadius: 0,
								borderWidth: 2,
								spanGaps: false
							}
						]
					},
					options: {
						responsive: true,
						maintainAspectRatio: false,
						animation: false,
						plugins: { legend: { display: false } },
						scales: {
							x: { ticks: { maxTicksLimit: 6, color: '#94a3b8' }, grid: { display: false } },
							y: { ticks: { color: '#94a3b8' }, grid: { color: '#94a3b822' } }
						}
					}
				});
			} catch {
				if (alive) error = '图表加载失败，仍可查看下方数据表。';
			}
		};
		const observer =
			typeof IntersectionObserver === 'undefined'
				? undefined
				: new IntersectionObserver((entries) => {
						if (entries.some((e) => e.isIntersecting)) {
							observer?.disconnect();
							void load();
						}
					});
		if (observer) observer.observe(canvas);
		else void load();
		return () => {
			alive = false;
			observer?.disconnect();
			chart?.destroy();
		};
	});
</script>

<div class="relative h-56 w-full">
	<canvas bind:this={canvas} aria-label="历史日线价格图；详细数值见数据表"></canvas>
	{#if error}<p class="absolute inset-0 p-4 text-sm">{error}</p>{/if}
</div>
