import { defineConfig } from 'wxt';

export default defineConfig({
  modules: ['@wxt-dev/module-react'],
  manifest: {
    name: 'AI Recorder',
    description: 'Record and replay user interactions with smart CSS selectors',
    permissions: ['activeTab', 'storage', 'tabs', 'scripting', 'sidePanel'],
    host_permissions: ['<all_urls>'],
  },
});
