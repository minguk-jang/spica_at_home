import { generateSelector, generateLabel } from '@/utils/selector';
import type { Message, StepRecordedPayload, ReplayStepPayload } from '@/utils/types';

export default defineContentScript({
  matches: ['<all_urls>'],
  main() {
    let isRecording = false;
    let inputDebounceTimer: ReturnType<typeof setTimeout> | null = null;
    let indicator: HTMLDivElement | null = null;

    function showIndicator() {
      if (indicator) return;
      indicator = document.createElement('div');
      indicator.id = '__ai-recorder-indicator';
      Object.assign(indicator.style, {
        position: 'fixed',
        top: '0',
        left: '0',
        right: '0',
        height: '3px',
        background: 'linear-gradient(90deg, #ef4444, #f97316, #ef4444)',
        backgroundSize: '200% 100%',
        animation: '__ai-recorder-slide 1.5s linear infinite',
        zIndex: '2147483647',
        pointerEvents: 'none',
      });

      const style = document.createElement('style');
      style.textContent = `
        @keyframes __ai-recorder-slide {
          0% { background-position: 0% 50%; }
          100% { background-position: 200% 50%; }
        }
      `;
      indicator.appendChild(style);
      document.body.appendChild(indicator);
    }

    function hideIndicator() {
      indicator?.remove();
      indicator = null;
    }

    function sendStep(payload: StepRecordedPayload) {
      const message: Message = { type: 'STEP_RECORDED', payload };
      browser.runtime.sendMessage(message);
    }

    function onClickCapture(e: MouseEvent) {
      if (!isRecording) return;
      const target = e.target as Element;
      if (!target || target.id === '__ai-recorder-indicator') return;

      const selector = generateSelector(target);
      const label = generateLabel(target, 'click');

      sendStep({
        action: 'click',
        selector,
        label,
        url: window.location.href,
      });
    }

    function onInput(e: Event) {
      if (!isRecording) return;
      const target = e.target as HTMLInputElement | HTMLTextAreaElement;
      if (!target || !('value' in target)) return;

      if (inputDebounceTimer) clearTimeout(inputDebounceTimer);

      inputDebounceTimer = setTimeout(() => {
        const selector = generateSelector(target);
        const label = generateLabel(target, 'input');

        sendStep({
          action: 'input',
          selector,
          label,
          value: target.value,
          url: window.location.href,
        });
      }, 500);
    }

    function onKeydown(e: KeyboardEvent) {
      if (!isRecording) return;
      if (e.key !== 'Enter' && e.key !== 'Escape') return;

      const target = e.target as Element;
      const selector = target ? generateSelector(target) : 'body';

      sendStep({
        action: 'keydown',
        selector,
        label: `Press ${e.key}`,
        key: e.key,
        url: window.location.href,
      });
    }

    function startRecording() {
      isRecording = true;
      document.addEventListener('click', onClickCapture, true);
      document.addEventListener('input', onInput, true);
      document.addEventListener('keydown', onKeydown, true);
      showIndicator();
    }

    function stopRecording() {
      isRecording = false;
      document.removeEventListener('click', onClickCapture, true);
      document.removeEventListener('input', onInput, true);
      document.removeEventListener('keydown', onKeydown, true);
      if (inputDebounceTimer) clearTimeout(inputDebounceTimer);
      hideIndicator();
    }

    async function replayStep(payload: ReplayStepPayload): Promise<boolean> {
      const { selector, action, value, key } = payload;
      const el = document.querySelector(selector);

      if (!el) {
        console.warn(`[AI Recorder] Element not found: ${selector}`);
        return false;
      }

      if (action === 'click') {
        (el as HTMLElement).click();
      } else if (action === 'input' && value !== undefined) {
        const input = el as HTMLInputElement;
        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
          window.HTMLInputElement.prototype,
          'value',
        )?.set;
        if (nativeInputValueSetter) {
          nativeInputValueSetter.call(input, value);
        } else {
          input.value = value;
        }
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
      } else if (action === 'keydown' && key) {
        el.dispatchEvent(
          new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }),
        );
        el.dispatchEvent(
          new KeyboardEvent('keyup', { key, bubbles: true, cancelable: true }),
        );
        if (key === 'Enter') {
          const form = (el as HTMLElement).closest('form');
          if (form) form.requestSubmit();
        }
      }

      return true;
    }

    browser.runtime.onMessage.addListener(
      (message: Message, _sender, sendResponse) => {
        if (message.type === 'START_RECORDING') {
          startRecording();
          sendResponse({ success: true });
        } else if (message.type === 'STOP_RECORDING') {
          stopRecording();
          sendResponse({ success: true });
        } else if (message.type === 'REPLAY_STEP') {
          const payload = message.payload as ReplayStepPayload;
          replayStep(payload).then((success) => {
            sendResponse({ success });
          });
          return true;
        }
      },
    );
  },
});
