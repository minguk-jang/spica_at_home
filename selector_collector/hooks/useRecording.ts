import { useState, useEffect, useCallback } from 'react';
import type { RecordingState } from '@/utils/types';
import { getState, setState as setStorageState, watchState } from '@/utils/storage';
import { sendToBackground } from '@/utils/messaging';
import { DEFAULT_RECORDING_STATE } from '@/utils/types';

export function useRecording() {
  const [state, setState] = useState<RecordingState>(DEFAULT_RECORDING_STATE);

  useEffect(() => {
    getState().then(setState);
    const unwatch = watchState(setState);
    return unwatch;
  }, []);

  const toggleRecording = useCallback(async () => {
    if (state.status === 'recording') {
      await sendToBackground({ type: 'STOP_RECORDING' });
    } else {
      await sendToBackground({ type: 'START_RECORDING' });
    }
  }, [state.status]);

  const startReplay = useCallback(async () => {
    if (state.steps.length === 0) return;
    await sendToBackground({ type: 'START_REPLAY' });
  }, [state.steps.length]);

  const updateStepLabel = useCallback(
    async (stepId: string, newLabel: string) => {
      const updated: RecordingState = {
        ...state,
        steps: state.steps.map((s) =>
          s.id === stepId ? { ...s, label: newLabel } : s,
        ),
        groups: state.groups.map((g) => ({
          ...g,
          steps: g.steps.map((s) =>
            s.id === stepId ? { ...s, label: newLabel } : s,
          ),
        })),
      };
      await setStorageState(updated);
    },
    [state],
  );

  const selectStep = useCallback(
    async (stepId: string | null) => {
      await setStorageState({ ...state, selectedStepId: stepId });
    },
    [state],
  );

  const toggleGroupCollapse = useCallback(
    async (groupId: string) => {
      const updated: RecordingState = {
        ...state,
        groups: state.groups.map((g) =>
          g.id === groupId ? { ...g, collapsed: !g.collapsed } : g,
        ),
      };
      await setStorageState(updated);
    },
    [state],
  );

  const totalSteps = state.steps.length;
  const totalGroups = state.groups.length;

  const selectedStep = state.selectedStepId
    ? state.steps.find((s) => s.id === state.selectedStepId) ?? null
    : state.steps.length > 0
      ? state.steps[state.steps.length - 1]
      : null;

  return {
    state,
    toggleRecording,
    startReplay,
    updateStepLabel,
    selectStep,
    toggleGroupCollapse,
    totalSteps,
    totalGroups,
    selectedStep,
  };
}
