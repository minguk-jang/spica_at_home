export type StepAction = 'click' | 'input' | 'keydown' | 'navigate';

export interface Step {
  id: string;
  action: StepAction;
  selector: string;
  label: string;
  value?: string;
  key?: string;
  url?: string;
  timestamp: number;
}

export interface StepGroupData {
  id: string;
  name: string;
  icon: string;
  steps: Step[];
  collapsed: boolean;
}

export type RecordingStatus = 'idle' | 'recording' | 'replaying';

export interface RecordingState {
  status: RecordingStatus;
  steps: Step[];
  groups: StepGroupData[];
  activeTabId: number | null;
  selectedStepId: string | null;
}

export const DEFAULT_RECORDING_STATE: RecordingState = {
  status: 'idle',
  steps: [],
  groups: [],
  activeTabId: null,
  selectedStepId: null,
};

// Message types between popup, background, and content scripts
export type MessageType =
  | 'START_RECORDING'
  | 'STOP_RECORDING'
  | 'START_REPLAY'
  | 'STEP_RECORDED'
  | 'REPLAY_STEP'
  | 'REPLAY_DONE'
  | 'GET_STATE'
  | 'STATE_UPDATED';

export interface Message {
  type: MessageType;
  payload?: unknown;
}

export interface StepRecordedPayload {
  action: StepAction;
  selector: string;
  label: string;
  value?: string;
  key?: string;
  url?: string;
}

export interface ReplayStepPayload {
  selector: string;
  action: StepAction;
  value?: string;
  key?: string;
}
