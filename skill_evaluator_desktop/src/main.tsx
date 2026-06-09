import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  Bot,
  ChevronRight,
  Database,
  Eye,
  ExternalLink,
  FileText,
  History,
  ListChecks,
  Play,
  RefreshCw,
  Route,
  ScrollText,
  Terminal,
  Workflow
} from "lucide-react";
import type {
  DefaultPaths,
  ApplyProposalPayload,
  RunEvent,
  RunPayload,
  StepRun,
  UpdateEvent,
  UpdateProposalPayload,
  WorkflowArgument,
  WorkflowCard,
  WorkflowDetail,
  WorkflowHandler,
  WorkflowResource,
  WorkflowRun,
  WorkflowStep,
  WorkflowUpdateProposal,
  WorkflowVersion
} from "./vite-env";
import {
  getRunEventResult,
  getWorkflowRunResult,
  type RunResultSummary
} from "./runResultSummary";
import {
  generatePlaywrightScriptPreview,
  getStepScriptDescriptor
} from "./script-preview";
import {
  UPDATE_MODE_OPTIONS,
  discoveryProviderForUpdateMode,
  type UpdateMode
} from "./updateModeOptions";
import { normalizeWorkflowDetail } from "./workflowDetailDefaults";
import "./styles.css";

type TabKey = "steps" | "script" | "versions" | "update" | "updates" | "runs";

const fallbackPaths: DefaultPaths = {
  repoRoot: "../skill_evaluator",
  dbPath: "../skill_evaluator/outputs/webmcp_plugin_cold_iter_check/workflows.sqlite",
  outputDir: "../skill_evaluator/outputs/desktop_runs",
  pythonPath: "../skill_evaluator/reference/webwright/.venv/bin/python",
  sidecarPath: "rust/webmcp-sidecar/target/debug/webmcp-sidecar"
};

function App(): React.ReactElement {
  const [paths, setPaths] = useState<DefaultPaths>(fallbackPaths);
  const [dbPath, setDbPath] = useState(fallbackPaths.dbPath);
  const [repoRoot, setRepoRoot] = useState(fallbackPaths.repoRoot);
  const [outputDir, setOutputDir] = useState(fallbackPaths.outputDir);
  const [pythonPath, setPythonPath] = useState(fallbackPaths.pythonPath);
  const [workflows, setWorkflows] = useState<WorkflowCard[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<WorkflowDetail | null>(null);
  const [status, setStatus] = useState("Loading");
  const [tab, setTab] = useState<TabKey>("steps");
  const [selectedResourceId, setSelectedResourceId] = useState<number | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [running, setRunning] = useState(false);
  const [request, setRequest] = useState("네이버에서 삼성전자 주가 리포트");
  const [companyName, setCompanyName] = useState("삼성전자");
  const [ticker, setTicker] = useState("005930");
  const [newsLimit, setNewsLimit] = useState(3);
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const [updateInstruction, setUpdateInstruction] = useState("");
  const [updateMode, setUpdateMode] = useState<UpdateMode>("code-only");
  const [updateModel, setUpdateModel] = useState("gpt-5.3-codex-spark");

  const selectedWorkflow = workflows.find((workflow) => workflow.id === selectedId) ?? workflows[0] ?? null;
  const selectedWorkflowId = selectedWorkflow?.id ?? null;
  const latestFinishedEvent = useMemo(
    () => events.find((event) => event.type === "job-finished") ?? null,
    [events]
  );
  const selectedResource = useMemo(() => {
    if (!detail || detail.resources.length === 0) {
      return null;
    }
    return (
      detail.resources.find((resource) => resource.id === selectedResourceId) ??
      detail.resources[0]
    );
  }, [detail, selectedResourceId]);

  useEffect(() => {
    if (!window.webmcp) {
      setStatus("Electron bridge is not available. Run with npm run electron.");
      return;
    }
    void window.webmcp
      .getDefaultPaths()
      .then((defaults) => {
        setPaths(defaults);
        setDbPath(defaults.dbPath);
        setRepoRoot(defaults.repoRoot);
        setOutputDir(defaults.outputDir);
        setPythonPath(defaults.pythonPath);
        setStatus("Ready");
        return defaults.dbPath;
      })
      .then((nextDbPath) => refresh(nextDbPath))
      .catch((error: unknown) => setStatus(errorMessage(error)));
  }, []);

  useEffect(() => {
    if (!window.webmcp) {
      return undefined;
    }
    return window.webmcp.onRunEvent((event) => {
      setEvents((current) => [event, ...current].slice(0, 80));
    });
  }, []);

  useEffect(() => {
    if (selectedWorkflowId === null || !window.webmcp) {
      setDetail(null);
      return;
    }
    void loadWorkflowDetail(selectedWorkflowId);
  }, [dbPath, repoRoot, selectedWorkflowId]);

  async function refresh(pathOverride = dbPath): Promise<void> {
    if (!window.webmcp) {
      setStatus("Electron bridge is not available.");
      return;
    }
    setStatus("Loading workflows");
    const loaded = await window.webmcp.listWorkflows(pathOverride);
    setWorkflows(loaded);
    setSelectedId((current) => {
      if (loaded.length === 0) {
        return null;
      }
      return current && loaded.some((workflow) => workflow.id === current)
        ? current
        : loaded[0].id;
    });
    setStatus(`${loaded.length} WebMCP workflows loaded`);
  }

  async function loadWorkflowDetail(workflowId: number, pathOverride = dbPath): Promise<WorkflowDetail | null> {
    if (!window.webmcp) {
      setStatus("Electron bridge is not available.");
      return null;
    }
    const workflowName = workflows.find((workflow) => workflow.id === workflowId)?.name ?? `workflow #${workflowId}`;
    setStatus(`Loading ${workflowName}`);
    try {
      const loaded = normalizeWorkflowDetail(await window.webmcp.getWorkflowDetail(pathOverride, workflowId, repoRoot));
      setDetail(loaded);
      setSelectedResourceId(loaded.resources[0]?.id ?? null);
      setSelectedVersion((current) =>
        current && loaded.versions.some((version) => version.version === current)
          ? current
          : loaded.versions[0]?.version ?? null
      );
      setStatus(`${loaded.workflow.name} loaded`);
      return loaded;
    } catch (error: unknown) {
      setDetail(null);
      setStatus(errorMessage(error));
      return null;
    }
  }

  function runPayload(extra: Partial<RunPayload> = {}): RunPayload {
    return {
      dbPath,
      repoRoot,
      outputDir,
      pythonPath,
      workflowName: detail?.workflow.name ?? selectedWorkflow?.name ?? "",
      request,
      companyName,
      ticker: ticker.trim() || undefined,
      newsLimit,
      ...extra
    };
  }

  async function runSelectedVersion(headed: boolean, versionOverride?: number): Promise<void> {
    const versionToRun = versionOverride ?? selectedVersion;
    if (!window.webmcp || !detail || versionToRun === null) {
      return;
    }
    setRunning(true);
    setEvents([]);
    try {
      if (headed) {
        await window.webmcp.watchVersion(runPayload({ version: versionToRun, headed: true }));
      } else {
        await window.webmcp.runVersions(runPayload({ versions: [versionToRun], headed: false }));
      }
      setStatus(`${headed ? "Headed" : "Headless"} run finished for v${versionToRun}`);
      const workflowId = detail.workflow.id;
      await refresh();
      await loadWorkflowDetail(workflowId);
      setTab("runs");
    } catch (error: unknown) {
      setStatus(webmcpErrorMessage(error));
    } finally {
      setRunning(false);
    }
  }

  async function generateUpdateProposal(): Promise<void> {
    if (!window.webmcp || !detail || selectedVersion === null || !updateInstruction.trim()) {
      return;
    }
    setRunning(true);
    setEvents([]);
    try {
      const payload: UpdateProposalPayload = {
        dbPath,
        repoRoot,
        outputDir,
        pythonPath,
        workflowName: detail.workflow.name,
        baseVersion: selectedVersion,
        instruction: updateInstruction,
        companyName,
        ticker: ticker.trim() || undefined,
        discoveryProvider: discoveryProviderForUpdateMode(updateMode),
        synthesizerModel: updateModel
      };
      const result = await window.webmcp.proposeUpdate(payload);
      const resultStatus =
        result && typeof result === "object" && "status" in result
          ? String((result as { status?: unknown }).status)
          : "finished";
      const workflowId = detail.workflow.id;
      await refresh();
      await loadWorkflowDetail(workflowId);
      setTab("update");
      setStatus(`Codex draft job ${resultStatus} for v${selectedVersion}`);
    } catch (error: unknown) {
      setStatus(webmcpErrorMessage(error));
    } finally {
      setRunning(false);
    }
  }

  async function applyUpdateProposal(proposalId: number): Promise<void> {
    if (!window.webmcp || !detail) {
      return;
    }
    setRunning(true);
    setEvents([]);
    try {
      const payload: ApplyProposalPayload = {
        dbPath,
        repoRoot,
        pythonPath,
        proposalId,
        approvedBy: "desktop"
      };
      await window.webmcp.applyProposal(payload);
      const workflowId = detail.workflow.id;
      await refresh();
      await loadWorkflowDetail(workflowId);
      setTab("versions");
      setStatus(`Proposal #${proposalId} applied`);
    } catch (error: unknown) {
      setStatus(webmcpErrorMessage(error));
    } finally {
      setRunning(false);
    }
  }

  return (
    <main className="appShell">
      <header className="topbar">
        <div className="brand">
          <Workflow size={24} aria-hidden="true" />
          <div>
            <h1>WebMCP Desktop</h1>
            <p>{status}</p>
          </div>
        </div>
        <div className="topActions">
          <PathField label="DB" icon={<Database size={16} />} value={dbPath} onChange={setDbPath} />
          <IconButton
            label="Refresh"
            title="Refresh workflows"
            onClick={() => void refresh()}
            disabled={running}
          >
            <RefreshCw size={17} />
          </IconButton>
        </div>
      </header>

      <section className="contentGrid">
        <aside className="sidebar" aria-label="Workflow list">
          <div className="sidebarHeader">
            <span>Tool List</span>
            <strong>{workflows.length}</strong>
          </div>
          <div className="workflowList">
            {workflows.map((workflow) => (
              <WorkflowCardButton
                key={workflow.id}
                workflow={workflow}
                selected={workflow.id === selectedWorkflow?.id}
                onClick={() => setSelectedId(workflow.id)}
              />
            ))}
            {workflows.length === 0 ? <div className="emptyState">No workflows found</div> : null}
          </div>
        </aside>

        <section className="detailPane">
          {!detail ? (
            <div className="emptyState large">Select a WebMCP workflow</div>
          ) : (
            <>
              <DetailHeader detail={detail} />
              <RunControls
                request={request}
                setRequest={setRequest}
                companyName={companyName}
                setCompanyName={setCompanyName}
                ticker={ticker}
                setTicker={setTicker}
                newsLimit={newsLimit}
                setNewsLimit={setNewsLimit}
                repoRoot={repoRoot}
                setRepoRoot={setRepoRoot}
                outputDir={outputDir}
                setOutputDir={setOutputDir}
                pythonPath={pythonPath}
                setPythonPath={setPythonPath}
                selectedVersion={selectedVersion}
                running={running}
                onRunHeadless={() => void runSelectedVersion(false)}
                onRunHeaded={() => void runSelectedVersion(true)}
              />
              {latestFinishedEvent ? (
                <LatestRunResult
                  event={latestFinishedEvent}
                  onOpenTarget={(targetPath) => void window.webmcp?.openPath(targetPath)}
                />
              ) : null}
              <Tabs active={tab} onSelect={setTab} />
              {tab === "steps" ? <StepsView steps={detail.steps} arguments={detail.arguments} /> : null}
              {tab === "script" ? (
                <ScriptView
                  versions={detail.versions}
                  steps={detail.steps}
                  resources={detail.resources}
                  handlers={detail.handlers}
                  selectedResource={selectedResource}
                  onSelectResource={setSelectedResourceId}
                />
              ) : null}
              {tab === "versions" ? (
                <VersionsView
                  versions={detail.versions}
                  selectedVersion={selectedVersion}
                  onSelectVersion={setSelectedVersion}
                  running={running}
                  onRunHeadless={(version) => {
                    setSelectedVersion(version);
                    void runSelectedVersion(false, version);
                  }}
                  onRunHeaded={(version) => {
                    setSelectedVersion(version);
                    void runSelectedVersion(true, version);
                  }}
                />
              ) : null}
              {tab === "update" ? (
                <UpdateStudio
                  detail={detail}
                  selectedVersion={selectedVersion}
                  instruction={updateInstruction}
                  setInstruction={setUpdateInstruction}
                  updateMode={updateMode}
                  setUpdateMode={setUpdateMode}
                  model={updateModel}
                  setModel={setUpdateModel}
                  running={running}
                  onGenerate={() => void generateUpdateProposal()}
                  onApply={(proposalId) => void applyUpdateProposal(proposalId)}
                />
              ) : null}
              {tab === "updates" ? <UpdatesView events={detail.updateEvents} /> : null}
              {tab === "runs" ? (
                <RunsView
                  runs={detail.runs}
                  stepRuns={detail.stepRuns}
                  onOpenTarget={(targetPath) => void window.webmcp?.openPath(targetPath)}
                />
              ) : null}
            </>
          )}
        </section>

        <aside className="queuePane" aria-label="Run queue">
          <div className="sidebarHeader">
            <span>Run Queue</span>
            <strong>{events.length}</strong>
          </div>
          <RunEvents
            events={events}
            onOpenTarget={(targetPath) => void window.webmcp?.openPath(targetPath)}
          />
        </aside>
      </section>
    </main>
  );
}

function WorkflowCardButton(props: {
  workflow: WorkflowCard;
  selected: boolean;
  onClick: () => void;
}): React.ReactElement {
  const { workflow, selected, onClick } = props;
  return (
    <button className={selected ? "workflowCard selected" : "workflowCard"} onClick={onClick}>
      <span className="workflowTitle">
        <Bot size={17} aria-hidden="true" />
        {workflow.name}
      </span>
      <span className="workflowDescription">{workflow.description}</span>
      <span className="metaRow">
        <Badge>{workflow.domain}</Badge>
        <Badge>v{workflow.latestVersion}</Badge>
        <Badge>{workflow.runCount} runs</Badge>
      </span>
      <ChevronRight className="cardArrow" size={18} aria-hidden="true" />
    </button>
  );
}

function DetailHeader({ detail }: { detail: WorkflowDetail }): React.ReactElement {
  return (
    <section className="detailHeader">
      <div>
        <p className="eyebrow">WebMCP workflow</p>
        <h2>{detail.workflow.name}</h2>
        <p>{detail.workflow.description}</p>
      </div>
      <div className="metricStrip">
        <Metric label="Versions" value={detail.workflow.versionCount} />
        <Metric label="Steps" value={detail.workflow.stepCount} />
        <Metric label="Runs" value={detail.workflow.runCount} />
        <Metric label="Updates" value={detail.workflow.updateCount} />
      </div>
    </section>
  );
}

function RunControls(props: {
  request: string;
  setRequest: (value: string) => void;
  companyName: string;
  setCompanyName: (value: string) => void;
  ticker: string;
  setTicker: (value: string) => void;
  newsLimit: number;
  setNewsLimit: (value: number) => void;
  repoRoot: string;
  setRepoRoot: (value: string) => void;
  outputDir: string;
  setOutputDir: (value: string) => void;
  pythonPath: string;
  setPythonPath: (value: string) => void;
  selectedVersion: number | null;
  running: boolean;
  onRunHeadless: () => void;
  onRunHeaded: () => void;
}): React.ReactElement {
  return (
    <section className="runControls">
      <div className="formGrid">
        <TextField label="Request" value={props.request} onChange={props.setRequest} />
        <TextField label="Company" value={props.companyName} onChange={props.setCompanyName} />
        <TextField label="Ticker" value={props.ticker} onChange={props.setTicker} />
        <NumberField label="News" value={props.newsLimit} onChange={props.setNewsLimit} />
        <TextField label="Repo" value={props.repoRoot} onChange={props.setRepoRoot} />
        <TextField label="Output" value={props.outputDir} onChange={props.setOutputDir} />
        <TextField label="Python" value={props.pythonPath} onChange={props.setPythonPath} />
      </div>
      <div className="runActionRow">
        <div className="selectedVersionBadge" aria-label="Selected version">
          Selected {props.selectedVersion === null ? "-" : `v${props.selectedVersion}`}
        </div>
        <button className="primaryButton" onClick={props.onRunHeadless} disabled={props.running || props.selectedVersion === null}>
          <Play size={17} aria-hidden="true" />
          Run selected headless
        </button>
        <button className="secondaryButton emphasized" onClick={props.onRunHeaded} disabled={props.running || props.selectedVersion === null}>
          <Eye size={17} aria-hidden="true" />
          Run selected headed
        </button>
      </div>
    </section>
  );
}

function Tabs({ active, onSelect }: { active: TabKey; onSelect: (tab: TabKey) => void }): React.ReactElement {
  const tabs: Array<{ key: TabKey; label: string; icon: React.ReactNode }> = [
    { key: "steps", label: "Steps", icon: <ListChecks size={16} /> },
    { key: "script", label: "Implementation", icon: <ScrollText size={16} /> },
    { key: "versions", label: "Versions", icon: <History size={16} /> },
    { key: "update", label: "Update", icon: <Bot size={16} /> },
    { key: "updates", label: "Updates", icon: <Route size={16} /> },
    { key: "runs", label: "Runs", icon: <Activity size={16} /> }
  ];
  return (
    <nav className="tabs" aria-label="Workflow detail tabs">
      {tabs.map((item) => (
        <button
          key={item.key}
          className={active === item.key ? "tab active" : "tab"}
          onClick={() => onSelect(item.key)}
        >
          {item.icon}
          {item.label}
        </button>
      ))}
    </nav>
  );
}

function StepsView({
  steps,
  arguments: workflowArguments
}: {
  steps: WorkflowStep[];
  arguments: WorkflowArgument[];
}): React.ReactElement {
  return (
    <section className="tabPanel">
      <div className="splitLayout">
        <div>
          <SectionTitle icon={<ListChecks size={17} />} title="Generated Steps" />
          <div className="timeline">
            {steps.map((step) => (
              <article className="timelineRow" key={step.id}>
                <span className="stepIndex">{step.orderIndex + 1}</span>
                <div>
                  <h3>{step.name}</h3>
                  <p>{step.description}</p>
                  <span className="metaRow">
                    <Badge>{step.stepType}</Badge>
                    {step.handlerRef ? <Badge>{step.handlerRef}</Badge> : null}
                  </span>
                </div>
                <JsonBlock value={{ action: step.action, assertions: step.assertions }} compact />
              </article>
            ))}
          </div>
        </div>
        <div>
          <SectionTitle icon={<Terminal size={17} />} title="Dynamic Arguments" />
          <div className="tableWrap narrow">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Required</th>
                  <th>Dynamic</th>
                </tr>
              </thead>
              <tbody>
                {workflowArguments.map((argument) => (
                  <tr key={argument.id}>
                    <td>{argument.name}</td>
                    <td>{argument.valueType}</td>
                    <td>{argument.required ? "yes" : "no"}</td>
                    <td>{argument.isDynamic ? "yes" : "no"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  );
}

function ScriptView(props: {
  versions: WorkflowVersion[];
  steps: WorkflowStep[];
  resources: WorkflowResource[];
  handlers: WorkflowHandler[];
  selectedResource: WorkflowResource | null;
  onSelectResource: (id: number) => void;
}): React.ReactElement {
  const latest = props.versions[0] ?? null;
  const playwrightPreview = generatePlaywrightScriptPreview(props.steps, props.handlers, props.resources);
  return (
    <section className="tabPanel">
      <div className="scriptStack">
        <div>
          <SectionTitle icon={<Terminal size={17} />} title="Playwright Python Preview" />
          <pre className="codeBlock preview">{playwrightPreview}</pre>
        </div>
        <div>
          <SectionTitle icon={<ListChecks size={17} />} title="Step Implementation" />
          <div className="stepScriptList">
            {props.steps.length === 0 ? <div className="emptyState">No steps found</div> : null}
            {props.steps.map((step) => {
              const descriptor = getStepScriptDescriptor(step, props.handlers);
              const handler = props.handlers.find((candidate) => candidate.name === step.handlerRef);
              return (
                <article className="stepScriptRow" key={step.id}>
                  <div className="stepScriptHeader">
                    <span className="stepIndex">{step.orderIndex + 1}</span>
                    <div>
                      <h3>{step.name}</h3>
                      <p>{step.description}</p>
                      <span className="metaRow">
                        <Badge>{step.stepType}</Badge>
                        <Badge>{descriptor.kind}</Badge>
                        <Badge>{descriptor.language}</Badge>
                        {step.handlerRef ? <Badge>{step.handlerRef}</Badge> : null}
                      </span>
                    </div>
                  </div>
                  <dl className="scriptFacts">
                    <div>
                      <dt>Implementation</dt>
                      <dd>{descriptor.implementation}</dd>
                    </div>
                    <div>
                      <dt>Stored as</dt>
                      <dd>{descriptor.storedAs}</dd>
                    </div>
                    {descriptor.resourceName ? (
                      <div>
                        <dt>Resource</dt>
                        <dd>{descriptor.resourceName}</dd>
                      </div>
                    ) : null}
                  </dl>
                  <div className="scriptCodeGrid">
                    <div>
                      <h4>Action JSON</h4>
                      <JsonBlock value={step.action} compact />
                    </div>
                    <div>
                      <h4>Argument Bindings</h4>
                      <JsonBlock value={step.argumentBindings} compact />
                    </div>
                    <div>
                      <h4>Assertions</h4>
                      <JsonBlock value={step.assertions} compact />
                    </div>
                  </div>
                  {handler ? (
                    <details className="rawOutput">
                      <summary>Handler registry</summary>
                      <pre>
                        {pretty({
                          description: handler.description,
                          module: handler.module,
                          function: handler.function,
                          sourcePath: handler.sourcePath,
                          inputSchema: handler.inputSchema,
                          outputSchema: handler.outputSchema,
                          allowedDomains: handler.allowedDomains
                        })}
                      </pre>
                    </details>
                  ) : null}
                  {handler?.sourceText ? (
                    <details className="rawOutput">
                      <summary>Handler source</summary>
                      <pre>{handler.sourceText}</pre>
                    </details>
                  ) : null}
                </article>
              );
            })}
          </div>
        </div>
        <div className="scriptGrid">
          <div>
            <SectionTitle icon={<FileText size={17} />} title="Workflow Body" />
            <pre className="codeBlock">{latest?.bodyMd ?? "No workflow body"}</pre>
          </div>
          <div>
            <SectionTitle icon={<ScrollText size={17} />} title="Resource Templates" />
            <div className="resourcePicker">
              {props.resources.map((resource) => (
                <button
                  key={resource.id}
                  className={
                    resource.id === props.selectedResource?.id ? "resourceButton active" : "resourceButton"
                  }
                  onClick={() => props.onSelectResource(resource.id)}
                >
                  {resource.name}
                </button>
              ))}
            </div>
            <pre className="codeBlock tall">
              {props.selectedResource?.contentText ||
                pretty(props.selectedResource?.contentJson) ||
                "No resource selected"}
            </pre>
          </div>
        </div>
      </div>
    </section>
  );
}

function VersionsView(props: {
  versions: WorkflowVersion[];
  selectedVersion: number | null;
  onSelectVersion: (version: number) => void;
  running: boolean;
  onRunHeadless: (version: number) => void;
  onRunHeaded: (version: number) => void;
}): React.ReactElement {
  return (
    <section className="tabPanel">
      <SectionTitle icon={<History size={17} />} title="Version Changes" />
      <div className="versionList">
        {props.versions.map((version) => (
          <article
            className={version.version === props.selectedVersion ? "versionRow selected" : "versionRow"}
            key={version.id}
          >
            <div>
              <h3>v{version.version}</h3>
              <p>{version.summary}</p>
              <span className="metaRow">
                <Badge>{version.status}</Badge>
                <Badge>{version.createdAt}</Badge>
                {version.createdFromRunId ? <Badge>from run {version.createdFromRunId}</Badge> : null}
              </span>
            </div>
            <div className="versionActions">
              <IconTextButton
                label="Select"
                title={`Select v${version.version}`}
                disabled={props.running}
                onClick={() => props.onSelectVersion(version.version)}
              >
                <ChevronRight size={16} />
              </IconTextButton>
              <IconTextButton
                label="Headless"
                title={`Run v${version.version} headless`}
                disabled={props.running}
                onClick={() => props.onRunHeadless(version.version)}
              >
                <Play size={16} />
              </IconTextButton>
              <IconTextButton
                label="Headed"
                title={`Run v${version.version} headed`}
                disabled={props.running}
                onClick={() => props.onRunHeaded(version.version)}
              >
                <Eye size={16} />
              </IconTextButton>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function UpdateStudio(props: {
  detail: WorkflowDetail;
  selectedVersion: number | null;
  instruction: string;
  setInstruction: (value: string) => void;
  updateMode: UpdateMode;
  setUpdateMode: (value: UpdateMode) => void;
  model: string;
  setModel: (value: string) => void;
  running: boolean;
  onGenerate: () => void;
  onApply: (proposalId: number) => void;
}): React.ReactElement {
  return (
    <section className="tabPanel">
      <SectionTitle icon={<Bot size={17} />} title="Update Studio" />
      <div className="updateComposer">
        <label className="textAreaField">
          <span>Instruction</span>
          <textarea
            value={props.instruction}
            rows={4}
            placeholder="리포트에 밸류에이션 섹션을 추가하고, PER/PBR 값을 argument로 받을 수 있게 해줘"
            onChange={(event) => props.setInstruction(event.target.value)}
          />
        </label>
        <div className="modeSelector" aria-label="Update mode">
          {UPDATE_MODE_OPTIONS.map((option) => (
            <button
              key={option.mode}
              className={props.updateMode === option.mode ? "modeOption active" : "modeOption"}
              type="button"
              onClick={() => props.setUpdateMode(option.mode)}
            >
              <strong>{option.label}</strong>
              <span>{option.description}</span>
            </button>
          ))}
        </div>
        <div className="updateControlGrid">
          <TextField label="Codex model" value={props.model} onChange={props.setModel} />
          <button
            className="primaryButton"
            onClick={props.onGenerate}
            disabled={props.running || props.selectedVersion === null || props.instruction.trim() === ""}
          >
            <Bot size={17} aria-hidden="true" />
            Generate draft
          </button>
        </div>
        <span className="metaRow">
          <Badge>{props.detail.workflow.name}</Badge>
          <Badge>base {props.selectedVersion === null ? "-" : `v${props.selectedVersion}`}</Badge>
          <Badge>Codex only</Badge>
          <Badge>{props.detail.proposals.length} proposals</Badge>
        </span>
      </div>
      <ProposalList proposals={props.detail.proposals} running={props.running} onApply={props.onApply} />
    </section>
  );
}

function ProposalList({
  proposals,
  running,
  onApply
}: {
  proposals: WorkflowUpdateProposal[];
  running: boolean;
  onApply: (proposalId: number) => void;
}): React.ReactElement {
  if (proposals.length === 0) {
    return <div className="emptyState">No update proposals yet</div>;
  }
  return (
    <div className="proposalList">
      {proposals.map((proposal) => (
        <article className="proposalRow" key={proposal.id}>
          <div className="proposalHeader">
            <div>
              <h3>Proposal #{proposal.id}</h3>
              <p>{proposal.instruction}</p>
              <span className="metaRow">
                <StatusPill status={proposal.status} />
                <Badge>v{proposal.proposedVersion}</Badge>
                <Badge>{proposal.synthesizerProvider}</Badge>
                <Badge>{duration(proposal.synthesisDurationMs)}</Badge>
                {proposal.appliedVersionId ? <Badge>applied {proposal.appliedVersionId}</Badge> : null}
              </span>
            </div>
            {proposal.status === "draft" ? (
              <button className="secondaryButton emphasized" disabled={running} onClick={() => onApply(proposal.id)}>
                <ChevronRight size={16} aria-hidden="true" />
                Apply
              </button>
            ) : null}
          </div>
          <div className="proposalGrid">
            <div>
              <h4>Diff</h4>
              <JsonBlock value={proposal.diff} compact />
            </div>
            <div>
              <h4>Evidence</h4>
              <JsonBlock value={proposal.evidence} compact />
            </div>
          </div>
          <details className="rawOutput">
            <summary>Proposed workflow JSON</summary>
            <pre>{pretty(proposal.proposedWorkflow)}</pre>
          </details>
        </article>
      ))}
    </div>
  );
}

function UpdatesView({ events }: { events: UpdateEvent[] }): React.ReactElement {
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

function RunsView({
  runs,
  stepRuns,
  onOpenTarget
}: {
  runs: WorkflowRun[];
  stepRuns: StepRun[];
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
          return (
            <article className="runCard" key={run.id}>
              <div className="runCardHeader">
                <div>
                  <h3>Run #{run.id}</h3>
                  <p>{run.userRequest}</p>
                </div>
                <span className="metaRow">
                  <StatusPill status={run.status} />
                  <Badge>{duration(run.durationMs)}</Badge>
                  <Badge>{run.llmUsed ? "LLM" : "No LLM"}</Badge>
                  <Badge>{runStepRuns.length} steps</Badge>
                </span>
              </div>
              <ResultSummaryPanel result={getWorkflowRunResult(run)} onOpenTarget={onOpenTarget} />
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

function LatestRunResult({
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

function RunEvents({
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
            {event.stderr ? <pre className="stderr">{event.stderr}</pre> : null}
          </div>
        </article>
      ))}
    </div>
  );
}

function ResultSummaryPanel({
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
            <button className="linkButton" onClick={() => onOpenTarget(result.reportPath ?? "")}>
              <ExternalLink size={14} aria-hidden="true" />
              Report
            </button>
          ) : null}
          {result.outputUrl ? (
            <button className="linkButton" onClick={() => onOpenTarget(result.outputUrl ?? "")}>
              <ExternalLink size={14} aria-hidden="true" />
              URL
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

function PathField(props: {
  label: string;
  icon: React.ReactNode;
  value: string;
  onChange: (value: string) => void;
}): React.ReactElement {
  return (
    <label className="pathField">
      <span>
        {props.icon}
        {props.label}
      </span>
      <input value={props.value} onChange={(event) => props.onChange(event.target.value)} />
    </label>
  );
}

function TextField(props: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}): React.ReactElement {
  return (
    <label className="textField">
      <span>{props.label}</span>
      <input value={props.value} onChange={(event) => props.onChange(event.target.value)} />
    </label>
  );
}

function SelectField(props: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}): React.ReactElement {
  return (
    <label className="textField">
      <span>{props.label}</span>
      <select value={props.value} onChange={(event) => props.onChange(event.target.value)}>
        {props.options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function NumberField(props: {
  label: string;
  value: number;
  onChange: (value: number) => void;
}): React.ReactElement {
  return (
    <label className="textField compact">
      <span>{props.label}</span>
      <input
        type="number"
        min={0}
        max={10}
        value={props.value}
        onChange={(event) => props.onChange(Number(event.target.value))}
      />
    </label>
  );
}

function IconButton(props: {
  label: string;
  title: string;
  disabled?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}): React.ReactElement {
  return (
    <button
      className="iconButton"
      aria-label={props.label}
      title={props.title}
      disabled={props.disabled}
      onClick={props.onClick}
    >
      {props.children}
    </button>
  );
}

function IconTextButton(props: {
  label: string;
  title: string;
  disabled?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}): React.ReactElement {
  return (
    <button className="secondaryButton" title={props.title} disabled={props.disabled} onClick={props.onClick}>
      {props.children}
      {props.label}
    </button>
  );
}

function SectionTitle({ icon, title }: { icon: React.ReactNode; title: string }): React.ReactElement {
  return (
    <div className="sectionTitle">
      {icon}
      <h3>{title}</h3>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }): React.ReactElement {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Badge({ children }: { children: React.ReactNode }): React.ReactElement {
  return <span className="badge">{children}</span>;
}

function StatusPill({ status }: { status: string }): React.ReactElement {
  return <span className={`statusPill ${status}`}>{status}</span>;
}

function JsonBlock({ value, compact = false }: { value: unknown; compact?: boolean }): React.ReactElement {
  return <pre className={compact ? "jsonBlock compact" : "jsonBlock"}>{pretty(value)}</pre>;
}

function pretty(value: unknown): string {
  if (value === undefined || value === null) {
    return "";
  }
  if (typeof value === "string") {
    return value;
  }
  return JSON.stringify(value, null, 2);
}

function duration(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "-";
  }
  return `${value} ms`;
}

function eventLabel(event: RunEvent): string {
  if (event.type.startsWith("update-proposal")) {
    return `${event.workflowName ?? "workflow"} proposal ${event.type.endsWith("finished") ? "finished" : "started"}`;
  }
  if (event.type.startsWith("update-apply")) {
    return `proposal #${event.proposalId ?? "-"} apply ${event.type.endsWith("finished") ? "finished" : "started"}`;
  }
  if (event.version) {
    return `${event.workflowName ?? "workflow"} v${event.version} ${event.headed ? "headed" : "headless"}`;
  }
  return event.type.replaceAll("-", " ");
}

function errorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function webmcpErrorMessage(error: unknown): string {
  const message = errorMessage(error);
  if (message.includes("No handler registered for 'webmcp:propose-update'")) {
    return "Electron main process is stale. Stop the app and run npm run dev again.";
  }
  return message;
}

createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
