import React, { useMemo } from "react";
import { Activity, Route } from "lucide-react";

import {
  getRunEventResult,
  getWorkflowRunResult
} from "../../../entities/run/model/runResultSummary";
import { storedRunDisplayStatus } from "../../../features/create-workflow/model/workflowDashboard";
import { duration } from "../../../shared/lib/format";
import { Badge, JsonBlock, SectionTitle, StatusPill } from "../../../shared/ui";
import type { RunEvent, StepRun, UpdateEvent, WorkflowRun } from "../../../vite-env";
import { ResultSummaryPanel } from "./ResultSummaryPanel";

export function UpdatesView({ events }: { events: UpdateEvent[] }): React.ReactElement {
  return (
    <section className="tabPanel">
      <SectionTitle icon={<Route size={17} />} title="Update Events" />
      <div className="tableWrap">
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>Type</th>
              <th>Versions</th>
              <th>Reason</th>
              <th>Diff</th>
            </tr>
          </thead>
          <tbody>
            {events.map((event) => (
              <tr key={event.id}>
                <td>{event.createdAt}</td>
                <td>{event.updateType}</td>
                <td>
                  {event.fromVersionId ?? "-"} → {event.toVersionId ?? "-"}
                </td>
                <td>{event.reason}</td>
                <td>
                  <JsonBlock value={event.diff} compact />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function RunsView({
  runs,
  stepRuns,
  activeJobRunning,
  onOpenTarget
}: {
  runs: WorkflowRun[];
  stepRuns: StepRun[];
  activeJobRunning: boolean;
  onOpenTarget: (path: string) => void;
}): React.ReactElement {
  const stepRunsByRun = useMemo(() => {
    const grouped = new Map<number, StepRun[]>();
    stepRuns.forEach((stepRun) => {
      grouped.set(stepRun.runId, [...(grouped.get(stepRun.runId) ?? []), stepRun]);
    });
    return grouped;
  }, [stepRuns]);

  if (runs.length === 0) {
    return (
      <section className="tabPanel">
        <SectionTitle icon={<Activity size={17} />} title="Run History" />
        <div className="emptyState">No stored runs yet</div>
      </section>
    );
  }

  return (
    <section className="tabPanel">
      <SectionTitle icon={<Activity size={17} />} title="Run History" />
      <div className="runCardList">
        {runs.map((run) => {
          const runStepRuns = stepRunsByRun.get(run.id) ?? [];
          const displayStatus = storedRunDisplayStatus(run, activeJobRunning);
          return (
            <article className="runCard" key={run.id}>
              <div className="runCardHeader">
                <div>
                  <h3>Run #{run.id}</h3>
                  <p>{run.userRequest}</p>
                </div>
                <span className="metaRow">
                  <StatusPill status={displayStatus} />
                  <Badge>{duration(run.durationMs)}</Badge>
                  <Badge>{run.llmUsed ? "LLM" : "No LLM"}</Badge>
                  <Badge>{runStepRuns.length} steps</Badge>
                </span>
              </div>
              <ResultSummaryPanel
                result={getWorkflowRunResult({ ...run, status: displayStatus })}
                onOpenTarget={onOpenTarget}
              />
              {runStepRuns.length > 0 ? (
                <details className="stepEvidence">
                  <summary>Step evidence</summary>
                  <div className="stepEvidenceList">
                    {runStepRuns.map((stepRun) => (
                      <article className="stepEvidenceRow" key={stepRun.id}>
                        <div>
                          <strong>Step #{stepRun.stepId}</strong>
                          <span className="metaRow">
                            <StatusPill status={stepRun.status} />
                            <Badge>{duration(stepRun.durationMs)}</Badge>
                          </span>
                        </div>
                        <JsonBlock
                          value={{
                            output: stepRun.output,
                            evidence: stepRun.evidence,
                            error: stepRun.error
                          }}
                          compact
                        />
                      </article>
                    ))}
                  </div>
                </details>
              ) : null}
            </article>
          );
        })}
      </div>
    </section>
  );
}

export function LatestRunResult({
  event,
  onOpenTarget
}: {
  event: RunEvent;
  onOpenTarget: (path: string) => void;
}): React.ReactElement {
  return (
    <section className="latestResult">
      <SectionTitle icon={<Activity size={17} />} title="Latest Run Result" />
      <ResultSummaryPanel result={getRunEventResult(event)} onOpenTarget={onOpenTarget} />
    </section>
  );
}
