<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import ScheduleDraft from '$lib/components/agent/ScheduleDraft.svelte';
	import { hermes, type Job } from '$lib/apis/hermes';
	let jobs: Job[] = [];
	let selected: Job | null = null;
	let editing = '';
	let name = '';
	let schedule = '';
	let prompt = '';
	let deliver = 'local';
	let busy = false;
	let loading = true;
	let error = '';
	let notice = '';
	async function refresh() {
		jobs = (await hermes('jobs?include_disabled=true')).jobs ?? [];
		if (selected) selected = jobs.find((j) => j.id === selected?.id) ?? null;
	}
	function edit(job: Job) {
		editing = job.id;
		name = job.name;
		schedule = job.schedule?.expr ?? job.schedule_display;
		prompt = job.prompt;
		deliver = job.deliver || 'local';
	}
	function clear() {
		editing = '';
		name = schedule = prompt = '';
		deliver = 'local';
	}
	async function save() {
		busy = true;
		error = '';
		notice = '';
		try {
			const result = await hermes(
				editing ? `jobs/${encodeURIComponent(editing)}` : 'jobs',
				{ name, schedule, prompt, deliver },
				editing ? 'PATCH' : 'POST'
			);
			selected = result.job;
			await refresh();
			clear();
			notice = '定时任务已保存到 Hermes';
		} catch (e) {
			error = (e as Error).message;
		} finally {
			busy = false;
		}
	}
	async function action(job: Job, action: string) {
		if (
			action === 'run' &&
			!confirm(`立即运行「${job.name}」？这会调用模型并可能向 ${job.deliver || 'local'} 投递结果。`)
		)
			return;
		if (action === 'delete' && !confirm(`删除定时任务「${job.name}」？`)) return;
		busy = true;
		error = '';
		notice = '';
		try {
			const path = `jobs/${encodeURIComponent(job.id)}`;
			if (action === 'delete') await hermes(path, undefined, 'DELETE');
			else await hermes(`${path}/${action}`, {});
			await refresh();
			notice = action === 'run' ? '已请求运行；实际执行结果以 Hermes 状态为准' : '任务已更新';
		} catch (e) {
			error = (e as Error).message;
		} finally {
			busy = false;
		}
	}
	function date(value?: string) {
		return value ? new Date(value).toLocaleString() : '—';
	}
	onMount(async () => {
		try {
			await refresh();
			selected = jobs.find((j) => j.id === $page.url.searchParams.get('job')) ?? selected;
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	});
</script>

{#if error}<div class="aw-error" role="alert">{error}</div>{/if}
<div class="aw-split cron-layout">
	<main class="aw-main">
		<div style="max-width:820px;margin:auto">
			<h1 class="aw-title">定时任务</h1>
			<p class="aw-muted" style="margin-bottom:20px">
				由 Hermes 调度并投递。时间按助手配置的时区解释。
			</p>
			<ScheduleDraft
				on:draft={(e) => {
					editing = '';
					name = e.detail.name;
					schedule = e.detail.schedule;
					prompt = e.detail.prompt;
					deliver = e.detail.deliver;
				}}
			/>
			<form class="aw-card aw-stack" on:submit|preventDefault={save}>
				<strong>{editing ? '编辑任务' : '创建任务'}</strong>
				<label
					><span class="aw-label">任务名称</span><input
						class="aw-input"
						bind:value={name}
						required
						maxlength="200"
						placeholder="美股收盘摘要"
					/></label
				>
				<label
					><span class="aw-label">提示词</span><textarea
						class="aw-input"
						bind:value={prompt}
						required
						rows="3"
						maxlength="32000"
						placeholder="希望 Hermes 定期完成什么？"
					></textarea></label
				>
				<div class="form-grid">
					<label
						><span class="aw-label">Cron 表达式或 Hermes 时间格式</span><input
							class="aw-input"
							bind:value={schedule}
							required
							placeholder="0 9 * * 1-5"
							maxlength="200"
						/></label
					><label
						><span class="aw-label">投递目标</span><input
							class="aw-input"
							bind:value={deliver}
							required
							placeholder="local 或 telegram:chat_id"
							maxlength="200"
						/></label
					>
				</div>
				<p class="aw-muted">
					创建前请确认时间和接收方。local 仅在 Hermes 本地保存；外部投递需要已配置的消息平台。
				</p>
				<div class="aw-row">
					<button class="aw-btn aw-primary" disabled={busy}
						>{busy ? '保存中…' : editing ? '保存修改' : '创建任务'}</button
					>{#if editing}<button type="button" class="aw-btn" on:click={clear}>取消编辑</button
						>{/if}<button
						type="button"
						class="aw-btn"
						disabled={busy}
						on:click={() => refresh().catch((e) => (error = e.message))}>刷新</button
					>
				</div>
				{#if notice}<p role="status" style="color:#257a52">{notice}</p>{/if}
			</form>
			<div class="jobs">
				<div class="job-row heading">
					<span>任务 / 时间</span><span>投递</span><span>下次运行</span><span>状态</span>
				</div>
				{#each jobs as job}<button
						class="job-row"
						class:aw-selected={selected?.id === job.id}
						class:paused={!job.enabled}
						on:click={() => (selected = job)}
						><span><strong>{job.name}</strong><small>{job.schedule_display}</small></span><span
							>{job.deliver || 'local'}</span
						><span>{date(job.next_run_at)}</span><span>{job.enabled ? '已启用' : '已暂停'}</span
						></button
					>{/each}
			</div>
			{#if !jobs.length}<div class="aw-empty">
					{loading ? '正在读取任务…' : '还没有定时任务'}
				</div>{/if}
			<div class="aw-muted" style="margin-top:18px">
				Open WebUI 的 <a class="underline" href="/automations">自动化</a> 与
				<a class="underline" href="/calendar">日历</a> 保留原有任务；本页管理 Hermes 任务，不重复创建第二套调度。
			</div>
		</div>
	</main>
	<aside class="aw-aside">
		{#if selected}<h2 class="aw-title">{selected.name}</h2>
			<p class="aw-muted">{selected.schedule_display} · {selected.deliver || 'local'}</p>
			<pre class="aw-card" style="margin-top:20px">{selected.prompt}</pre>
			<span class="aw-label">最近一次运行</span>
			<p>{date(selected.last_run_at)}</p>
			<p class="aw-muted">{selected.last_status || '尚未运行'}</p>
			{#if selected.last_error}<div class="aw-error">{selected.last_error}</div>{/if}
			<div class="aw-stack" style="margin-top:24px">
				<button class="aw-btn aw-primary" disabled={busy} on:click={() => action(selected!, 'run')}
					>立即运行</button
				><button class="aw-btn" disabled={busy} on:click={() => edit(selected!)}>编辑</button
				><button
					class="aw-btn"
					disabled={busy}
					on:click={() => action(selected!, selected!.enabled ? 'pause' : 'resume')}
					>{selected.enabled ? '暂停任务' : '恢复任务'}</button
				><button class="aw-btn" disabled={busy} on:click={() => action(selected!, 'delete')}
					>删除任务</button
				>
			</div>{:else}<p class="aw-muted">选择任务查看提示词和运行状态</p>{/if}
	</aside>
</div>

<style>
	@media (max-width: 900px) {
		.cron-layout {
			flex-direction: column;
			height: auto;
		}
		.cron-layout :global(.aw-aside) {
			display: block;
			width: 100%;
			border-left: 0;
			border-top: 1px solid var(--aw-border);
		}
	}

	.form-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 12px;
	}
	.jobs {
		border: 1px solid var(--aw-border);
		border-radius: 12px;
		overflow: hidden;
	}
	.job-row {
		width: 100%;
		display: grid;
		grid-template-columns: 2fr 1fr 1.5fr 72px;
		gap: 12px;
		padding: 12px 16px;
		text-align: left;
		border-bottom: 1px solid var(--aw-border);
		font-size: 12px;
		overflow-wrap: anywhere;
	}
	.heading {
		background: var(--aw-subtle);
		color: var(--aw-muted);
	}
	small {
		display: block;
		color: var(--aw-muted);
		margin-top: 4px;
	}
	.paused {
		opacity: 0.55;
	}
	@media (max-width: 640px) {
		.form-grid {
			grid-template-columns: 1fr;
		}
		.job-row {
			grid-template-columns: 2fr 1fr;
		}
	}
</style>
