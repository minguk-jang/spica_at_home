import Header from '@/components/Header';
import ControlBar from '@/components/ControlBar';
import StepGroup from '@/components/StepGroup';
import JsonPanel from '@/components/JsonPanel';
import Footer from '@/components/Footer';
import { useRecording } from '@/hooks/useRecording';

function App() {
  const {
    state,
    toggleRecording,
    startReplay,
    updateStepLabel,
    selectStep,
    toggleGroupCollapse,
    totalSteps,
    totalGroups,
    selectedStep,
  } = useRecording();

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <Header />
      <ControlBar
        status={state.status}
        hasSteps={totalSteps > 0}
        onToggleRecording={toggleRecording}
        onStartReplay={startReplay}
      />

      <main className="flex-1 flex flex-col overflow-hidden">
        <section className="flex-1 flex flex-col overflow-y-auto custom-scrollbar p-3">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
              Smart Step Grouping
            </h2>
            {totalSteps > 0 && (
              <span className="text-[10px] bg-primary/10 text-primary px-2 py-0.5 rounded-full font-bold">
                {totalGroups} Group{totalGroups !== 1 ? 's' : ''} &bull; {totalSteps} Step
                {totalSteps !== 1 ? 's' : ''}
              </span>
            )}
          </div>

          {state.groups.length > 0 ? (
            <div className="space-y-4">
              {state.groups.map((group) => (
                <StepGroup
                  key={group.id}
                  group={group}
                  selectedStepId={state.selectedStepId}
                  onToggleCollapse={toggleGroupCollapse}
                  onSelectStep={selectStep}
                  onStepLabelChange={updateStepLabel}
                />
              ))}
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center text-slate-500">
                <span className="material-symbols-outlined text-4xl mb-2 block">
                  radio_button_checked
                </span>
                <p className="text-xs">
                  Click <strong>Record</strong> to start capturing
                </p>
                <p className="text-[10px] mt-1">
                  Your interactions will appear here
                </p>
              </div>
            </div>
          )}
        </section>

        <JsonPanel step={selectedStep} />
      </main>

      <Footer status={state.status} />
    </div>
  );
}

export default App;
