<script lang="ts">
	import { createEventDispatcher, onDestroy } from 'svelte';
	import { hermes, terminal } from '$lib/apis/hermes';
	const dispatch = createEventDispatcher();
	let text = '';
	let busy = false;
	let error = '';
	let run = '';
	let alive = true;
	async function parse() {
		busy = true;
		error = '';
		try {
			const session = (await hermes('sessions', { title: '' })).session.id;
			const input = `只拟定定时任务草稿，不执行任务、不调用工具、不创建定时任务。请把下面的需求转换为一个 JSON 对象，仅包含四个字符串字段 name、schedule（五段 cron 表达式）、prompt、deliver（未指明时为 local）。时间和接收方由用户随后确认。不要添加 Markdown。需求：\n${text}`;
			run = (await hermes('runs', { input, session_id: session }, 'POST', crypto.randomUUID()))
				.run_id;
			for (let n = 0; n < 90 && alive; n++) {
				const state = await hermes(`runs/${run}`);
				if (terminal.has(state.status)) {
					if (state.status !== 'completed') throw new Error('草稿生成未完成，请手动填写或重试');
					const value = JSON.parse(
						(state.output ?? '').replace(/^```(?:json)?\s*|\s*```$/g, '').trim()
					);
					if (
						!['name', 'schedule', 'prompt', 'deliver'].every(
							(k) => typeof value[k] === 'string' && value[k].trim()
						)
					)
						throw new Error('模型未返回有效草稿，请手动填写');
					dispatch('draft', value);
					run = '';
					return;
				}
				if (state.status === 'waiting_for_approval')
					throw new Error('草稿解析不应执行需要审批的操作，已停止');
				await new Promise((resolve) => setTimeout(resolve, 1000));
			}
			throw new Error('草稿生成超时，已请求停止');
		} catch (e) {
			error = (e as Error).message;
		} finally {
			if (run) await hermes(`runs/${run}/stop`, {}).catch(() => {});
			run = '';
			busy = false;
		}
	}
	onDestroy(() => {
		alive = false;
		if (run) void hermes(`runs/${run}/stop`, {}).catch(() => {});
	});
</script>

<div class="aw-card aw-stack">
	<label
		><span class="aw-label">用自然语言拟定任务</span><textarea
			class="aw-input"
			bind:value={text}
			rows="2"
			maxlength="4000"
			placeholder="每个工作日上午 9 点整理美股新闻，结果保存在本地"
			disabled={busy}
		></textarea></label
	>
	<div class="aw-row">
		<button class="aw-btn" disabled={busy || !text.trim()} on:click={parse}
			>{busy ? 'Hermes 正在解析…' : '解析为任务草稿'}</button
		><span class="aw-muted">调用当前模型；解析后仍需确认创建。</span>
	</div>
	{#if error}<p role="alert">{error}</p>{/if}
</div>
