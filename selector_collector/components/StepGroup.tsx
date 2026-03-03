import type { StepGroupData } from '@/utils/types';
import StepItem from './StepItem';

interface StepGroupProps {
  group: StepGroupData;
  selectedStepId: string | null;
  onToggleCollapse: (groupId: string) => void;
  onSelectStep: (stepId: string) => void;
  onStepLabelChange: (stepId: string, label: string) => void;
}

export default function StepGroup({
  group,
  selectedStepId,
  onToggleCollapse,
  onSelectStep,
  onStepLabelChange,
}: StepGroupProps) {
  return (
    <div className="group-container">
      <div
        className="step-group-header"
        onClick={() => onToggleCollapse(group.id)}
      >
        <span className="material-symbols-outlined text-slate-400 text-sm">
          {group.collapsed ? 'chevron_right' : 'expand_more'}
        </span>
        <span className="material-symbols-outlined text-primary text-[18px]">
          {group.icon}
        </span>
        <span className="text-xs font-bold flex-1">{group.name}</span>
        <span className="text-[10px] text-slate-400 bg-slate-800 px-1.5 rounded">
          {group.steps.length} step{group.steps.length !== 1 ? 's' : ''}
        </span>
      </div>

      {!group.collapsed && (
        <div className="pl-4 space-y-2 mt-2">
          {group.steps.map((step) => (
            <StepItem
              key={step.id}
              step={step}
              isSelected={step.id === selectedStepId}
              onSelect={onSelectStep}
              onLabelChange={onStepLabelChange}
            />
          ))}
        </div>
      )}
    </div>
  );
}
