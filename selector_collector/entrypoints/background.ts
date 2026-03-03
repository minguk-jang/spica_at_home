import type { Message, Step, StepRecordedPayload, RecordingState } from '@/utils/types';
import { getState, updateState } from '@/utils/storage';
import { sendToContentScript } from '@/utils/messaging';

function generateId(): string {
  return crypto.randomUUID();
}

async function ensureContentScript(tabId: number): Promise<void> {
  try {
    await browser.tabs.sendMessage(tabId, { type: 'GET_STATE' });
  } catch {
    await browser.scripting.executeScript({
      target: { tabId },
      files: ['/content-scripts/content.js'],
    });
  }
}

export default defineBackground(() => {
  // Open side panel on action click
  browser.sidePanel
    .setPanelBehavior({ openPanelOnActionClick: true })
    .catch((error) => console.error(error));

  browser.runtime.onMessage.addListener(
    (message: Message, _sender, sendResponse) => {
      handleMessage(message, _sender)
        .then(sendResponse)
        .catch((err) => {
          console.error('[AI Recorder Background]', err);
          sendResponse({ error: String(err) });
        });
      return true;
    },
  );

  async function handleMessage(
    message: Message,
    _sender: Browser.runtime.MessageSender,
  ): Promise<unknown> {
    switch (message.type) {
      case 'START_RECORDING': {
        const [tab] = await browser.tabs.query({
          active: true,
          currentWindow: true,
        });
        if (!tab?.id) return { error: 'No active tab' };

        await ensureContentScript(tab.id);

        const state = await updateState((prev) => ({
          ...prev,
          status: 'recording',
          steps: [],
          groups: [],
          activeTabId: tab.id!,
          selectedStepId: null,
        }));

        await sendToContentScript(tab.id, { type: 'START_RECORDING' });
        return { success: true, state };
      }

      case 'STOP_RECORDING': {
        const state = await getState();
        if (state.activeTabId) {
          try {
            await sendToContentScript(state.activeTabId, {
              type: 'STOP_RECORDING',
            });
          } catch {
            // Tab may have been closed
          }
        }

        const newState = await updateState((prev) => ({
          ...prev,
          status: 'idle',
        }));
        return { success: true, state: newState };
      }

      case 'STEP_RECORDED': {
        const payload = message.payload as StepRecordedPayload;
        const step: Step = {
          id: generateId(),
          action: payload.action,
          selector: payload.selector,
          label: payload.label,
          value: payload.value,
          key: payload.key,
          url: payload.url,
          timestamp: Date.now(),
        };

        const newState = await updateState((prev) => {
          const steps = [...prev.steps, step];
          const groups = groupSteps(steps);
          return { ...prev, steps, groups };
        });
        return { success: true, state: newState };
      }

      case 'START_REPLAY': {
        const state = await getState();
        const [tab] = await browser.tabs.query({
          active: true,
          currentWindow: true,
        });
        if (!tab?.id) return { error: 'No active tab' };

        await ensureContentScript(tab.id);
        await updateState((prev) => ({ ...prev, status: 'replaying' }));

        replaySteps(tab.id, state.steps).then(async () => {
          await updateState((prev) => ({ ...prev, status: 'idle' }));
        });

        return { success: true };
      }

      case 'GET_STATE': {
        return await getState();
      }

      default:
        return { error: `Unknown message type: ${message.type}` };
    }
  }

  async function replaySteps(tabId: number, steps: Step[]): Promise<void> {
    for (const step of steps) {
      await new Promise((resolve) => setTimeout(resolve, 500));
      try {
        await sendToContentScript(tabId, {
          type: 'REPLAY_STEP',
          payload: {
            selector: step.selector,
            action: step.action,
            value: step.value,
            key: step.key,
          },
        });
      } catch (err) {
        console.error(`[AI Recorder] Replay failed for step: ${step.label}`, err);
      }
    }
  }
});

// Step grouping heuristic
function groupSteps(steps: Step[]): RecordingState['groups'] {
  if (steps.length === 0) return [];

  const groups: RecordingState['groups'] = [];
  let currentGroup: { name: string; icon: string; steps: Step[] } | null = null;

  for (const step of steps) {
    const category = categorizeStep(step);

    if (!currentGroup || currentGroup.name !== category.name) {
      if (currentGroup) {
        groups.push({
          id: crypto.randomUUID(),
          name: currentGroup.name,
          icon: currentGroup.icon,
          steps: currentGroup.steps,
          collapsed: false,
        });
      }
      currentGroup = { name: category.name, icon: category.icon, steps: [step] };
    } else {
      currentGroup.steps.push(step);
    }
  }

  if (currentGroup) {
    groups.push({
      id: crypto.randomUUID(),
      name: currentGroup.name,
      icon: currentGroup.icon,
      steps: currentGroup.steps,
      collapsed: false,
    });
  }

  return groups;
}

function categorizeStep(step: Step): { name: string; icon: string } {
  const selectorLower = step.selector.toLowerCase();
  const labelLower = step.label.toLowerCase();

  // Login/Auth related
  if (
    selectorLower.includes('login') ||
    selectorLower.includes('auth') ||
    selectorLower.includes('password') ||
    selectorLower.includes('email') ||
    selectorLower.includes('sign') ||
    labelLower.includes('login') ||
    labelLower.includes('sign') ||
    labelLower.includes('password') ||
    labelLower.includes('email')
  ) {
    return { name: 'Login Flow', icon: 'lock_open' };
  }

  // Search related
  if (
    selectorLower.includes('search') ||
    labelLower.includes('search') ||
    labelLower.includes('find') ||
    labelLower.includes('filter')
  ) {
    return { name: 'Search Process', icon: 'search' };
  }

  // Navigation related
  if (
    step.action === 'click' &&
    (selectorLower.includes('nav') ||
      selectorLower.includes('menu') ||
      selectorLower.includes('link') ||
      selectorLower.includes('href'))
  ) {
    return { name: 'Navigation', icon: 'explore' };
  }

  // Form related
  if (
    step.action === 'input' ||
    selectorLower.includes('form') ||
    selectorLower.includes('input') ||
    selectorLower.includes('textarea')
  ) {
    return { name: 'Form Input', icon: 'edit_note' };
  }

  return { name: 'User Actions', icon: 'touch_app' };
}
