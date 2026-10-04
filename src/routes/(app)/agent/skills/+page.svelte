<script lang="ts">
	import { onMount } from 'svelte';
	import { hermes, type Skill } from '$lib/apis/hermes';
	let skills: Skill[] = [];
	let selected: Skill | null = null;
	let query = '';
	let category = '';
	let error = '';
	let loading = true;
	let content = '';
	let reading = false;
	async function choose(skill: Skill) {
		selected = skill;
		content = '';
		reading = true;
		error = '';
		try {
			const result = await hermes(`skills/${encodeURIComponent(skill.name)}`);
			if (selected.name === skill.name) content = result.content;
		} catch (e) {
			error = (e as Error).message;
		} finally {
			reading = false;
		}
	}
	$: categories = [...new Set(skills.map((s) => s.category).filter(Boolean))];
	$: filtered = skills.filter(
		(s) =>
			(!category || s.category === category) &&
			`${s.name} ${s.description}`.toLowerCase().includes(query.toLowerCase())
	);
	onMount(async () => {
		try {
			skills = (await hermes('skills')).data ?? [];
			if (skills[0]) await choose(skills[0]);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	});
</script>

{#if error}<div class="aw-error" role="alert">{error}</div>{/if}
<div class="aw-split">
	<aside class="aw-list">
		<div class="aw-stack">
			<input
				class="aw-input"
				aria-label="搜索技能"
				placeholder="搜索技能…"
				bind:value={query}
			/><select class="aw-input" aria-label="技能分类" bind:value={category}
				><option value="">全部技能 · {skills.length}</option>{#each categories as item}<option
						value={item}>{item}</option
					>{/each}</select
			>
			{#each filtered as skill}<button
					class="skill"
					class:aw-selected={selected?.name === skill.name}
					on:click={() => choose(skill)}
					><strong>{skill.name}</strong>
					<p>{skill.description}</p>
					<span class="aw-muted">{skill.category || '未分类'}</span></button
				>{/each}
			{#if !filtered.length}<div class="aw-empty">
					{loading ? '正在加载技能…' : '没有匹配的技能'}
				</div>{/if}
		</div>
	</aside>
	<main class="aw-main">
		{#if selected}<div style="max-width:720px">
				<span class="aw-label">Hermes 技能库</span>
				<h1 class="aw-title" style="font-family:monospace">{selected.name}</h1>
				<p style="margin-bottom:24px">{selected.description}</p>
				<div class="aw-card"><span class="aw-label">分类</span>{selected.category || '未分类'}</div>
				<div class="aw-card">
					<h2>SKILL.md</h2>
					<pre>{reading ? '正在读取…' : content}</pre>
					<p class="aw-muted" style="margin-top:8px">
						技能内容仅供查看，不执行内联命令。版本记录和草稿审批请在 Hermes 原生端管理。
					</p>
				</div>
				<p class="aw-muted">技能出现在目录中，不代表当前助手已获准调用技能工具。</p>
			</div>{:else}<div class="aw-empty">选择一个技能查看详情</div>{/if}
	</main>
</div>

<style>
	.skill {
		text-align: left;
		padding: 12px;
		border-radius: 8px;
	}
	.skill strong {
		font: 500 13px monospace;
	}
	.skill p {
		font-size: 12px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		margin: 6px 0;
	}
</style>
