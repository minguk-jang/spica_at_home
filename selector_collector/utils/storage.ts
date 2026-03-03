import { type RecordingState, DEFAULT_RECORDING_STATE } from './types';

const STORAGE_KEY = 'recordingState';

export async function getState(): Promise<RecordingState> {
  const result = await browser.storage.local.get(STORAGE_KEY);
  return (result[STORAGE_KEY] as RecordingState | undefined) ?? DEFAULT_RECORDING_STATE;
}

export async function setState(state: RecordingState): Promise<void> {
  await browser.storage.local.set({ [STORAGE_KEY]: state });
}

export async function updateState(
  updater: (prev: RecordingState) => RecordingState,
): Promise<RecordingState> {
  const prev = await getState();
  const next = updater(prev);
  await setState(next);
  return next;
}

export function watchState(
  callback: (state: RecordingState) => void,
): () => void {
  const listener = (
    changes: Record<string, Browser.storage.StorageChange>,
    area: string,
  ) => {
    if (area === 'local' && changes[STORAGE_KEY]) {
      callback(changes[STORAGE_KEY].newValue as RecordingState);
    }
  };
  browser.storage.onChanged.addListener(listener);
  return () => browser.storage.onChanged.removeListener(listener);
}
