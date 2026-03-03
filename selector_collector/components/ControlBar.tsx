import type { RecordingStatus } from '@/utils/types';

interface ControlBarProps {
  status: RecordingStatus;
  hasSteps: boolean;
  onToggleRecording: () => void;
  onStartReplay: () => void;
}

export default function ControlBar({
  status,
  hasSteps,
  onToggleRecording,
  onStartReplay,
}: ControlBarProps) {
  const isRecording = status === 'recording';
  const isReplaying = status === 'replaying';

  return (
    <div className="flex items-center gap-2 p-3 bg-background-dark border-b border-border-dark z-10">
      <button
        onClick={onToggleRecording}
        disabled={isReplaying}
        className={`flex items-center gap-1.5 ${
          isRecording
            ? 'bg-red-700 hover:bg-red-800'
            : 'bg-red-500 hover:bg-red-600'
        } text-white px-3 py-1.5 rounded-full text-xs font-semibold transition-all shadow-sm disabled:opacity-50`}
      >
        <span className="material-symbols-outlined text-sm">
          {isRecording ? 'stop' : 'fiber_manual_record'}
        </span>
        {isRecording ? 'Stop' : 'Record'}
      </button>

      <button
        onClick={onStartReplay}
        disabled={!hasSteps || isRecording || isReplaying}
        className="flex items-center gap-1.5 bg-primary hover:bg-blue-700 text-white px-3 py-1.5 rounded-full text-xs font-semibold transition-all shadow-sm disabled:opacity-50"
      >
        <span className="material-symbols-outlined text-sm">
          {isReplaying ? 'hourglass_empty' : 'play_arrow'}
        </span>
        {isReplaying ? 'Replaying...' : 'Replay'}
      </button>

      <div className="h-5 w-[1px] bg-border-dark mx-1" />

      <button className="flex items-center gap-1.5 text-slate-300 px-2 py-1.5 rounded-lg text-xs font-medium hover:bg-white/5">
        <span className="material-symbols-outlined text-sm">api</span>
        LLM API
      </button>
    </div>
  );
}
