import { useState } from 'react';
import type { Step } from '@/utils/types';

interface JsonPanelProps {
  step: Step | null;
}

export default function JsonPanel({ step }: JsonPanelProps) {
  const [copied, setCopied] = useState(false);

  const jsonData = step
    ? {
        intent: step.label,
        selectors: [step.selector],
        action: step.action,
        ...(step.value && { value: step.value }),
        ...(step.key && { key: step.key }),
      }
    : null;

  const jsonString = jsonData ? JSON.stringify(jsonData, null, 2) : '';

  const handleCopy = async () => {
    if (!jsonString) return;
    await navigator.clipboard.writeText(jsonString);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <aside className="bg-[#0c0c16] border-t border-border-dark p-4 shrink-0">
      <div className="flex items-center justify-between mb-2">
        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
          JSON Step Definition
        </p>
        <span
          className="material-symbols-outlined text-slate-400 text-sm cursor-pointer hover:text-primary transition-colors"
          onClick={handleCopy}
        >
          {copied ? 'check' : 'content_copy'}
        </span>
      </div>

      <div className="bg-json-bg rounded-lg border border-border-dark p-3 font-mono text-[10px] leading-tight max-h-32 overflow-hidden relative">
        {jsonData ? (
          <>
            <div className="text-blue-400">{'{'}</div>
            <div className="pl-4">
              <span className="text-purple-500">"intent"</span>:{' '}
              <span className="text-green-600">"{jsonData.intent}"</span>,
              <br />
              <span className="text-purple-500">"selectors"</span>: [
              <div className="pl-4">
                <span className="text-green-600">"{jsonData.selectors[0]}"</span>
              </div>
              ],
              <br />
              <span className="text-purple-500">"action"</span>:{' '}
              <span className="text-green-600">"{jsonData.action}"</span>
              {jsonData.value && (
                <>
                  ,<br />
                  <span className="text-purple-500">"value"</span>:{' '}
                  <span className="text-green-600">"{jsonData.value}"</span>
                </>
              )}
            </div>
            <div className="text-blue-400">{'}'}</div>
          </>
        ) : (
          <p className="text-slate-500 italic">Select a step to view JSON</p>
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-json-bg via-transparent to-transparent pointer-events-none" />
      </div>

      <div className="mt-4">
        <button className="w-full bg-primary hover:brightness-110 text-white font-bold py-3 rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-primary/20 transition-all">
          <span className="material-symbols-outlined text-lg">auto_fix_high</span>
          AI Selector Processing
        </button>
        <p className="text-[9px] text-center text-slate-400 mt-2 px-2">
          Cleans redundant selectors to maintain essential, resilient identifiers.
        </p>
      </div>
    </aside>
  );
}
