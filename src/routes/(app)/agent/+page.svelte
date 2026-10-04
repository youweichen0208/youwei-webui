<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { page } from '$app/stores';
	import { afterNavigate } from '$app/navigation';
	import { user } from '$lib/stores';
	import {
		hermes,
		HermesError,
		events,
		waitStopped,
		terminal,
		type Message,
		type Session,
		type RunEvent
	} from '$lib/apis/hermes';
	let sessions: Session[] = [];
	let session = '';
	let messages: Message[] = [];
	let draft = '';
	let output = '';
	let run = '';
	let active = false;
	let busy = false;
	let status = '';
	let error = '';
	let approval: RunEvent | null = null;
	let traces: RunEvent[] = [];
	let toolsets: any[] = [];
	let usage: Record<string, number> | undefined;
	let controller: AbortController | undefined;
	let poll: ReturnType<typeof setInterval> | undefined;
	let polling = false;
	let alive = true;
	let mounted = false;
	afterNavigate(() => {
		const id = $page.url.searchParams.get('session');
		if (mounted && id && id !== session) void selectSession(id);
	});
	let requestKey = '';
	let pendingInput = '';
	let pendingSession = '';
	$: storageKey = `hermes-workbench-run:${$user?.id}`;

	async function loadSessions() {
		sessions = (await hermes('sessions?limit=100')).data ?? [];
	}
	async function loadMessages() {
		if (!session) {
			messages = [];
			return;
		}
		const result = await hermes(
			`sessions/${encodeURIComponent(session)}/messages?limit=100&order=latest`
		);
		if (result.session_id) session = result.session_id;
		messages = (result.data ?? []).filter(
			(m: Message) =>
				['user', 'assistant'].includes(m.role) && typeof m.content === 'string' && m.content
		);
	}
	async function selectSession(id: string) {
		if (active || busy || requestKey) return;
		session = id;
		output = '';
		traces = [];
		error = '';
		try {
			await loadMessages();
		} catch (e) {
			error = (e as Error).message;
		}
	}
	function receive(event: RunEvent) {
		if (!alive) return;
		if (event.event === 'message.delta') output += event.delta ?? '';
		if (event.event === 'message.interim' && !event.already_streamed)
			output += `\n${event.text ?? ''}\n`;
		if (event.event.startsWith('tool.') || event.event.startsWith('subagent.'))
			traces = [...traces, event].slice(-200);
		if (event.event === 'approval.request') {
			approval = event;
			status = 'waiting_for_approval';
		}
		if (event.event === 'approval.responded') {
			approval = null;
			status = 'running';
		}
		if (event.event === 'connection.error') error = '事件流已断开，正在通过运行状态恢复。';
		if (terminal.has(event.event.replace('run.', ''))) {
			if (event.output !== undefined) output = event.output;
			usage = event.usage;
			status = event.event.replace('run.', '');
			if (event.error) error = String(event.error);
		}
	}
	async function refreshRun() {
		if (!run || polling) return;
		polling = true;
		const observedRun = run;
		try {
			const state = await hermes(`runs/${encodeURIComponent(run)}`);
			if (!alive || run !== observedRun) return;
			status = state.status;
			approval = state.status === 'waiting_for_approval' ? (state.approval ?? null) : null;
			if (state.session_id) session = state.session_id;
			if (terminal.has(state.status)) {
				active = false;
				clearInterval(poll);
				controller?.abort();
				localStorage.removeItem(storageKey);
				output = state.output ?? output;
				usage = state.usage;
				if (state.error) error = String(state.error);
				await loadMessages();
				await loadSessions();
				if (messages.at(-1)?.role === 'assistant' && messages.at(-1)?.content === output)
					output = '';
			}
		} catch (e) {
			error = (e as Error).message;
			if (e instanceof HermesError && e.status === 404 && run === observedRun) {
				active = false;
				run = '';
				approval = null;
				clearInterval(poll);
				controller?.abort();
				localStorage.removeItem(storageKey);
				error = 'Hermes 已无法提供该次运行状态，请查看会话历史确认结果。';
			}
		} finally {
			polling = false;
		}
	}
	function watch() {
		controller?.abort();
		clearInterval(poll);
		controller = new AbortController();
		active = true;
		localStorage.setItem(storageKey, JSON.stringify({ run, session }));
		void events(run, receive, controller.signal)
			.catch((e) => {
				if (e.name !== 'AbortError' && alive) error = '事件流暂不可用，正在查询运行状态。';
			})
			.finally(() => {
				if (alive) void refreshRun();
			});
		poll = setInterval(refreshRun, 2000);
		void refreshRun();
	}
	async function send() {
		if (busy || (!draft.trim() && !requestKey)) return;
		busy = true;
		error = '';
		try {
			if (active) {
				await hermes(`runs/${encodeURIComponent(run)}/stop`, {});
				status = 'stopping';
				await waitStopped(run);
				active = false;
				controller?.abort();
				clearInterval(poll);
				await loadMessages();
			}
			if (!session) session = (await hermes('sessions', { title: '' })).session.id;
			// Preserve both body and key after uncertain acceptance; retry cannot start a second run.
			if (!requestKey) {
				requestKey = crypto.randomUUID();
				pendingInput = draft.trim();
				pendingSession = session;
				localStorage.setItem(
					storageKey,
					JSON.stringify({
						pending: { key: requestKey, input: pendingInput, session: pendingSession }
					})
				);
			}
			const result = await hermes(
				'runs',
				{ input: pendingInput, session_id: pendingSession },
				'POST',
				requestKey
			);
			run = result.run_id;
			requestKey = '';
			draft = '';
			output = '';
			traces = [];
			approval = null;
			usage = undefined;
			messages = [...messages, { role: 'user', content: pendingInput }];
			status = 'running';
			watch();
		} catch (e) {
			error = (e as Error).message;
			if (
				requestKey &&
				e instanceof HermesError &&
				[400, 401, 403, 404, 409, 413, 422, 429].includes(e.status)
			) {
				requestKey = '';
				localStorage.removeItem(storageKey);
			}
		} finally {
			busy = false;
		}
	}
	async function stop() {
		busy = true;
		error = '';
		try {
			await hermes(`runs/${encodeURIComponent(run)}/stop`, {});
			status = 'stopping';
			await refreshRun();
		} catch (e) {
			error = (e as Error).message;
		} finally {
			busy = false;
		}
	}
	async function approve(choice: string) {
		if (!approval?.request_id) return;
		busy = true;
		error = '';
		try {
			await hermes(`runs/${encodeURIComponent(run)}/approval`, {
				choice,
				request_id: approval.request_id
			});
			approval = null;
			await refreshRun();
		} catch (e) {
			error = (e as Error).message;
		} finally {
			busy = false;
		}
	}
	onMount(async () => {
		mounted = true;
		try {
			await loadSessions();
			toolsets = (await hermes('toolsets')).data ?? [];
			const saved = JSON.parse(localStorage.getItem(storageKey) || 'null');
			if (saved?.pending) {
				requestKey = saved.pending.key;
				pendingInput = saved.pending.input;
				pendingSession = saved.pending.session;
				session = pendingSession;
				draft = pendingInput;
				await loadMessages();
			} else if (saved?.run && saved?.session) {
				run = saved.run;
				session = saved.session;
				await loadMessages();
				watch();
			} else {
				session = $page.url.searchParams.get('session') ?? '';
				await loadMessages();
			}
		} catch (e) {
			error = (e as Error).message;
		}
	});
	onDestroy(() => {
		alive = false;
		controller?.abort();
		clearInterval(poll);
	});
</script>

<div class="aw-split">
	<div class="chat-column">
		<div class="session-bar aw-row">
			<select
				class="aw-input"
				aria-label="选择 Hermes 会话"
				value={session}
				disabled={active || busy || !!requestKey}
				on:change={(e) => selectSession(e.currentTarget.value)}
			>
				<option value="">新对话</option>{#each sessions as item}<option value={item.id}
						>{item.title || item.id} · {item.source ?? 'Web'}</option
					>{/each}
			</select>
			<button
				class="aw-btn"
				disabled={active || busy || !!requestKey}
				on:click={() => selectSession('')}>新对话</button
			>
		</div>
		{#if error}<div class="aw-error" role="alert">
				{error}
				{#if run}<button class="underline" on:click={refreshRun}>刷新状态</button>{/if}
			</div>{/if}
		<div class="transcript" aria-label="对话记录">
			{#if !messages.length && !active}<div class="aw-empty">
					<h1 class="aw-title">与 Hermes 一起工作</h1>
					<p>查询美股、整理资料，或继续已有的跨平台会话。</p>
				</div>{/if}
			{#each messages as message}<div class:user-message={message.role === 'user'} class="message">
					<div class="aw-label">{message.role === 'user' ? '你' : '● Hermes'}</div>
					<div class="message-content">{message.content}</div>
				</div>{/each}
			{#each traces as trace}<details class="tool-card">
					<summary
						><span class="status-dot"></span><strong>{trace.tool ?? '工具'}</strong><span
							class="aw-muted">{trace.event === 'tool.started' ? '执行中' : '执行结果'}</span
						><span class="tool-preview">{trace.preview ?? ''}</span></summary
					>
					<pre>{trace.preview || '该事件未提供输出'}</pre>
				</details>{/each}
			{#if approval}<div class="approval" role="status">
					<strong>等待审批</strong>
					<p class="aw-muted">仅授权当前 Hermes 提出的操作</p>
					<pre>{approval.command ?? approval.preview ?? '需要确认的操作'}</pre>
					<div class="aw-row">
						{#each [['once', '允许一次'], ['session', '本会话始终允许'], ['deny', '拒绝']] as [choice, label]}{#if approval.choices?.includes(choice)}<button
									class="aw-btn"
									class:aw-primary={choice === 'once'}
									disabled={busy || !approval.request_id}
									on:click={() => approve(choice)}>{label}</button
								>{/if}{/each}
					</div>
					{#if !approval.request_id}<p>当前审批缺少请求标识，请在 Hermes 原生端处理。</p>{/if}
				</div>{/if}
			{#if output}<div class="message">
					<div class="aw-label">● Hermes</div>
					<div class="message-content" aria-live="polite">{output}</div>
				</div>{/if}
		</div>
		<form class="composer" on:submit|preventDefault={send}>
			<div class="aw-row aw-muted" style="justify-content:space-between;margin-bottom:8px">
				<span
					>{active
						? approval
							? '等待审批 · 新消息将停止当前运行后发送'
							: status === 'stopping'
								? '正在停止…'
								: '运行中 · 新消息将停止当前运行后发送'
						: '消息与会话保存在 Hermes'}
				</span>{#if active}<button type="button" class="aw-btn" disabled={busy} on:click={stop}
						>停止</button
					>{/if}
			</div>
			<div class="input-shell">
				<textarea
					aria-label="发送给 Hermes 的消息"
					placeholder="输入你的任务…"
					bind:value={draft}
					disabled={busy || !!requestKey}
					rows="3"
					on:keydown={(e) => {
						if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
							e.preventDefault();
							void send();
						}
					}}
				></textarea>
				<div class="aw-row" style="justify-content:space-between">
					<span class="aw-muted">Shift + Enter 换行</span><button
						class="aw-btn aw-primary"
						disabled={busy || (!draft.trim() && !requestKey)}
						>{busy ? '处理中…' : requestKey ? '重试原消息' : active ? '中断并发送' : '发送'}</button
					>
				</div>
			</div>
		</form>
	</div>
	<aside class="aw-aside">
		<section class="aw-section">
			<h2 class="aw-label">执行轨迹</h2>
			{#if !traces.length}<p class="aw-muted">
					工具调用将在这里显示
				</p>{/if}{#each traces.slice(-8) as trace}<div class="aw-card">
					<strong>{trace.tool ?? 'Hermes'}</strong>
					<p class="aw-muted">{trace.event}</p>
				</div>{/each}
		</section>
		<section class="aw-section">
			<h2 class="aw-label">工具集</h2>
			<div class="toolsets">
				{#each toolsets.filter((t) => t.enabled) as tool}<span class="aw-pill"
						>{tool.label || tool.name}</span
					>{/each}
			</div>
			<p class="aw-muted" style="margin-top:10px">工具权限由助手配置管理。</p>
		</section>
		<section class="aw-section">
			<h2 class="aw-label">本轮用量</h2>
			{#if usage}<pre>{JSON.stringify(usage, null, 2)}</pre>{:else}<p class="aw-muted">
					运行结束后显示实际用量
				</p>{/if}
		</section>
		<a href="/agent/gateway" class="aw-btn">消息网关 →</a>
	</aside>
</div>

<style>
	.chat-column {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		height: 100%;
	}
	.session-bar {
		padding: 12px 24px;
		border-bottom: 1px solid var(--aw-border);
	}
	.transcript {
		flex: 1;
		overflow: auto;
		padding: 28px max(24px, calc((100% - 760px) / 2));
	}
	.message {
		margin-bottom: 24px;
	}
	.message-content {
		white-space: pre-wrap;
		overflow-wrap: anywhere;
		line-height: 1.75;
	}
	.user-message {
		margin-left: auto;
		max-width: 80%;
		background: var(--aw-subtle);
		border-radius: 16px;
		padding: 10px 14px;
	}
	.tool-card {
		border: 1px solid var(--aw-border);
		border-radius: 10px;
		margin-bottom: 10px;
		overflow: hidden;
	}
	summary {
		cursor: pointer;
		background: var(--aw-subtle);
		padding: 10px 12px;
		display: flex;
		align-items: center;
		gap: 8px;
		font-size: 12px;
	}
	.tool-preview {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		flex: 1;
		font-family: monospace;
	}
	.tool-card pre {
		padding: 12px;
		border-top: 1px solid var(--aw-border);
	}
	.status-dot {
		width: 7px;
		height: 7px;
		background: #2f9e6a;
		border-radius: 50%;
	}
	.approval {
		background: #fffaf0;
		border: 1px solid #f0dcb4;
		color: #a5650f;
		border-radius: 12px;
		padding: 16px;
		margin-bottom: 20px;
	}
	.approval pre {
		background: white;
		padding: 12px;
		border-radius: 6px;
		color: #27272a;
		margin: 12px 0;
	}
	.composer {
		padding: 12px 24px 20px;
	}
	.input-shell {
		border: 1px solid var(--aw-border);
		border-radius: 18px;
		padding: 12px;
		box-shadow: 0 1px 2px #00000008;
	}
	textarea {
		width: 100%;
		background: transparent;
		outline: none;
		border: 0;
	}
	.toolsets {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
	}
	@media (max-width: 640px) {
		.chat-column {
			min-height: calc(100dvh - 130px);
		}
		.transcript {
			padding: 20px 16px;
		}
		.composer {
			padding: 12px;
		}
	}
</style>
