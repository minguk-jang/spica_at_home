import type { Step, StepAction } from '@/utils/types';

interface StepItemProps {
  step: Step;
  isSelected: boolean;
  onSelect: (id: string) => void;
  onLabelChange: (id: string, label: string) => void;
}

function getActionIcon(action: StepAction, selector: string): string {
  if (action === 'input') {
    if (selector.includes('password')) return 'password';
    return 'edit_note';
  }
  if (action === 'keydown') return 'keyboard';
  // click
  if (selector.includes('search')) return 'search_check';
  if (selector.includes('login') || selector.includes('sign')) return 'login';
  return 'touch_app';
}

export default function StepItem({
  step,
  isSelected,
  onSelect,
  onLabelChange,
}: StepItemProps) {
  const icon = getActionIcon(step.action, step.selector);

  return (
    <div
      className={`flex items-center gap-3 p-2 rounded-lg cursor-pointer transition-colors ${
        isSelected
          ? 'bg-primary/5 border border-primary/20'
          : 'bg-panel-dark border border-border-dark hover:border-border-dark/80'
      }`}
      onClick={() => onSelect(step.id)}
    >
      <span className="material-symbols-outlined text-slate-400 text-[18px]">{icon}</span>
      <div className="flex-1 min-w-0">
        <input
          className="w-full bg-transparent border-none p-0 text-xs font-medium focus:ring-0 focus:outline-none text-slate-200"
          type="text"
          value={step.label}
          onChange={(e) => onLabelChange(step.id, e.target.value)}
          onClick={(e) => e.stopPropagation()}
        />
        <p className="text-[10px] text-slate-400 truncate">{step.selector}</p>
      </div>
      <span className="material-symbols-outlined text-accent-green text-[16px]">check_circle</span>
    </div>
  );
}
