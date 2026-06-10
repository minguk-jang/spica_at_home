import React from "react";
import { Activity, Terminal } from "lucide-react";

import { getRunEventResult } from "../../../entities/run/model/runResultSummary";
import { duration } from "../../../shared/lib/format";
import { JsonBlock } from "../../../shared/ui";
import type { RunEvent } from "../../../vite-env";
import { ResultSummaryPanel } from "../../workflow-detail/ui";

export function RunEvents({
  events,
  onOpenTarget
}: {
  events: RunEvent[];
  onOpenTarget: (path: string) => void;
}): React.ReactElement {
  if (events.length === 0) {
    return <div className="emptyState">No run events yet</div>;
  }
  return (
    <div className="eventList">
      {events.map((event, index) => (
        <article className="eventRow" key={`${event.type}-${event.jobId ?? "q"}-${index}`}>
          <span className="eventIcon">
            {event.type.includes("finished") ? <Activity size={15} /> : <Terminal size={15} />}
          </span>
          <div>
            <h3>{eventLabel(event)}</h3>
            <p>{event.status ? `${event.status} · ${duration(event.durationMs ?? null)}` : event.startedAt}</p>
            {event.type === "job-finished" ? (
              <ResultSummaryPanel
                result={getRunEventResult(event)}
                onOpenTarget={onOpenTarget}
                compact
              />
            ) : null}
            {event.type.startsWith("update-") && event.type.endsWith("finished") && event.output ? (
              <JsonBlock value={event.output} compact />
            ) : null}
            {event.type.startsWith("evolution") && event.type.endsWith("finished") && event.output ? (
              <JsonBlock value={event.output} compact />
            ) : null}
            {event.type.startsWith("creation") && event.type.endsWith("finished") && event.output ? (
              <JsonBlock value={event.output} compact />
            ) : null}
            {event.type.startsWith("js-tool") && event.type.endsWith("finished") && event.output ? (
              <JsonBlock value={event.output} compact />
            ) : null}
            {event.stderr ? <pre className="stderr">{event.stderr}</pre> : null}
          </div>
        </article>
      ))}
    </div>
  );
}

function eventLabel(event: RunEvent): string {
  if (event.type.startsWith("update-proposal")) {
    return `${event.workflowName ?? "workflow"} proposal ${event.type.endsWith("finished") ? "finished" : "started"}`;
  }
  if (event.type.startsWith("evolution")) {
    return `${event.workflowName ?? "workflow"} evolution ${event.type.endsWith("finished") ? "finished" : "started"}`;
  }
  if (event.type.startsWith("creation")) {
    return `workflow creation ${event.type.endsWith("finished") ? "finished" : "started"}`;
  }
  if (event.type.startsWith("js-tool")) {
    return `JavaScript tool ${event.type.endsWith("finished") ? "finished" : "started"}`;
  }
  return `${event.workflowName ?? "workflow"} ${event.type}`;
}
