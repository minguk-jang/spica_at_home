import React from "react";
import { ExternalLink } from "lucide-react";

import type { RunResultSummary } from "../../../entities/run/model/runResultSummary";
import { Badge, StatusPill } from "../../../shared/ui";

export function ResultSummaryPanel({
  result,
  onOpenTarget,
  compact = false
}: {
  result: RunResultSummary;
  onOpenTarget: (path: string) => void;
  compact?: boolean;
}): React.ReactElement {
  return (
    <div className={compact ? "resultPanel compact" : "resultPanel"}>
      <div className="resultPanelHeader">
        <div>
          <h4>{result.title}</h4>
          <span className="metaRow">
            {result.status ? <StatusPill status={result.status} /> : null}
            {result.runId !== null ? <Badge>run {result.runId}</Badge> : null}
          </span>
        </div>
        <div className="resultActions">
          {result.reportPath ? (
            <button
              className="linkButton"
              aria-label="Open report"
              title="Open report"
              onClick={() => onOpenTarget(result.reportPath ?? "")}
            >
              <ExternalLink size={14} aria-hidden="true" />
            </button>
          ) : null}
          {result.outputUrl ? (
            <button
              className="linkButton"
              aria-label="Open output URL"
              title="Open output URL"
              onClick={() => onOpenTarget(result.outputUrl ?? "")}
            >
              <ExternalLink size={14} aria-hidden="true" />
            </button>
          ) : null}
        </div>
      </div>
      {result.metrics.length > 0 ? (
        <div className="resultMetrics">
          {result.metrics.map(([label, value]) => (
            <div className="resultMetric" key={label}>
              <span>{label}</span>
              <strong>{value}</strong>
            </div>
          ))}
        </div>
      ) : null}
      {result.outputPreview ? <pre className="resultPreview">{result.outputPreview}</pre> : null}
      {result.rawJson && result.rawJson !== result.outputPreview ? (
        <details className="rawOutput">
          <summary>Raw output</summary>
          <pre>{result.rawJson}</pre>
        </details>
      ) : null}
    </div>
  );
}
