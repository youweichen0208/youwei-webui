import { defineConfig } from 'vitest/config';
import { sveltekit } from '@sveltejs/kit/vite';
import { fileURLToPath } from 'node:url';
export default defineConfig({
	plugins: [sveltekit()],
	resolve: {
		conditions: ['browser'],
		alias: { $lib: fileURLToPath(new URL('./src/lib', import.meta.url)) }
	},
	test: { environment: 'jsdom', include: ['src/lib/components/chat/hermes/*.test.ts'] }
});
