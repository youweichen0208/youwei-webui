<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { hermes, type Session } from '$lib/apis/hermes';
	let health: any = null;
	let sessions: Session[] = [];
	let selected = 'api_server';
	let error = '';
	let loading = false;
	let timer: ReturnType<typeof setInterval>;
	const labels: Record<string, string> = {
		api_server: 'Web API',
		telegram: 'Telegram',
		discord: 'Discord',
		slack: 'Slack',
		whatsapp: 'WhatsApp',
		signal: 'Signal',
		email: 'Email'
	};
	$: platforms = [...new Set([...Object.keys(labels), ...Object.keys(health?.platforms ?? {})])];
	$: platform = health?.platforms?.[selected];
	async function refresh() {
		if (loading) return;
		loading = true;
		try {
			health = await hermes('gateway');
			sessions = (await hermes('sessions?limit=20')).data ?? [];
			error = '';
		} catch (e) {
			error = (e as Error).message;
			health = null;
		} finally {
			loading = false;
		}
	}
	onMount(() => {
		void refresh();
		timer = setInterval(refresh, 15000);
	});
	onDestroy(() => clearInterval(timer));
</script>

<main class="aw-main" style="max-width:1036px;margin:auto">
	<h1 class="aw-title">消息网关</h1>
	<p class="aw-muted" style="margin-bottom:24px">同一个 Hermes，连接不同消息平台。</p>
	{#if error}<div class="aw-error" role="alert">{error}</div>{/if}
	<div class="aw-card aw-row" style="justify-content:space-between">
		<div>
			<strong>{health ? '● 网关进程在线' : loading ? '正在检查网关…' : '网关连接不可用'}</strong
			>{#if health}<p class="aw-muted">
					Hermes {health.version} · {health.gateway_state || health.status} · 活跃 Agent {health.active_agents ??
						0}
				</p>{/if}
		</div>
		<button class="aw-btn" disabled={loading} on:click={refresh}>刷新</button>
	</div>
	<div class="platforms">
		{#each platforms as key}<button
				class="platform-card"
				class:selected={selected === key}
				on:click={() => (selected = key)}
				><strong>{labels[key] ?? key}</strong><span class="aw-muted"
					>{health?.platforms?.[key]?.state ??
						(key === 'api_server' && health ? '在线' : '未报告连接')}</span
				></button
			>{/each}
	</div>
	<div class="aw-card">
		<h2><strong>{labels[selected] ?? selected}</strong></h2>
		<p class="aw-muted" style="margin:10px 0">
			{platform?.state ? `当前状态：${platform.state}` : '当前没有该平台的运行状态。'}
		</p>
		<p>平台凭证、允许的用户和默认投递频道由 Hermes 配置管理。</p>
		<p class="aw-muted" style="margin-top:8px">
			当前连接不提供配置写入、配对码或进程重启接口。工作台不会读取或展示 Bot Token。
		</p>
	</div>
	<div class="aw-card">
		<h2 class="aw-label">最近会话 · 跨平台</h2>
		{#each sessions as session}<a
				class="thread"
				href="/agent?session={encodeURIComponent(session.id)}"
				><span class="aw-pill">{labels[session.source ?? ''] ?? session.source ?? 'Web'}</span><span
					>{session.title || '未命名会话'}</span
				><span class="aw-muted">继续对话 →</span></a
			>{/each}{#if !sessions.length}<p class="aw-muted">暂无可显示的会话</p>{/if}
	</div>
</main>

<style>
	.platforms {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
		gap: 10px;
		margin-bottom: 24px;
	}
	.platform-card {
		display: flex;
		flex-direction: column;
		gap: 14px;
		padding: 20px;
		border: 1px solid var(--aw-border);
		border-radius: 12px;
		text-align: left;
	}
	.selected {
		border-color: #3b7dd8;
		box-shadow: 0 0 0 3px #eaf2fc;
	}
	.thread {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 12px 0;
		border-top: 1px solid var(--aw-border);
	}
	.thread span:nth-child(2) {
		flex: 1;
	}
</style>
