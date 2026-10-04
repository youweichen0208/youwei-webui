<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { showSidebar } from '$lib/stores';
	import { hermes } from '$lib/apis/hermes';
	import Sidebar from '$lib/components/icons/Sidebar.svelte';
	import '$lib/components/agent/workbench.css';
	let ready = false;
	let error = '';
	let model = '';
	const links = [
		['/agent', 'Agent 对话'],
		['/agent/skills', '技能库'],
		['/agent/cron', '定时任务'],
		['/agent/gateway', '消息网关']
	];
	onMount(async () => {
		try {
			const config = await hermes('config');
			if (!config.enabled) {
				error = '工作台尚未启用，或当前账号不是工作台所有者。';
				return;
			}
			ready = true;
			const models = await hermes('models');
			model = models.data?.[0]?.id ?? '';
		} catch (e) {
			error = (e as Error).message;
		}
	});
</script>

<svelte:head><title>Agent 工作台 · Hermes</title></svelte:head>
<div class="agent-workbench">
	<header class="aw-header">
		<div class="aw-row">
			<button aria-label="切换侧栏" on:click={() => showSidebar.update((v) => !v)}
				><Sidebar className="size-5" /></button
			><span class="aw-muted">Agent 工作台 /</span><strong
				>{links.find(([url]) => url === $page.url.pathname)?.[1] ?? 'Hermes'}</strong
			>
		</div>
		{#if model}<span class="aw-pill">{model}</span>{/if}
	</header>
	<nav class="aw-tabs" aria-label="Agent 工作台">
		{#each links as [url, label]}<a
				href={url}
				aria-current={$page.url.pathname === url ? 'page' : undefined}>{label}</a
			>{/each}
	</nav>
	{#if error}<div class="aw-error" role="alert">{error}</div>{/if}
	<div class="aw-body">
		{#if ready}<slot />{:else if !error}<div class="aw-empty">正在连接 Hermes…</div>{/if}
	</div>
</div>
