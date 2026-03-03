import type { RecordingStatus } from '@/utils/types';

interface FooterProps {
  status: RecordingStatus;
}

export default function Footer({ status }: FooterProps) {
  return (
    <footer className="bg-background-dark border-t border-border-dark px-4 py-2 flex items-center justify-between text-[10px] text-slate-400">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1">
          <span
            className={`size-1.5 rounded-full ${
              status === 'recording' ? 'bg-red-500 animate-pulse' : 'bg-accent-green'
            }`}
          />
          <span>
            {status === 'recording'
              ? 'Recording'
              : status === 'replaying'
                ? 'Replaying'
                : 'AI Ready'}
          </span>
        </div>
        <span className="opacity-50">|</span>
        <span>Grouping Active</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="material-symbols-outlined text-[14px]">bolt</span>
        <span>Low Latency</span>
      </div>
    </footer>
  );
}
