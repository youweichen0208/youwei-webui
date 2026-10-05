<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { hermes, type Session, type Job } from '$lib/apis/hermes';
	let enabled = false;
	let sessions: Session[] = [];
	let skills: number | null = null;
	let jobs: number | null = null;
	$: links = [
		['/agent', 'Agent 对话', null],
		['/agent/skills', '技能库', skills],
		['/agent/cron', '定时任务', jobs],
		['/agent/gateway', '消息网关', null]
	];
	onMount(() => {
		const configRequest = new AbortController();
		let detailsRequest: AbortController | undefined;
		let inWorkbench = false;

		const clearDetails = () => {
			detailsRequest?.abort();
			detailsRequest = undefined;
			sessions = [];
			skills = null;
			jobs = null;
		};
		const loadDetails = async () => {
			// Keep the controller after completion: one load per workbench visit,
			// including failures. Route updates within the workbench do not retry.
			if (!enabled || !inWorkbench || detailsRequest) return;
			const request = new AbortController();
			detailsRequest = request;
			const results = await Promise.allSettled([
				hermes('sessions?limit=5', undefined, undefined, undefined, request.signal),
				hermes('skills', undefined, undefined, undefined, request.signal),
				hermes('jobs', undefined, undefined, undefined, request.signal)
			]);
			if (request.signal.aborted || detailsRequest !== request) return;
			if (results[0].status === 'fulfilled') sessions = results[0].value.data ?? [];
			if (results[1].status === 'fulfilled') skills = results[1].value.data?.length ?? 0;
			if (results[2].status === 'fulfilled')
				jobs = results[2].value.jobs?.filter((j: Job) => j.enabled).length ?? 0;
		};
		const unsubscribe = page.subscribe(({ url }) => {
			inWorkbench = url.pathname === '/agent' || url.pathname.startsWith('/agent/');
			if (inWorkbench) void loadDetails();
			else clearDetails();
		});
		void hermes('config', undefined, undefined, undefined, configRequest.signal)
			.then((config) => {
				if (configRequest.signal.aborted) return;
				enabled = config.enabled;
				void loadDetails();
			})
			.catch(() => {
				/* Existing chat navigation remains available when Hermes is offline. */
			});
		return () => {
			unsubscribe();
			configRequest.abort();
			clearDetails();
		};
	});
</script>

{#if enabled}
	<nav class="px-3 py-3" aria-label="Agent 工作台">
		<div class="flex items-center justify-between text-xs text-gray-500 mb-2">
			Agent 工作台 <span class="border rounded px-1 text-[10px]">hermes</span>
		</div>
		{#each links as [url, label, count]}
			<a
				href={String(url)}
				class="flex justify-between rounded-lg px-2 py-1.5 text-[13px] hover:bg-gray-100 dark:hover:bg-gray-900"
				class:bg-gray-100={$page.url.pathname === url}
				class:dark:bg-gray-800={$page.url.pathname === url}
				>{label}{#if count !== null}<span class="text-gray-400">{count}</span>{/if}</a
			>
		{/each}
		{#if sessions.length}<div class="text-[11px] text-gray-500 mt-4 mb-2">
				最近会话 · 跨平台
			</div>{/if}
		{#each sessions as session}<a
				class="flex gap-2 items-center py-1.5 text-xs truncate"
				href="/agent?session={encodeURIComponent(session.id)}"
				><span class="border rounded px-1 text-[10px] font-mono">{session.source ?? 'Web'}</span
				><span class="truncate">{session.title || '未命名会话'}</span></a
			>{/each}
	</nav>
{/if}
