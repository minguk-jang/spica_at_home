import type { Message } from './types';

export function sendToBackground(message: Message): Promise<unknown> {
  return browser.runtime.sendMessage(message);
}

export function sendToContentScript(
  tabId: number,
  message: Message,
): Promise<unknown> {
  return browser.tabs.sendMessage(tabId, message);
}
