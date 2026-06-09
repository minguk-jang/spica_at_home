import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  Bot,
  Brain,
  ChevronRight,
  Database,
  Eye,
  ExternalLink,
  FileText,
  Gauge,
  Globe2,
  History,
  Layers,
  Lightbulb,
  ListChecks,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Route,
  ScrollText,
  Search,
  ShieldCheck,
  Sparkles,
  Terminal,
  Workflow,
  X
} from "lucide-react";
import type {
  CreateWorkflowPayload,
  DefaultPaths,
  EvolveWorkflowPayload,
  ApplyProposalPayload,
  MemoryOverview,
  PageAnalysisMemory,
  RunEvent,
  RunPayload,
  StepRun,
  UpdateEvent,
  UpdateProposalPayload,
  WorkflowKnowledgeMemory,
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
import {
  activeJobControlLabel,
  activeJobStatusText,
  activeJobTitle,
  type ActiveJob
} from "./activeJob";
import {
  summarizeEvolutionJobStatus,
  summarizeEvolutionOutput
} from "./evolutionSummary";
import {
  browserModeLabel,
  evolutionStatusLabel
} from "./evolutionDisplay";
import {
  buildVisibleRunControlFields,
  type VisibleRunControlField
} from "./runControlFields";
import {
  argumentExampleMeta,
  argumentDisplayRows,
  buildArgumentExamples,
  buildCreateWorkflowPayload,
  buildOperationControlState,
  buildStepCards,
  canCreateWorkflow,
  findLatestDraftProposal,
  storedRunDisplayStatus,
  type ArgumentExample
} from "./workflowDashboard";
import { normalizeWorkflowDetail } from "./workflowDetailDefaults";
import {
  coreLogicStages,
  desktopTabGuides,
  landingMetricItems,
  type CoreLogicStage,
  type LandingMetricItem
} from "./landingPage";
import "./styles.css";

type AppView = "home" | "workflows" | "jsTool" | "memory";
type MemoryFilter = "all" | "pages" | "knowledge";
type TabKey = "steps" | "script" | "jsTool" | "versions" | "update" | "updates" | "runs";

const fallbackPaths: DefaultPaths = {
  repoRoot: "../../core",
  dbPath: "~/.webmcp-studio/db/workflows.sqlite",
  outputDir: "../../core/outputs/desktop_runs",
  pythonPath: "../../core/reference/webwright/.venv/bin/python",
  sidecarPath: "rust/webmcp-sidecar/target/debug/webmcp-sidecar"
};

function App(): React.ReactElement {
  const [appView, setAppView] = useState<AppView>("home");
  const [paths, setPaths] = useState<DefaultPaths>(fallbackPaths);
  const [dbPath, setDbPath] = useState(fallbackPaths.dbPath);
  const [repoRoot, setRepoRoot] = useState(fallbackPaths.repoRoot);
  const [outputDir, setOutputDir] = useState(fallbackPaths.outputDir);
  const [pythonPath, setPythonPath] = useState(fallbackPaths.pythonPath);
  const [memoryOverview, setMemoryOverview] = useState<MemoryOverview | null>(null);
  const [memoryLoading, setMemoryLoading] = useState(false);
  const [memoryQuery, setMemoryQuery] = useState("");
  const [memoryFilter, setMemoryFilter] = useState<MemoryFilter>("all");
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
  const [extraArguments, setExtraArguments] = useState<Record<string, unknown>>({});
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const [updateInstruction, setUpdateInstruction] = useState("");
  const [updateMode, setUpdateMode] = useState<UpdateMode>("code-only");
  const [updateModel, setUpdateModel] = useState("gpt-5.5");
  const [evolveMaxAttempts, setEvolveMaxAttempts] = useState(3);
  const [evolutionResultEvent, setEvolutionResultEvent] = useState<RunEvent | null>(null);
  const [evolutionModalOpen, setEvolutionModalOpen] = useState(false);
  const [pendingEvolutionProposalId, setPendingEvolutionProposalId] = useState<number | null>(null);
  const [createPanelOpen, setCreatePanelOpen] = useState(false);
  const [createStartUrl, setCreateStartUrl] = useState("https://www.google.com/flights");
  const [createTask, setCreateTask] = useState("Search for flights from SEA to JFK on 2026-08-15 to 2026-08-20");
  const [createFinalState, setCreateFinalState] = useState("Flight results for SEA to JFK are visible with outbound and return dates applied.");
  const [createHeaded, setCreateHeaded] = useState(true);
  const [creationResultEvent, setCreationResultEvent] = useState<RunEvent | null>(null);
  const [jsToolOutputDir, setJsToolOutputDir] = useState(`${fallbackPaths.outputDir}/js_tools`);
  const [jsToolDir, setJsToolDir] = useState("");
  const [jsToolArgumentsJson, setJsToolArgumentsJson] = useState("{}");
  const [jsToolRequiredOutput, setJsToolRequiredOutput] = useState("");
  const [jsToolResultEvent, setJsToolResultEvent] = useState<RunEvent | null>(null);
  const [activeJob, setActiveJob] = useState<ActiveJob | null>(null);

  const selectedWorkflow = workflows.find((workflow) => workflow.id === selectedId) ?? workflows[0] ?? null;
  const selectedWorkflowId = selectedWorkflow?.id ?? null;
  const latestFinishedEvent = useMemo(
    () => events.find((event) => event.type === "job-finished") ?? null,
    [events]
  );
  const latestEvolutionEvent = useMemo(
    () => events.find((event) => event.type === "evolution-finished") ?? null,
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
  const pendingEvolutionProposal = useMemo(() => {
    if (!detail) {
      return null;
    }
    return (
      detail.proposals.find((proposal) => proposal.id === pendingEvolutionProposalId) ??
      findLatestDraftProposal(detail.proposals)
    );
  }, [detail, pendingEvolutionProposalId]);
  const operationControl = buildOperationControlState({
    running,
    paused: activeJob?.paused ?? false
  });
  const jobActive = activeJob !== null;

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
        setJsToolOutputDir(`${defaults.outputDir}/js_tools`);
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
    setExtraArguments({});
  }, [selectedWorkflowId]);

  useEffect(() => {
    if (!detail) {
      return;
    }
    applyWorkflowRunDefaults(detail);
  }, [detail?.workflow.id]);

  useEffect(() => {
    if (!detail) {
      return;
    }
    setJsToolArgumentsJson(defaultJsToolArgumentsJson(detail));
    setJsToolRequiredOutput(defaultRequiredOutputKeys(detail, selectedVersion).join("\n"));
    setJsToolDir("");
    setJsToolResultEvent(null);
  }, [detail?.workflow.id, selectedVersion]);

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

  async function refreshMemory(pathOverride = dbPath, announce = true): Promise<void> {
    if (!window.webmcp) {
      setStatus("Electron bridge is not available.");
      return;
    }
    setMemoryLoading(true);
    if (announce) {
      setStatus("Loading page analysis and knowledge");
    }
    try {
      const overview = await window.webmcp.getMemoryOverview(pathOverride);
      setMemoryOverview(overview);
      if (announce) {
        setStatus(`${overview.pageAnalysisCount} page analyses, ${overview.knowledgeEntryCount} knowledge entries loaded`);
      }
    } catch (error: unknown) {
      setStatus(errorMessage(error));
    } finally {
      setMemoryLoading(false);
    }
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
    const argumentPayload = selectedRunArgumentPayload();
    return {
      dbPath,
      repoRoot,
      outputDir,
      pythonPath,
      workflowName: detail?.workflow.name ?? selectedWorkflow?.name ?? "",
      request,
      ...argumentPayload,
      ...extra
    };
  }

  function applyArgumentExample(example: ArgumentExample): void {
    setRequest(example.values.request);
    setCompanyName(example.values.companyName);
    setTicker(example.values.ticker);
    setNewsLimit(example.values.newsLimit);
    setExtraArguments(example.values.extraArguments);
  }

  function applyWorkflowRunDefaults(workflowDetail: WorkflowDetail): void {
    const firstExample = buildArgumentExamples(workflowDetail.examples)[0];
    if (firstExample) {
      applyArgumentExample(firstExample);
      return;
    }

    const fields = buildVisibleRunControlFields(workflowDetail.arguments);
    const nextExtraArguments: Record<string, unknown> = {};
    let nextCompanyName = "";
    let nextTicker = "";
    let nextNewsLimit = 3;

    for (const field of fields) {
      if (!field.argumentName) {
        continue;
      }
      const argument = workflowDetail.arguments.find((item) => item.name === field.argumentName);
      const value = argument ? defaultRunValue(argument) : undefined;
      if (value === undefined) {
        continue;
      }
      if (field.role === "companyName") {
        nextCompanyName = String(value);
      } else if (field.role === "ticker") {
        nextTicker = String(value);
      } else if (field.role === "newsLimit") {
        nextNewsLimit = numberFromUnknown(value, 3);
      } else if (field.role === "extraArgument") {
        nextExtraArguments[field.argumentName] = value;
      }
    }

    setCompanyName(nextCompanyName);
    setTicker(nextTicker);
    setNewsLimit(nextNewsLimit);
    setExtraArguments(nextExtraArguments);
  }

  function selectedRunArgumentPayload(): Pick<RunPayload, "companyName" | "ticker" | "newsLimit" | "extraArguments"> {
    const fields = detail ? buildVisibleRunControlFields(detail.arguments) : [];
    const payload: Pick<RunPayload, "companyName" | "ticker" | "newsLimit" | "extraArguments"> = {};
    const hasRole = (role: VisibleRunControlField["role"]) => fields.some((field) => field.role === role);

    if (hasRole("companyName") && companyName.trim()) {
      payload.companyName = companyName.trim();
    }
    if (hasRole("ticker") && ticker.trim()) {
      payload.ticker = ticker.trim();
    }
    if (hasRole("newsLimit")) {
      payload.newsLimit = newsLimit;
    }

    const allowedExtraArguments = new Set(
      fields
        .filter((field) => field.role === "extraArgument" && field.argumentName)
        .map((field) => field.argumentName as string)
    );
    const nextExtraArguments = Object.fromEntries(
      Object.entries(extraArguments).filter(([key, value]) =>
        allowedExtraArguments.has(key) && value !== undefined && value !== null && value !== ""
      )
    );
    if (Object.keys(nextExtraArguments).length > 0) {
      payload.extraArguments = nextExtraArguments;
    }

    return payload;
  }

  function setExtraArgument(name: string, value: unknown): void {
    setExtraArguments((current) => ({
      ...current,
      [name]: value
    }));
  }

  function beginActiveJob(job: Omit<ActiveJob, "paused">): void {
    setActiveJob({ ...job, paused: false });
    setRunning(true);
    setEvents([]);
  }

  function finishActiveJob(): void {
    setActiveJob(null);
    setRunning(false);
  }

  function setActiveJobPaused(paused: boolean): void {
    setActiveJob((current) => current ? { ...current, paused } : current);
  }

  async function runSelectedVersion(headed: boolean, versionOverride?: number): Promise<void> {
    const versionToRun = versionOverride ?? selectedVersion;
    if (!window.webmcp || !detail || versionToRun === null) {
      return;
    }
    beginActiveJob({ kind: "run", workflowName: detail.workflow.name, version: versionToRun });
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
      finishActiveJob();
    }
  }

  async function generateUpdateProposal(): Promise<void> {
    if (!window.webmcp || !detail || selectedVersion === null || !updateInstruction.trim()) {
      return;
    }
    beginActiveJob({ kind: "update", workflowName: detail.workflow.name, version: selectedVersion });
    try {
      const argumentPayload = selectedRunArgumentPayload();
      const payload: UpdateProposalPayload = {
        dbPath,
        repoRoot,
        outputDir,
        pythonPath,
        workflowName: detail.workflow.name,
        baseVersion: selectedVersion,
        instruction: updateInstruction,
        companyName: argumentPayload.companyName,
        ticker: argumentPayload.ticker,
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
      finishActiveJob();
    }
  }

  async function applyUpdateProposal(proposalId: number): Promise<void> {
    if (!window.webmcp || !detail) {
      return;
    }
    beginActiveJob({ kind: "apply", proposalId });
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
      finishActiveJob();
    }
  }

  async function runEvolutionLoop(): Promise<void> {
    if (!window.webmcp || !detail || selectedVersion === null) {
      return;
    }
    beginActiveJob({ kind: "evolution", workflowName: detail.workflow.name, version: selectedVersion });
    try {
      const argumentPayload = selectedRunArgumentPayload();
      const payload: EvolveWorkflowPayload = {
        dbPath,
        repoRoot,
        outputDir,
        pythonPath,
        workflowName: detail.workflow.name,
        baseVersion: selectedVersion,
        request,
        ...argumentPayload,
        maxAttempts: Math.max(1, evolveMaxAttempts),
        repairSynthesizer: "codex",
        synthesizerModel: updateModel,
        headed: true,
        evalBrowser: "chromium"
      };
      const result = await window.webmcp.evolveWorkflow(payload);
      const resultStatus = summarizeEvolutionJobStatus(result);
      const workflowId = detail.workflow.id;
      await refresh();
      const loadedDetail = await loadWorkflowDetail(workflowId);
      const latestDraft = findLatestDraftProposal(loadedDetail?.proposals ?? []);
      setEvolutionResultEvent(asRunEvent(result, "evolution-finished"));
      setPendingEvolutionProposalId(latestDraft?.id ?? null);
      setEvolutionModalOpen(true);
      setTab("update");
      setStatus(`Evolution job ${resultStatus} for v${selectedVersion}`);
    } catch (error: unknown) {
      setStatus(webmcpErrorMessage(error));
    } finally {
      finishActiveJob();
    }
  }

  async function createWorkflowFromBrowserTask(): Promise<void> {
    if (!window.webmcp || !canCreateWorkflow({
      startUrl: createStartUrl,
      task: createTask,
      finalState: createFinalState
    })) {
      return;
    }
    beginActiveJob({ kind: "creation", startUrl: createStartUrl });
    try {
      const payload: CreateWorkflowPayload = buildCreateWorkflowPayload({
        dbPath,
        repoRoot,
        outputDir,
        pythonPath,
        startUrl: createStartUrl,
        task: createTask,
        finalState: createFinalState,
        headed: createHeaded,
        synthesizerModel: updateModel
      });
      const result = await window.webmcp.createWorkflow(payload);
      const event = asRunEvent(result, "creation-finished");
      const output = event.output && typeof event.output === "object"
        ? event.output as { created_skill_id?: unknown; status?: unknown }
        : {};
      setCreationResultEvent(event);
      await refresh();
      if (typeof output.created_skill_id === "number") {
        setSelectedId(output.created_skill_id);
        await loadWorkflowDetail(output.created_skill_id);
        setTab("steps");
      }
      if (output.status === "succeeded") {
        setCreatePanelOpen(false);
      }
      setStatus(`Creation job ${String(output.status ?? event.status ?? "finished")}`);
    } catch (error: unknown) {
      setStatus(webmcpErrorMessage(error));
    } finally {
      finishActiveJob();
    }
  }

  async function exportSelectedJsTool(): Promise<void> {
    if (!window.webmcp || !detail || selectedVersion === null) {
      return;
    }
    beginActiveJob({ kind: "jsTool", workflowName: detail.workflow.name, version: selectedVersion });
    try {
      const result = await window.webmcp.exportJsTool({
        dbPath,
        repoRoot,
        outputDir: jsToolOutputDir,
        pythonPath,
        workflowName: detail.workflow.name,
        version: selectedVersion
      });
      const event = asRunEvent(result, "js-tool-export-finished");
      setJsToolResultEvent(event);
      const output = asRecord(event.output);
      const exportedToolDir = firstStringFromKeys(output, "tool_dir", "toolDir");
      if (exportedToolDir) {
        setJsToolDir(exportedToolDir);
      }
      setStatus(`JavaScript tool export ${event.status ?? "finished"}`);
    } catch (error: unknown) {
      setStatus(webmcpErrorMessage(error));
    } finally {
      finishActiveJob();
    }
  }

  async function runExportedJsTool(): Promise<void> {
    if (!window.webmcp || !jsToolDir.trim()) {
      return;
    }
    const parsed = parseJsonObject(jsToolArgumentsJson);
    if (!parsed.ok) {
      setStatus(parsed.error);
      return;
    }
    beginActiveJob({ kind: "jsTool", workflowName: detail?.workflow.name, version: selectedVersion ?? undefined });
    try {
      const result = await window.webmcp.runJsTool({
        repoRoot,
        pythonPath,
        toolDir: jsToolDir.trim(),
        arguments: parsed.value
      });
      const event = asRunEvent(result, "js-tool-run-finished");
      setJsToolResultEvent(event);
      setStatus(`JavaScript tool run ${event.status ?? "finished"}`);
    } catch (error: unknown) {
      setStatus(webmcpErrorMessage(error));
    } finally {
      finishActiveJob();
    }
  }

  async function evalExportedJsTool(): Promise<void> {
    if (!window.webmcp || !jsToolDir.trim()) {
      return;
    }
    const parsed = parseJsonObject(jsToolArgumentsJson);
    if (!parsed.ok) {
      setStatus(parsed.error);
      return;
    }
    beginActiveJob({ kind: "jsTool", workflowName: detail?.workflow.name, version: selectedVersion ?? undefined });
    try {
      const result = await window.webmcp.evalJsTool({
        repoRoot,
        pythonPath,
        toolDir: jsToolDir.trim(),
        arguments: parsed.value,
        requiredOutput: parseRequiredOutputKeys(jsToolRequiredOutput)
      });
      const event = asRunEvent(result, "js-tool-eval-finished");
      setJsToolResultEvent(event);
      const output = asRecord(event.output);
      const passed = output.passed === true ? "passed" : event.status ?? "finished";
      setStatus(`JavaScript tool eval ${passed}`);
    } catch (error: unknown) {
      setStatus(webmcpErrorMessage(error));
    } finally {
      finishActiveJob();
    }
  }

  async function pauseCurrentJob(): Promise<void> {
    if (!window.webmcp) {
      return;
    }
    try {
      const result = await window.webmcp.pauseCurrentJob();
      const nextStatus = controlStatus(result);
      setActiveJobPaused(nextStatus === "paused");
      setStatus(`Job pause ${nextStatus}`);
    } catch (error: unknown) {
      setStatus(webmcpErrorMessage(error));
    }
  }

  async function resumeCurrentJob(): Promise<void> {
    if (!window.webmcp) {
      return;
    }
    try {
      const result = await window.webmcp.resumeCurrentJob();
      const nextStatus = controlStatus(result);
      setActiveJobPaused(nextStatus === "paused");
      setStatus(`Job resume ${nextStatus}`);
    } catch (error: unknown) {
      setStatus(webmcpErrorMessage(error));
    }
  }

  async function approveEvolutionResult(): Promise<void> {
    const proposalId = pendingEvolutionProposal?.id ?? null;
    if (proposalId === null) {
      setStatus("No draft proposal is available to approve.");
      return;
    }
    setEvolutionModalOpen(false);
    await applyUpdateProposal(proposalId);
  }

  function rejectEvolutionResult(): void {
    setEvolutionModalOpen(false);
    setPendingEvolutionProposalId(null);
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
        <AppNav
          active={appView}
          onSelect={(view) => {
            setAppView(view);
            if (view === "memory" && memoryOverview === null && !memoryLoading) {
              void refreshMemory();
            }
          }}
        />
        <div className="topActions">
          <ActiveJobStrip
            job={activeJob}
            onPause={() => void pauseCurrentJob()}
            onResume={() => void resumeCurrentJob()}
          />
          <IconButton
            label="Refresh"
            title={appView === "memory" ? "Refresh memory" : "Refresh workflows"}
            onClick={() => void (appView === "memory" ? refreshMemory() : refresh())}
            disabled={operationControl.busy || memoryLoading}
          >
            <RefreshCw size={17} />
          </IconButton>
        </div>
      </header>

      {appView === "home" ? (
        <LandingView
          workflows={workflows}
          memoryOverview={memoryOverview}
          onCreate={() => setCreatePanelOpen(true)}
          onOpenWorkflows={() => setAppView("workflows")}
          onOpenJsTool={() => setAppView("jsTool")}
          onOpenMemory={() => {
            setAppView("memory");
            if (memoryOverview === null && !memoryLoading) {
              void refreshMemory();
            }
          }}
        />
      ) : appView === "workflows" ? (
      <section className="contentGrid">
        <aside className="sidebar" aria-label="Workflow list">
          <div className="sidebarHeader">
            <span>Tool List</span>
            <span className="sidebarHeaderActions">
              <strong>{workflows.length}</strong>
              <IconButton
                label="Create workflow"
                title="Create workflow"
                onClick={() => setCreatePanelOpen(true)}
                disabled={operationControl.busy}
                variant="plain"
              >
                <Plus size={16} aria-hidden="true" />
              </IconButton>
            </span>
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
              <WorkflowMainDashboard
                detail={detail}
                request={request}
                setRequest={setRequest}
                companyName={companyName}
                setCompanyName={setCompanyName}
                ticker={ticker}
                setTicker={setTicker}
                newsLimit={newsLimit}
                setNewsLimit={setNewsLimit}
                extraArguments={extraArguments}
                setExtraArgument={setExtraArgument}
                selectedVersion={selectedVersion}
                evolveMaxAttempts={evolveMaxAttempts}
                setEvolveMaxAttempts={setEvolveMaxAttempts}
                latestEvolutionEvent={latestEvolutionEvent}
                onApplyExample={applyArgumentExample}
                running={jobActive}
                onRunHeaded={() => void runSelectedVersion(true)}
                onEvolve={() => void runEvolutionLoop()}
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
              {tab === "jsTool" ? (
                <JsToolStudio
                  detail={detail}
                  selectedVersion={selectedVersion}
                  outputDir={jsToolOutputDir}
                  setOutputDir={setJsToolOutputDir}
                  toolDir={jsToolDir}
                  setToolDir={setJsToolDir}
                  argumentsJson={jsToolArgumentsJson}
                  setArgumentsJson={setJsToolArgumentsJson}
                  requiredOutput={jsToolRequiredOutput}
                  setRequiredOutput={setJsToolRequiredOutput}
                  latestEvent={jsToolResultEvent}
                  running={jobActive}
                  onExport={() => void exportSelectedJsTool()}
                  onRun={() => void runExportedJsTool()}
                  onEval={() => void evalExportedJsTool()}
                  onOpenTarget={(targetPath) => void window.webmcp?.openPath(targetPath)}
                />
              ) : null}
              {tab === "versions" ? (
                <VersionsView
                  versions={detail.versions}
                  selectedVersion={selectedVersion}
                  onSelectVersion={setSelectedVersion}
                  running={jobActive}
                  locked={operationControl.busy}
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
                  running={jobActive}
                  onGenerate={() => void generateUpdateProposal()}
                  onApply={(proposalId) => void applyUpdateProposal(proposalId)}
                />
              ) : null}
              {tab === "updates" ? <UpdatesView events={detail.updateEvents} /> : null}
              {tab === "runs" ? (
                <RunsView
                  runs={detail.runs}
                  stepRuns={detail.stepRuns}
                  activeJobRunning={jobActive}
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
      ) : appView === "jsTool" ? (
        <JsToolAppView
          workflows={workflows}
          selectedWorkflow={selectedWorkflow}
          detail={detail}
          selectedVersion={selectedVersion}
          outputDir={jsToolOutputDir}
          setOutputDir={setJsToolOutputDir}
          toolDir={jsToolDir}
          setToolDir={setJsToolDir}
          argumentsJson={jsToolArgumentsJson}
          setArgumentsJson={setJsToolArgumentsJson}
          requiredOutput={jsToolRequiredOutput}
          setRequiredOutput={setJsToolRequiredOutput}
          latestEvent={jsToolResultEvent}
          running={jobActive}
          events={events}
          onSelectWorkflow={setSelectedId}
          onCreate={() => setCreatePanelOpen(true)}
          onExport={() => void exportSelectedJsTool()}
          onRun={() => void runExportedJsTool()}
          onEval={() => void evalExportedJsTool()}
          onOpenTarget={(targetPath) => void window.webmcp?.openPath(targetPath)}
        />
      ) : (
        <MemoryView
          overview={memoryOverview}
          dbPath={dbPath}
          loading={memoryLoading}
          query={memoryQuery}
          setQuery={setMemoryQuery}
          filter={memoryFilter}
          setFilter={setMemoryFilter}
          onRefresh={() => void refreshMemory()}
        />
      )}
      <EvolutionResultModal
        open={evolutionModalOpen}
        event={evolutionResultEvent}
        proposal={pendingEvolutionProposal}
        running={jobActive}
        onOpenTarget={(targetPath) => void window.webmcp?.openPath(targetPath)}
        onApprove={() => void approveEvolutionResult()}
        onReject={rejectEvolutionResult}
      />
      <CreateWorkflowSheet
        open={createPanelOpen}
        running={jobActive}
        locked={operationControl.busy}
        startUrl={createStartUrl}
        setStartUrl={setCreateStartUrl}
        task={createTask}
        setTask={setCreateTask}
        finalState={createFinalState}
        setFinalState={setCreateFinalState}
        headed={createHeaded}
        setHeaded={setCreateHeaded}
        paused={activeJob?.kind === "creation" && activeJob.paused}
        showJobControl={activeJob?.kind === "creation"}
        model={updateModel}
        setModel={setUpdateModel}
        latestEvent={creationResultEvent}
        onOpenTarget={(targetPath) => void window.webmcp?.openPath(targetPath)}
        onCreate={() => void createWorkflowFromBrowserTask()}
        onPause={() => void pauseCurrentJob()}
        onResume={() => void resumeCurrentJob()}
        onClose={() => setCreatePanelOpen(false)}
      />
    </main>
  );
}

function AppNav({
  active,
  onSelect
}: {
  active: AppView;
  onSelect: (view: AppView) => void;
}): React.ReactElement {
  const items: Array<{ key: AppView; label: string; icon: React.ReactNode }> = [
    { key: "home", label: "홈", icon: <Gauge size={17} aria-hidden="true" /> },
    { key: "workflows", label: "워크플로우", icon: <Workflow size={17} aria-hidden="true" /> },
    { key: "jsTool", label: "JS 도구", icon: <Terminal size={17} aria-hidden="true" /> },
    { key: "memory", label: "메모리", icon: <Brain size={17} aria-hidden="true" /> }
  ];
  return (
    <nav className="appNav" aria-label="App sections">
      {items.map((item) => (
        <button
          key={item.key}
          className={active === item.key ? "appNavButton active" : "appNavButton"}
          type="button"
          aria-label={item.label}
          aria-pressed={active === item.key}
          title={item.label}
          onClick={() => onSelect(item.key)}
        >
          {item.icon}
          <span className="srOnly">{item.label}</span>
        </button>
      ))}
    </nav>
  );
}

function JsToolAppView(props: {
  workflows: WorkflowCard[];
  selectedWorkflow: WorkflowCard | null;
  detail: WorkflowDetail | null;
  selectedVersion: number | null;
  outputDir: string;
  setOutputDir: (value: string) => void;
  toolDir: string;
  setToolDir: (value: string) => void;
  argumentsJson: string;
  setArgumentsJson: (value: string) => void;
  requiredOutput: string;
  setRequiredOutput: (value: string) => void;
  latestEvent: RunEvent | null;
  running: boolean;
  events: RunEvent[];
  onSelectWorkflow: (workflowId: number) => void;
  onCreate: () => void;
  onExport: () => void;
  onRun: () => void;
  onEval: () => void;
  onOpenTarget: (path: string) => void;
}): React.ReactElement {
  return (
    <section className="contentGrid jsToolAppShell">
      <aside className="sidebar" aria-label="Workflow list for JavaScript tools">
        <div className="sidebarHeader">
          <span>Tool List</span>
          <span className="sidebarHeaderActions">
            <strong>{props.workflows.length}</strong>
            <IconButton
              label="Create workflow"
              title="Create workflow"
              onClick={props.onCreate}
              disabled={props.running}
              variant="plain"
            >
              <Plus size={16} aria-hidden="true" />
            </IconButton>
          </span>
        </div>
        <div className="workflowList">
          {props.workflows.map((workflow) => (
            <WorkflowCardButton
              key={workflow.id}
              workflow={workflow}
              selected={workflow.id === props.selectedWorkflow?.id}
              onClick={() => props.onSelectWorkflow(workflow.id)}
            />
          ))}
          {props.workflows.length === 0 ? <div className="emptyState">No workflows found</div> : null}
        </div>
      </aside>

      <section className="detailPane">
        {!props.detail ? (
          <div className="emptyState large">Select a WebMCP workflow to export as a JavaScript tool</div>
        ) : (
          <>
            <DetailHeader detail={props.detail} />
            <JsToolStudio
              detail={props.detail}
              selectedVersion={props.selectedVersion}
              outputDir={props.outputDir}
              setOutputDir={props.setOutputDir}
              toolDir={props.toolDir}
              setToolDir={props.setToolDir}
              argumentsJson={props.argumentsJson}
              setArgumentsJson={props.setArgumentsJson}
              requiredOutput={props.requiredOutput}
              setRequiredOutput={props.setRequiredOutput}
              latestEvent={props.latestEvent}
              running={props.running}
              onExport={props.onExport}
              onRun={props.onRun}
              onEval={props.onEval}
              onOpenTarget={props.onOpenTarget}
            />
          </>
        )}
      </section>

      <aside className="queuePane" aria-label="JavaScript tool queue">
        <div className="sidebarHeader">
          <span>Run Queue</span>
          <strong>{props.events.length}</strong>
        </div>
        <RunEvents events={props.events} onOpenTarget={props.onOpenTarget} />
      </aside>
    </section>
  );
}

function LandingView({
  workflows,
  memoryOverview,
  onCreate,
  onOpenWorkflows,
  onOpenJsTool,
  onOpenMemory
}: {
  workflows: WorkflowCard[];
  memoryOverview: MemoryOverview | null;
  onCreate: () => void;
  onOpenWorkflows: () => void;
  onOpenJsTool: () => void;
  onOpenMemory: () => void;
}): React.ReactElement {
  return (
    <section className="landingShell" aria-label="WebMCP Desktop 개요">
      <header className="landingHero">
        <div className="landingHeroCopy">
          <p className="eyebrow">개요</p>
          <h2>브라우저 요청에서 재사용 가능한 워크플로우까지</h2>
          <p>
            WebMCP Desktop은 사람이 원하는 브라우저 작업을 저장 가능한 워크플로우로 만들고,
            실제 브라우저 증거로 실행과 평가를 마친 뒤 다음 생성을 위한 페이지 지식을 남깁니다.
          </p>
          <div className="landingActions">
            <button className="primaryButton" type="button" onClick={onCreate}>
              <Plus size={16} aria-hidden="true" />
              워크플로우 생성
            </button>
            <button className="secondaryButton" type="button" onClick={onOpenWorkflows}>
              <Workflow size={16} aria-hidden="true" />
              워크플로우 열기
            </button>
            <button className="secondaryButton" type="button" onClick={onOpenJsTool}>
              <Terminal size={16} aria-hidden="true" />
              JS 도구
            </button>
            <button className="secondaryButton" type="button" onClick={onOpenMemory}>
              <Brain size={16} aria-hidden="true" />
              메모리 열기
            </button>
          </div>
        </div>
        <div className="landingMetricGrid" aria-label="스튜디오 상태">
          {landingMetricItems.map((item) => (
            <LandingMetricCard key={item.id} item={item} workflows={workflows} memoryOverview={memoryOverview} />
          ))}
        </div>
      </header>

      <section className="landingSection" aria-labelledby="core-flow-title">
        <div className="landingSectionHeader">
          <SectionTitle icon={<Route size={17} />} title="코어 로직" />
          <h3 id="core-flow-title">생성, 실행, 평가, 메모리가 하나의 루프로 이어집니다.</h3>
        </div>
        <div className="logicDiagram" aria-label="코어 로직 다이어그램">
          {coreLogicStages.map((stage, index) => (
            <article className={`logicNode ${stage.accent}`} key={stage.id}>
              <div className="logicNodeTop">
                <span className={`logicIcon ${stage.accent}`}>{landingStageIcon(stage.id)}</span>
                <span className="logicStep">{String(index + 1).padStart(2, "0")}</span>
              </div>
              <h4>{stage.title}</h4>
              <p>{stage.summary}</p>
              <small>{stage.detail}</small>
            </article>
          ))}
        </div>
      </section>

      <section className="landingSection" aria-labelledby="tab-guide-title">
        <div className="landingSectionHeader">
          <SectionTitle icon={<ListChecks size={17} />} title="데스크톱 탭" />
          <h3 id="tab-guide-title">각 탭은 워크플로우 생명주기의 서로 다른 작업을 맡습니다.</h3>
        </div>
        <div className="tabGuideGrid">
          {desktopTabGuides.map((guide) => (
            <article className="tabGuideCard" key={guide.title}>
              <h4>{guide.title}</h4>
              <p>{guide.role}</p>
              <span>{guide.usage}</span>
            </article>
          ))}
        </div>
      </section>
    </section>
  );
}

function LandingMetricCard({
  item,
  workflows,
  memoryOverview
}: {
  item: LandingMetricItem;
  workflows: WorkflowCard[];
  memoryOverview: MemoryOverview | null;
}): React.ReactElement {
  return (
    <article className="landingMetric">
      <div className="landingMetricHeader">
        <span className="landingMetricIcon">{landingMetricIcon(item.id)}</span>
        <span>{item.label}</span>
      </div>
      <strong>{landingMetricValue(item, workflows, memoryOverview)}</strong>
      <p>{item.description}</p>
    </article>
  );
}

function landingMetricValue(
  item: LandingMetricItem,
  workflows: WorkflowCard[],
  memoryOverview: MemoryOverview | null
): string {
  if (item.id === "workflows") {
    return String(workflows.length);
  }
  if (item.id === "pageMemory") {
    return String(memoryOverview?.pageAnalysisCount ?? 0);
  }
  if (item.id === "knowledge") {
    return String(memoryOverview?.knowledgeEntryCount ?? 0);
  }
  return "Codex VLM";
}

function landingStageIcon(id: CoreLogicStage["id"]): React.ReactNode {
  switch (id) {
    case "request":
      return <Eye size={16} aria-hidden="true" />;
    case "create":
      return <Sparkles size={16} aria-hidden="true" />;
    case "store":
      return <Database size={16} aria-hidden="true" />;
    case "run":
      return <Play size={16} aria-hidden="true" />;
    case "jsTool":
      return <Terminal size={16} aria-hidden="true" />;
    case "evaluate":
      return <ShieldCheck size={16} aria-hidden="true" />;
    case "memory":
      return <Brain size={16} aria-hidden="true" />;
  }
}

function landingMetricIcon(id: LandingMetricItem["id"]): React.ReactNode {
  switch (id) {
    case "workflows":
      return <Workflow size={16} aria-hidden="true" />;
    case "pageMemory":
      return <Eye size={16} aria-hidden="true" />;
    case "knowledge":
      return <Lightbulb size={16} aria-hidden="true" />;
    case "evaluator":
      return <ShieldCheck size={16} aria-hidden="true" />;
  }
}

function MemoryView(props: {
  overview: MemoryOverview | null;
  dbPath: string;
  loading: boolean;
  query: string;
  setQuery: (value: string) => void;
  filter: MemoryFilter;
  setFilter: (value: MemoryFilter) => void;
  onRefresh: () => void;
}): React.ReactElement {
  const overview = props.overview ?? {
    pageAnalyses: [],
    knowledgeEntries: [],
    pageAnalysisCount: 0,
    knowledgeEntryCount: 0
  };
  const query = props.query.trim();
  const pageAnalyses = overview.pageAnalyses.filter((page) => memoryMatches(page, query));
  const knowledgeEntries = overview.knowledgeEntries.filter((entry) => memoryMatches(entry, query));
  const showPages = props.filter === "all" || props.filter === "pages";
  const showKnowledge = props.filter === "all" || props.filter === "knowledge";

  return (
    <section className="memoryShell" aria-label="Page analysis and workflow knowledge">
      <header className="memoryHeader">
        <div className="memoryTitleBlock">
          <p className="eyebrow">Studio Memory</p>
          <h2>Page Analysis & Knowledge</h2>
          <p>{props.dbPath}</p>
        </div>
        <div className="memoryToolbar">
          <label className="memorySearch">
            <Search size={16} aria-hidden="true" />
            <span className="srOnly">Search memory</span>
            <input
              value={props.query}
              placeholder="url, marker, handler, tip"
              onChange={(event) => props.setQuery(event.target.value)}
            />
          </label>
          <div className="memoryFilter" aria-label="Memory filter">
            {memoryFilterItems.map((item) => (
              <button
                key={item.key}
                className={props.filter === item.key ? "memoryFilterButton active" : "memoryFilterButton"}
                type="button"
                title={item.label}
                aria-label={item.label}
                aria-pressed={props.filter === item.key}
                onClick={() => props.setFilter(item.key)}
              >
                {item.icon}
                <span className="srOnly">{item.label}</span>
              </button>
            ))}
          </div>
          <IconButton
            label="Refresh memory"
            title="Refresh memory"
            onClick={props.onRefresh}
            disabled={props.loading}
            variant="plain"
          >
            <RefreshCw size={17} aria-hidden="true" />
          </IconButton>
        </div>
      </header>

      <div className="memorySummaryGrid">
        <MemoryMetric icon={<Globe2 size={16} />} label="Pages" value={overview.pageAnalysisCount} />
        <MemoryMetric icon={<Lightbulb size={16} />} label="Knowledge" value={overview.knowledgeEntryCount} />
        <MemoryMetric icon={<Layers size={16} />} label="Matched Pages" value={pageAnalyses.length} />
        <MemoryMetric icon={<Database size={16} />} label="Matched Tips" value={knowledgeEntries.length} />
      </div>

      {props.loading && props.overview === null ? (
        <div className="emptyState large">Loading memory</div>
      ) : null}

      <div className="memoryGrid">
        {showPages ? (
          <section className="memoryPanel">
            <div className="memoryPanelHeader">
              <SectionTitle icon={<Globe2 size={17} />} title="Page Analysis" />
              <Badge>{pageAnalyses.length}</Badge>
            </div>
            <div className="memoryList">
              {pageAnalyses.length === 0 ? <div className="emptyState">No page analysis found</div> : null}
              {pageAnalyses.map((page) => (
                <PageAnalysisCard key={page.id} page={page} />
              ))}
            </div>
          </section>
        ) : null}

        {showKnowledge ? (
          <section className="memoryPanel">
            <div className="memoryPanelHeader">
              <SectionTitle icon={<Lightbulb size={17} />} title="Script Knowledge" />
              <Badge>{knowledgeEntries.length}</Badge>
            </div>
            <div className="memoryList">
              {knowledgeEntries.length === 0 ? <div className="emptyState">No knowledge found</div> : null}
              {knowledgeEntries.map((entry) => (
                <KnowledgeCard key={entry.id} entry={entry} />
              ))}
            </div>
          </section>
        ) : null}
      </div>
    </section>
  );
}

const memoryFilterItems: Array<{ key: MemoryFilter; label: string; icon: React.ReactNode }> = [
  { key: "all", label: "All memory", icon: <Database size={16} aria-hidden="true" /> },
  { key: "pages", label: "Page analysis", icon: <Globe2 size={16} aria-hidden="true" /> },
  { key: "knowledge", label: "Script knowledge", icon: <Lightbulb size={16} aria-hidden="true" /> }
];

function MemoryMetric({
  icon,
  label,
  value
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
}): React.ReactElement {
  return (
    <div className="memoryMetric">
      {icon}
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function PageAnalysisCard({ page }: { page: PageAnalysisMemory }): React.ReactElement {
  const facts = pageAnalysisFacts(page);
  return (
    <article className="memoryItem">
      <div className="memoryItemHeader">
        <div>
          <h3>{page.title || page.urlKey}</h3>
          <p className="memoryUrl">{page.canonicalUrl}</p>
        </div>
        <span className="metaRow">
          <Badge>{facts.pageType}</Badge>
          <Badge>{page.source}</Badge>
          <Badge>{page.observationCount} seen</Badge>
        </span>
      </div>
      <TipGroup icon={<Lightbulb size={15} />} title="Tips" items={facts.tips} />
      <div className="memoryFactGrid">
        <TipGroup icon={<ShieldCheck size={15} />} title="Waits" items={facts.waits} compact />
        <TipGroup icon={<Layers size={15} />} title="Selectors" items={facts.selectors} compact />
        <TipGroup icon={<Globe2 size={15} />} title="Frames" items={facts.frames} compact />
        <TipGroup icon={<ShieldCheck size={15} />} title="Risks" items={facts.risks} compact />
      </div>
      <details className="rawOutput">
        <summary>Raw page analysis</summary>
        <pre>{pretty({ analysis: page.analysis, locatorHints: page.locatorHints, evidence: page.evidence })}</pre>
      </details>
    </article>
  );
}

function KnowledgeCard({ entry }: { entry: WorkflowKnowledgeMemory }): React.ReactElement {
  const facts = knowledgeFacts(entry);
  return (
    <article className="memoryItem">
      <div className="memoryItemHeader">
        <div>
          <h3>{entry.summary}</h3>
          {facts.urlShape ? <p className="memoryUrl">{facts.urlShape}</p> : null}
        </div>
        <span className="metaRow">
          <Badge>{entry.category}</Badge>
          <Badge>{entry.source}</Badge>
          <Badge>{formatConfidence(entry.confidence)}</Badge>
        </span>
      </div>
      {facts.tags.length > 0 ? (
        <span className="metaRow">
          {facts.tags.map((tag) => <Badge key={tag}>{tag}</Badge>)}
        </span>
      ) : null}
      <TipGroup icon={<Lightbulb size={15} />} title="Tips" items={facts.tips} />
      <div className="memoryFactGrid">
        <TipGroup icon={<ShieldCheck size={15} />} title="Assert" items={facts.assertions} compact />
        <TipGroup icon={<Layers size={15} />} title="Failures" items={facts.failures} compact />
        <TipGroup icon={<Globe2 size={15} />} title="Selectors" items={facts.selectors} compact />
        <TipGroup icon={<Database size={15} />} title="Outputs" items={facts.outputs} compact />
      </div>
      <details className="rawOutput">
        <summary>Raw knowledge</summary>
        <pre>{pretty(entry.content)}</pre>
      </details>
    </article>
  );
}

function TipGroup({
  icon,
  title,
  items,
  compact = false
}: {
  icon: React.ReactNode;
  title: string;
  items: string[];
  compact?: boolean;
}): React.ReactElement | null {
  if (items.length === 0) {
    return null;
  }
  return (
    <section className={compact ? "tipGroup compact" : "tipGroup"}>
      <h4>{icon}{title}</h4>
      <ul>
        {items.map((item) => <li key={item}>{item}</li>)}
      </ul>
    </section>
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

function ActiveJobStrip({
  job,
  onPause,
  onResume
}: {
  job: ActiveJob | null;
  onPause: () => void;
  onResume: () => void;
}): React.ReactElement | null {
  if (!job) {
    return null;
  }
  const controlLabel = activeJobControlLabel(job);
  return (
    <div className="activeJobStrip" aria-label={`${activeJobStatusText(job)}: ${activeJobTitle(job)}`}>
      <RefreshCw className={job.paused ? "activeJobSpinner paused" : "activeJobSpinner"} size={16} aria-hidden="true" />
      <span className="activeJobCopy">
        <strong>{activeJobTitle(job)}</strong>
        <small>{activeJobStatusText(job)}</small>
      </span>
      <IconButton
        label={controlLabel}
        title={controlLabel}
        onClick={job.paused ? onResume : onPause}
        variant="plain"
      >
        {job.paused ? <Play size={17} aria-hidden="true" /> : <Pause size={17} aria-hidden="true" />}
      </IconButton>
    </div>
  );
}

function CreateWorkflowSheet(props: {
  open: boolean;
  running: boolean;
  locked: boolean;
  startUrl: string;
  setStartUrl: (value: string) => void;
  task: string;
  setTask: (value: string) => void;
  finalState: string;
  setFinalState: (value: string) => void;
  headed: boolean;
  setHeaded: (value: boolean) => void;
  paused: boolean;
  showJobControl: boolean;
  model: string;
  setModel: (value: string) => void;
  latestEvent: RunEvent | null;
  onOpenTarget: (path: string) => void;
  onCreate: () => void;
  onPause: () => void;
  onResume: () => void;
  onClose: () => void;
}): React.ReactElement | null {
  if (!props.open) {
    return null;
  }
  const ready = canCreateWorkflow({
    startUrl: props.startUrl,
    task: props.task,
    finalState: props.finalState
  });
  return (
    <div className="modalBackdrop" role="presentation">
      <section className="modalPanel createPanel" role="dialog" aria-modal="true" aria-labelledby="create-workflow-title">
        <div className="modalHeader">
          <div>
            <p className="eyebrow">Create</p>
            <h2 id="create-workflow-title">새 WebMCP workflow</h2>
          </div>
          <IconButton
            label="Close create workflow"
            title="Close create workflow"
            onClick={props.onClose}
            disabled={props.locked}
            variant="plain"
          >
            <X size={17} aria-hidden="true" />
          </IconButton>
        </div>
        <div className="modalBody createBody">
          <TextField label="Start URL" value={props.startUrl} onChange={props.setStartUrl} />
          <label className="textAreaField">
            <span>Task</span>
            <textarea
              value={props.task}
              rows={3}
              onChange={(event) => props.setTask(event.target.value)}
            />
          </label>
          <label className="textAreaField">
            <span>Done State</span>
            <textarea
              value={props.finalState}
              rows={3}
              onChange={(event) => props.setFinalState(event.target.value)}
            />
          </label>
          <div className="createOptionGrid">
            <TextField label="Codex model" value={props.model} onChange={props.setModel} />
          </div>
          <SegmentedControl
            label="Browser"
            value={props.headed ? "headed" : "headless"}
            options={[
              { value: "headed", label: "Visible", title: "Run browser visibly while creating" },
              { value: "headless", label: "Background", title: "Run browser in the background" }
            ]}
            onChange={(value) => props.setHeaded(value === "headed")}
          />
          {props.latestEvent ? (
            <ResultSummaryPanel result={getRunEventResult(props.latestEvent)} onOpenTarget={props.onOpenTarget} />
          ) : null}
        </div>
        <div className="modalFooter">
          <button className="secondaryButton" type="button" disabled={props.locked} onClick={props.onClose}>
            닫기
          </button>
          {props.showJobControl ? (
            <IconButton
              label={props.paused ? "Resume job" : "Pause job"}
              title={props.paused ? "Resume job" : "Pause job"}
              onClick={props.paused ? props.onResume : props.onPause}
              variant="plain"
            >
              {props.paused ? <Play size={17} aria-hidden="true" /> : <Pause size={17} aria-hidden="true" />}
            </IconButton>
          ) : null}
          <button className="primaryButton" type="button" disabled={props.running || !ready} onClick={props.onCreate}>
            <Sparkles size={16} aria-hidden="true" />
            생성
          </button>
        </div>
      </section>
    </div>
  );
}

function WorkflowMainDashboard(props: {
  detail: WorkflowDetail;
  request: string;
  setRequest: (value: string) => void;
  companyName: string;
  setCompanyName: (value: string) => void;
  ticker: string;
  setTicker: (value: string) => void;
  newsLimit: number;
  setNewsLimit: (value: number) => void;
  extraArguments: Record<string, unknown>;
  setExtraArgument: (name: string, value: unknown) => void;
  selectedVersion: number | null;
  evolveMaxAttempts: number;
  setEvolveMaxAttempts: (value: number) => void;
  latestEvolutionEvent: RunEvent | null;
  onApplyExample: (example: ArgumentExample) => void;
  running: boolean;
  onRunHeaded: () => void;
  onEvolve: () => void;
}): React.ReactElement {
  const stepCards = buildStepCards(props.detail.steps);
  const argumentRows = argumentDisplayRows(props.detail.arguments);
  const examples = buildArgumentExamples(props.detail.examples);
  return (
    <section className="workflowDashboard">
      <div className="dashboardGrid">
        <div className="dashboardSection wide">
          <SectionTitle icon={<ListChecks size={17} />} title="Selected Version Steps" />
          <div className="dashboardStepList">
            {stepCards.map((step) => (
              <article className="dashboardStepRow" key={step.id}>
                <span className="stepIndex">{step.label.replace("Step ", "")}</span>
                <div>
                  <h3>{step.label}: {step.name}</h3>
                  <p>{step.description}</p>
                  <span className="metaRow">
                    <Badge>{step.type}</Badge>
                    {step.handlerRef ? <Badge>{step.handlerRef}</Badge> : null}
                  </span>
                </div>
              </article>
            ))}
          </div>
        </div>
        <div className="dashboardSection">
          <SectionTitle icon={<Terminal size={17} />} title="Arguments" />
          <div className="argumentSummaryList">
            {argumentRows.map((argument) => (
              <article className="argumentSummaryRow" key={argument.id}>
                <div>
                  <h3>{argument.name}</h3>
                  <p>{argument.description}</p>
                </div>
                <span className="metaRow">
                  <Badge>{argument.type}</Badge>
                  <Badge>{argument.required}</Badge>
                  <Badge>{argument.dynamic}</Badge>
                </span>
                {argument.examples !== "-" ? <p className="argumentExamples">예시: {argument.examples}</p> : null}
              </article>
            ))}
          </div>
        </div>
      </div>
      <ArgumentExamples examples={examples} onApplyExample={props.onApplyExample} />
      <RunControls
        request={props.request}
        setRequest={props.setRequest}
        companyName={props.companyName}
        setCompanyName={props.setCompanyName}
        ticker={props.ticker}
        setTicker={props.setTicker}
        newsLimit={props.newsLimit}
        setNewsLimit={props.setNewsLimit}
        workflowArguments={props.detail.arguments}
        extraArguments={props.extraArguments}
        setExtraArgument={props.setExtraArgument}
        selectedVersion={props.selectedVersion}
        running={props.running}
        onRunHeaded={props.onRunHeaded}
      />
      <EvolutionPanel
        workflowName={props.detail.workflow.name}
        selectedVersion={props.selectedVersion}
        maxAttempts={props.evolveMaxAttempts}
        setMaxAttempts={props.setEvolveMaxAttempts}
        latestEvent={props.latestEvolutionEvent}
        running={props.running}
        onEvolve={props.onEvolve}
      />
    </section>
  );
}

function ArgumentExamples({
  examples,
  onApplyExample
}: {
  examples: ArgumentExample[];
  onApplyExample: (example: ArgumentExample) => void;
}): React.ReactElement {
  if (examples.length === 0) {
    return (
      <section className="argumentExamplesPanel">
        <SectionTitle icon={<FileText size={17} />} title="Argument Examples" />
        <div className="emptyState">저장된 argument 예시가 없습니다.</div>
      </section>
    );
  }
  return (
    <section className="argumentExamplesPanel">
      <SectionTitle icon={<FileText size={17} />} title="Argument Examples" />
      <div className="exampleGrid">
        {examples.map((example) => (
          <button
            key={example.id}
            className="exampleButton"
            type="button"
            title={`${example.label} 예시 적용`}
            onClick={() => onApplyExample(example)}
          >
            <strong>{example.label}</strong>
            <span>{example.description}</span>
            <small>{argumentExampleMeta(example)}</small>
          </button>
        ))}
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
  workflowArguments: WorkflowArgument[];
  extraArguments: Record<string, unknown>;
  setExtraArgument: (name: string, value: unknown) => void;
  selectedVersion: number | null;
  running: boolean;
  onRunHeaded: () => void;
}): React.ReactElement {
  const fields = buildVisibleRunControlFields(props.workflowArguments);
  return (
    <section className="runControls">
      <div className="formGrid">
        {fields.map((field) => renderRunControlField(field, props))}
      </div>
      <div className="runActionRow">
        <div className="selectedVersionBadge" aria-label="Selected version">
          Selected {props.selectedVersion === null ? "-" : `v${props.selectedVersion}`}
        </div>
        <IconButton
          label="Run selected headed"
          title="Run selected version headed"
          variant="success"
          onClick={props.onRunHeaded}
          disabled={props.running || props.selectedVersion === null}
        >
          <Eye size={17} aria-hidden="true" />
        </IconButton>
      </div>
    </section>
  );
}

function renderRunControlField(
  field: VisibleRunControlField,
  props: {
    request: string;
    setRequest: (value: string) => void;
    companyName: string;
    setCompanyName: (value: string) => void;
    ticker: string;
    setTicker: (value: string) => void;
    newsLimit: number;
    setNewsLimit: (value: number) => void;
    extraArguments: Record<string, unknown>;
    setExtraArgument: (name: string, value: unknown) => void;
  }
): React.ReactElement {
  switch (field.role) {
    case "request":
      return <TextField key={field.key} label={field.label} value={props.request} onChange={props.setRequest} />;
    case "companyName":
      return <TextField key={field.key} label={field.label} value={props.companyName} onChange={props.setCompanyName} />;
    case "ticker":
      return <TextField key={field.key} label={field.label} value={props.ticker} onChange={props.setTicker} />;
    case "newsLimit":
      return <NumberField key={field.key} label={field.label} value={props.newsLimit} onChange={props.setNewsLimit} />;
    case "extraArgument": {
      const argumentName = field.argumentName ?? field.key;
      const value = props.extraArguments[argumentName];
      if (field.inputType === "number") {
        return (
          <NumberField
            key={field.key}
            label={field.label}
            value={numberFromUnknown(value, 0)}
            onChange={(nextValue) => props.setExtraArgument(argumentName, nextValue)}
          />
        );
      }
      if (field.inputType === "checkbox") {
        return (
          <CheckboxField
            key={field.key}
            label={field.label}
            checked={Boolean(value)}
            onChange={(nextValue) => props.setExtraArgument(argumentName, nextValue)}
          />
        );
      }
      return (
        <TextField
          key={field.key}
          label={field.label}
          value={stringFromUnknown(value)}
          onChange={(nextValue) => props.setExtraArgument(argumentName, nextValue)}
        />
      );
    }
  }
}

function Tabs({ active, onSelect }: { active: TabKey; onSelect: (tab: TabKey) => void }): React.ReactElement {
  const tabs: Array<{ key: TabKey; label: string; icon: React.ReactNode }> = [
    { key: "steps", label: "Steps", icon: <ListChecks size={16} /> },
    { key: "script", label: "Implementation", icon: <ScrollText size={16} /> },
    { key: "jsTool", label: "JS Tool", icon: <Terminal size={16} /> },
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
          aria-label={item.label}
          title={item.label}
          onClick={() => onSelect(item.key)}
        >
          {item.icon}
          <span className="srOnly">{item.label}</span>
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

function JsToolStudio(props: {
  detail: WorkflowDetail;
  selectedVersion: number | null;
  outputDir: string;
  setOutputDir: (value: string) => void;
  toolDir: string;
  setToolDir: (value: string) => void;
  argumentsJson: string;
  setArgumentsJson: (value: string) => void;
  requiredOutput: string;
  setRequiredOutput: (value: string) => void;
  latestEvent: RunEvent | null;
  running: boolean;
  onExport: () => void;
  onRun: () => void;
  onEval: () => void;
  onOpenTarget: (path: string) => void;
}): React.ReactElement {
  const selectedVersion = props.detail.versions.find((version) => version.version === props.selectedVersion) ?? props.detail.versions[0] ?? null;
  const requiredOutputKeys = parseRequiredOutputKeys(props.requiredOutput);
  const lastOutput = asRecord(props.latestEvent?.output);
  const exportedFiles = asRecord(lastOutput.files);
  const artifactEntries = Object.entries(exportedFiles).filter((entry): entry is [string, string] => typeof entry[1] === "string");
  const evalPassed = lastOutput.passed === true;
  const resultStatus = props.latestEvent
    ? evalPassed
      ? "passed"
      : props.latestEvent.status ?? String(lastOutput.status ?? "finished")
    : "";
  const canUseExportedTool = props.toolDir.trim() !== "";
  return (
    <section className="tabPanel jsToolStudio">
      <div className="jsToolHero">
        <div>
          <SectionTitle icon={<Terminal size={17} />} title="JavaScript Tool Lab" />
          <h3>도구를 JavaScript로 변환하고 테스트</h3>
          <p>
            선택한 workflow 버전을 `manifest.json`, `workflow.json`, `tool.cjs`로 export하고
            동일한 arguments로 run/eval contract를 확인합니다.
          </p>
        </div>
        <span className="metaRow">
          <Badge>{props.detail.workflow.name}</Badge>
          <Badge>{selectedVersion ? `v${selectedVersion.version}` : "version -"}</Badge>
          <Badge>webmcp-js-tool-v1</Badge>
          <Badge>{requiredOutputKeys.length} required output</Badge>
        </span>
      </div>

      <div className="jsToolGrid">
        <section className="jsToolPanel">
          <SectionTitle icon={<FileText size={17} />} title="Export" />
          <TextField label="Output directory" value={props.outputDir} onChange={props.setOutputDir} />
          <div className="jsToolActionRow">
            <button
              className="primaryButton jsToolActionButton"
              type="button"
              aria-label="Export JS tool"
              title="Export JS tool"
              disabled={props.running || props.selectedVersion === null || props.outputDir.trim() === ""}
              onClick={props.onExport}
            >
              <FileText size={16} aria-hidden="true" />
              <span>Export</span>
            </button>
          </div>
          <div className="jsToolFacts">
            <SummaryItem label="Input" value="Studio DB workflow version" />
            <SummaryItem label="Files" value="manifest, workflow, tool.cjs" />
            <SummaryItem label="Runtime" value="Node.js CommonJS" />
          </div>
        </section>

        <section className="jsToolPanel">
          <SectionTitle icon={<Play size={17} />} title="Run / Eval" />
          <TextField label="Exported tool directory" value={props.toolDir} onChange={props.setToolDir} />
          <label className="textAreaField">
            <span>Arguments JSON</span>
            <textarea
              value={props.argumentsJson}
              rows={8}
              spellCheck={false}
              onChange={(event) => props.setArgumentsJson(event.target.value)}
            />
          </label>
          <label className="textAreaField">
            <span>required output keys</span>
            <textarea
              value={props.requiredOutput}
              rows={3}
              spellCheck={false}
              onChange={(event) => props.setRequiredOutput(event.target.value)}
            />
          </label>
          <div className="jsToolActionRow">
            <button
              className="secondaryButton emphasized jsToolActionButton"
              type="button"
              aria-label="Run JS tool"
              title="Run JS tool"
              disabled={props.running || !canUseExportedTool}
              onClick={props.onRun}
            >
              <Play size={16} aria-hidden="true" />
              <span>Run</span>
            </button>
            <button
              className="secondaryButton jsToolActionButton"
              type="button"
              aria-label="Eval JS tool"
              title="Eval JS tool"
              disabled={props.running || !canUseExportedTool}
              onClick={props.onEval}
            >
              <ShieldCheck size={16} aria-hidden="true" />
              <span>Eval</span>
            </button>
          </div>
        </section>
      </div>

      <div className="jsToolGrid">
        <section className="jsToolPanel">
          <SectionTitle icon={<ListChecks size={17} />} title="Contract" />
          <div className="jsToolFacts">
            <SummaryItem label="Step support" value="deterministic steps" />
            <SummaryItem label="Browser/VLM" value="Python eval-and-evolve" />
            <SummaryItem label="Output keys" value={requiredOutputKeys.length === 0 ? "-" : requiredOutputKeys.join(", ")} />
          </div>
          <div className="scriptCodeGrid compact">
            <div>
              <h4>Input schema</h4>
              <JsonBlock value={selectedVersion?.inputSchema ?? {}} compact />
            </div>
            <div>
              <h4>Output schema</h4>
              <JsonBlock value={selectedVersion?.outputSchema ?? {}} compact />
            </div>
            <div>
              <h4>Latest output</h4>
              <JsonBlock value={props.latestEvent?.output ?? {}} compact />
            </div>
          </div>
        </section>

        <section className="jsToolPanel">
          <SectionTitle icon={<Activity size={17} />} title="Result" />
          {props.latestEvent ? (
            <div className="jsToolResult">
              <div className="resultPanelHeader">
                <div>
                  <h4>{props.latestEvent.type.replaceAll("-", " ")}</h4>
                  <span className="metaRow">
                    <StatusPill status={resultStatus} />
                    <Badge>{duration(props.latestEvent.durationMs ?? null)}</Badge>
                  </span>
                </div>
                <div className="resultActions">
                  {artifactEntries.map(([label, targetPath]) => (
                    <button
                      key={`${label}-${targetPath}`}
                      className="linkButton"
                      type="button"
                      aria-label={`Open ${label}`}
                      title={`Open ${label}`}
                      onClick={() => props.onOpenTarget(targetPath)}
                    >
                      <ExternalLink size={14} aria-hidden="true" />
                    </button>
                  ))}
                </div>
              </div>
              <JsonBlock value={props.latestEvent.output} />
              {props.latestEvent.stderr ? <pre className="stderr">{props.latestEvent.stderr}</pre> : null}
            </div>
          ) : (
            <div className="emptyState">아직 JavaScript tool 작업 결과가 없습니다.</div>
          )}
        </section>
      </div>
    </section>
  );
}

function VersionsView(props: {
  versions: WorkflowVersion[];
  selectedVersion: number | null;
  onSelectVersion: (version: number) => void;
  running: boolean;
  locked: boolean;
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
                disabled={props.locked}
                onClick={() => props.onSelectVersion(version.version)}
              >
                <ChevronRight size={16} />
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
            className="iconButton primary"
            aria-label="Generate update draft"
            title="Generate update draft"
            onClick={props.onGenerate}
            disabled={props.running || props.selectedVersion === null || props.instruction.trim() === ""}
          >
            <Bot size={17} aria-hidden="true" />
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

function EvolutionPanel(props: {
  workflowName: string;
  selectedVersion: number | null;
  maxAttempts: number;
  setMaxAttempts: (value: number) => void;
  latestEvent: RunEvent | null;
  running: boolean;
  onEvolve: () => void;
}): React.ReactElement {
  const summary = props.latestEvent ? summarizeEvolutionOutput(props.latestEvent.output) : null;
  return (
    <div className="evolutionPanel">
      <div className="evolutionHeader">
        <div>
          <SectionTitle icon={<Gauge size={17} />} title="Eval & Evolve" />
        </div>
        <button
          className="iconButton success"
          aria-label="Eval and evolve 실행"
          title="Eval and evolve 실행"
          onClick={props.onEvolve}
          disabled={props.running || props.selectedVersion === null}
        >
          <Route size={17} aria-hidden="true" />
        </button>
      </div>
      <div className="evolutionControlGrid compact">
        <NumberField label="최대 시도" value={props.maxAttempts} onChange={props.setMaxAttempts} />
      </div>
      <div className="evolutionSummaryStrip">
        <SummaryItem label="워크플로우" value={props.workflowName} />
        <SummaryItem label="기준 버전" value={props.selectedVersion === null ? "-" : `v${props.selectedVersion}`} />
        <SummaryItem label="실행 화면" value={browserModeLabel(true)} />
        <SummaryItem label="수정 방식" value="자동 수정안 생성" />
      </div>
      {summary ? (
        <span className="metaRow">
          <StatusPill status={summary.status} label={evolutionStatusLabel(summary.status)} />
          <Badge>{summary.versionLabel}</Badge>
          <Badge>{summary.attemptCount}회 시도</Badge>
        </span>
      ) : (
        <div className="emptyState">아직 실행 결과 없음</div>
      )}
    </div>
  );
}

function EvolutionResultModal(props: {
  open: boolean;
  event: RunEvent | null;
  proposal: WorkflowUpdateProposal | null;
  running: boolean;
  onOpenTarget: (path: string) => void;
  onApprove: () => void;
  onReject: () => void;
}): React.ReactElement | null {
  if (!props.open || !props.event) {
    return null;
  }
  const summary = summarizeEvolutionOutput(props.event.output);
  const canApprove = props.proposal !== null && !props.running;
  return (
    <div className="modalBackdrop" role="presentation">
      <section className="modalPanel" role="dialog" aria-modal="true" aria-labelledby="evolution-result-title">
        <div className="modalHeader">
          <div>
            <p className="eyebrow">Eval & Evolve</p>
            <h2 id="evolution-result-title">검사 결과 승인</h2>
          </div>
          <span className="metaRow">
            <StatusPill status={summary.status} label={evolutionStatusLabel(summary.status)} />
            <Badge>{summary.versionLabel}</Badge>
            <Badge>{summary.attemptCount}회 시도</Badge>
          </span>
        </div>
        <div className="modalBody">
          <div className="resultMetrics">
            <div className="resultMetric">
              <span>최근 시도</span>
              <strong>{summary.latestAttemptStatus}</strong>
            </div>
            <div className="resultMetric">
              <span>실패 step</span>
              <strong>{summary.latestFailedStep}</strong>
            </div>
            <div className="resultMetric">
              <span>소요 시간</span>
              <strong>{summary.latestDuration}</strong>
            </div>
          </div>
          {props.proposal ? (
            <div className="modalNotice">
              <strong>저장 대기 중인 수정안</strong>
              <span>Proposal #{props.proposal.id} · 새 버전 v{props.proposal.proposedVersion}</span>
            </div>
          ) : (
            <div className="modalNotice warning">
              <strong>저장할 draft proposal 없음</strong>
              <span>결과는 확인할 수 있지만 승인 저장은 비활성화됩니다.</span>
            </div>
          )}
          <AttemptStepTimeline attempts={summary.attempts} onOpenTarget={props.onOpenTarget} />
          {summary.artifacts.length > 0 ? (
            <div className="artifactList">
              {summary.artifacts.map((artifact) => (
                <button
                  key={`${artifact.label}-${artifact.path}`}
                  className="artifactButton"
                  type="button"
                  title={`${artifact.label} 열기`}
                  onClick={() => props.onOpenTarget(artifact.path)}
                >
                  <ExternalLink size={14} aria-hidden="true" />
                  <span>{artifact.label}</span>
                </button>
              ))}
            </div>
          ) : null}
          <details className="rawOutput">
            <summary>원본 evolution JSON</summary>
            <pre>{pretty(props.event.output)}</pre>
          </details>
        </div>
        <div className="modalFooter">
          <button className="secondaryButton" type="button" disabled={props.running} onClick={props.onReject}>
            거절
          </button>
          <button className="primaryButton" type="button" disabled={!canApprove} onClick={props.onApprove}>
            승인하고 새 버전 저장
          </button>
        </div>
      </section>
    </div>
  );
}

function AttemptStepTimeline(props: {
  attempts: ReturnType<typeof summarizeEvolutionOutput>["attempts"];
  onOpenTarget: (path: string) => void;
}): React.ReactElement {
  if (props.attempts.length === 0) {
    return <div className="emptyState">step 결과 없음</div>;
  }
  return (
    <div className="attemptTimeline">
      {props.attempts.map((attempt) => (
        <article className="attemptCard" key={attempt.key}>
          <div className="attemptHeader">
            <div>
              <h5>시도 {attempt.attemptIndex}</h5>
              <span className="metaRow">
                <Badge>v{attempt.version}</Badge>
                <StatusPill status={attempt.status} label={evolutionStatusLabel(attempt.status)} />
                <Badge>{attempt.duration}</Badge>
                <Badge>실행 {attempt.runId}</Badge>
              </span>
            </div>
          </div>
          <div className="attemptStepList">
            {attempt.steps.map((step, index) => (
              <article className="attemptStepRow" key={step.key}>
                <span className="stepIndex">{index + 1}</span>
                <div className="attemptStepBody">
                  <div className="attemptStepHeader">
                    <div>
                      <h6>{step.name}</h6>
                      <span className="metaRow">
                        <Badge>{step.type}</Badge>
                        <Badge>{step.duration}</Badge>
                        <Badge>{step.source === "evaluation" ? "Codex VLM 평가" : "실행 기록"}</Badge>
                      </span>
                    </div>
                    <StatusPill status={step.status} label={evolutionStatusLabel(step.status)} />
                  </div>
                  <p>{step.summary}</p>
                  {step.expectedState ? (
                    <div className="stepNote">
                      <strong>기대 상태</strong>
                      <span>{step.expectedState}</span>
                    </div>
                  ) : null}
                  {step.observedState ? (
                    <div className="stepNote">
                      <strong>관찰 결과</strong>
                      <span>{step.observedState}</span>
                    </div>
                  ) : null}
                  {step.problems.length > 0 ? (
                    <div className="stepNote failed">
                      <strong>문제</strong>
                      <span>{step.problems.join(" / ")}</span>
                    </div>
                  ) : null}
                  {step.repairFocus ? (
                    <div className="stepNote">
                      <strong>수정 초점</strong>
                      <span>{step.repairFocus}</span>
                    </div>
                  ) : null}
                  {step.suggestedUpdate ? (
                    <div className="stepNote">
                      <strong>수정 방향</strong>
                      <span>{step.suggestedUpdate}</span>
                    </div>
                  ) : null}
                  {step.evidenceArtifacts.length > 0 ? (
                    <div className="artifactList compact">
                      {step.evidenceArtifacts.map((path) => (
                        <button
                          key={path}
                          className="artifactButton"
                          type="button"
                          title="증거 파일 열기"
                          onClick={() => props.onOpenTarget(path)}
                        >
                          <ExternalLink size={14} aria-hidden="true" />
                          <span>증거</span>
                        </button>
                      ))}
                    </div>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        </article>
      ))}
    </div>
  );
}

function SummaryItem({ label, value }: { label: string; value: string }): React.ReactElement {
  return (
    <div className="summaryItem">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function SegmentedControl(props: {
  label: string;
  value: string;
  options: Array<{ value: string; label: string; title: string }>;
  onChange: (value: string) => void;
}): React.ReactElement {
  return (
    <fieldset className="segmentedField">
      <legend>{props.label}</legend>
      <div className="segmentedControl">
        {props.options.map((option) => (
          <button
            key={option.value}
            className={props.value === option.value ? "segment active" : "segment"}
            type="button"
            title={option.title}
            aria-pressed={props.value === option.value}
            onClick={() => props.onChange(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>
    </fieldset>
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
              <button
                className="iconButton success"
                aria-label={`Apply proposal ${proposal.id}`}
                title={`Apply proposal ${proposal.id}`}
                disabled={running}
                onClick={() => onApply(proposal.id)}
              >
                <ChevronRight size={16} aria-hidden="true" />
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

function CheckboxField(props: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}): React.ReactElement {
  return (
    <label className="checkboxField">
      <input
        type="checkbox"
        checked={props.checked}
        onChange={(event) => props.onChange(event.target.checked)}
      />
      <span>{props.label}</span>
    </label>
  );
}

function defaultJsToolArgumentsJson(detail: WorkflowDetail): string {
  const values: Record<string, unknown> = {};
  for (const argument of [...detail.arguments].sort((left, right) => left.orderIndex - right.orderIndex)) {
    const value = defaultRunValue(argument);
    if (value !== undefined) {
      values[argument.name] = value;
      continue;
    }
    if (argument.required) {
      values[argument.name] = sampleValueForArgument(argument);
    }
  }
  return JSON.stringify(values, null, 2);
}

function defaultRequiredOutputKeys(detail: WorkflowDetail, selectedVersion: number | null): string[] {
  const version = detail.versions.find((candidate) => candidate.version === selectedVersion) ?? detail.versions[0] ?? null;
  return version ? schemaKeys(version.outputSchema) : [];
}

function schemaKeys(schema: unknown): string[] {
  const record = asRecord(schema);
  const properties = asRecord(record.properties);
  const directKeys = Object.keys(record).filter((key) => !["type", "properties", "required"].includes(key));
  return uniqueStrings([
    ...toStringList(record.required),
    ...Object.keys(properties),
    ...directKeys
  ]);
}

function sampleValueForArgument(argument: WorkflowArgument): unknown {
  const valueType = argument.valueType.toLowerCase();
  if (valueType.includes("number") || valueType.includes("integer")) {
    return 0;
  }
  if (valueType.includes("boolean")) {
    return false;
  }
  if (argument.name === "page_text") {
    return "";
  }
  return "";
}

function parseJsonObject(source: string): { ok: true; value: Record<string, unknown> } | { ok: false; error: string } {
  try {
    const parsed = JSON.parse(source);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return { ok: false, error: "Arguments JSON must be an object." };
    }
    return { ok: true, value: parsed as Record<string, unknown> };
  } catch (error: unknown) {
    return { ok: false, error: `Invalid arguments JSON: ${errorMessage(error)}` };
  }
}

function parseRequiredOutputKeys(source: string): string[] {
  return uniqueStrings(
    source
      .split(/[\n,]/)
      .map((item) => item.trim())
      .filter(Boolean)
  );
}

function defaultRunValue(argument: WorkflowArgument): unknown {
  if (argument.defaultValue !== undefined && argument.defaultValue !== null) {
    return argument.defaultValue;
  }
  if (Array.isArray(argument.examples) && argument.examples.length > 0) {
    return argument.examples[0];
  }
  return undefined;
}

function numberFromUnknown(value: unknown, fallback: number): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  }
  return fallback;
}

function stringFromUnknown(value: unknown): string {
  if (value === undefined || value === null) {
    return "";
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

function IconButton(props: {
  label: string;
  title: string;
  disabled?: boolean;
  variant?: "primary" | "success" | "plain";
  onClick: () => void;
  children: React.ReactNode;
}): React.ReactElement {
  return (
    <button
      className={props.variant ? `iconButton ${props.variant}` : "iconButton"}
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
    <button
      className="iconButton"
      aria-label={props.label}
      title={props.title}
      disabled={props.disabled}
      onClick={props.onClick}
    >
      {props.children}
      <span className="srOnly">{props.label}</span>
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

function StatusPill({ status, label = status }: { status: string; label?: string }): React.ReactElement {
  return <span className={`statusPill ${status}`}>{label}</span>;
}

function JsonBlock({ value, compact = false }: { value: unknown; compact?: boolean }): React.ReactElement {
  return <pre className={compact ? "jsonBlock compact" : "jsonBlock"}>{pretty(value)}</pre>;
}

function pageAnalysisFacts(page: PageAnalysisMemory): {
  pageType: string;
  tips: string[];
  waits: string[];
  selectors: string[];
  frames: string[];
  risks: string[];
} {
  const analysis = asRecord(page.analysis);
  const locatorHints = asRecord(page.locatorHints);
  const frameHints = asRecord(page.frameHints);
  const frameworkHints = asRecord(page.frameworkHints);
  const evidence = asRecord(page.evidence);
  const pageType = firstStringFromKeys(analysis, "page_type", "pageType") ?? "page";
  const tips = uniqueStrings([
    ...stringsFromKeys(analysis, "actionable_tips", "recommended_interaction_strategy", "extraction_strategy"),
    ...stringsFromKeys(locatorHints, "preferred_handlers", "preferred_selectors")
  ]).slice(0, 8);
  const waits = uniqueStrings([
    ...stringsFromKeys(analysis, "stable_wait_markers", "stable_markers", "stable_text"),
    ...stringsFromKeys(locatorHints, "stable_text", "wait_markers"),
    ...stringsFromKeys(evidence, "text_markers", "markers")
  ]).slice(0, 8);
  const selectors = uniqueStrings([
    ...stringsFromKeys(analysis, "selector_strategy"),
    ...stringsFromKeys(locatorHints, "selector_strategy", "preferred_handlers", "preferred_selectors")
  ]).slice(0, 8);
  const frames = uniqueStrings([
    ...stringsFromKeys(frameHints, "recommended_frame_strategy", "frame_strategy"),
    ...stringsFromKeys(frameHints, "iframe_urls", "iframe_titles"),
    ...stringsFromKeys(frameworkHints, "frameworks", "signals")
  ]).slice(0, 8);
  const risks = uniqueStrings(stringsFromKeys(analysis, "risk_notes", "risks", "failure_modes")).slice(0, 8);
  return { pageType, tips, waits, selectors, frames, risks };
}

function knowledgeFacts(entry: WorkflowKnowledgeMemory): {
  urlShape: string | null;
  tags: string[];
  tips: string[];
  assertions: string[];
  failures: string[];
  selectors: string[];
  outputs: string[];
} {
  const content = asRecord(entry.content);
  const urlShape = firstStringFromKeys(content, "url_shape", "urlShape", "canonical_url", "target_url");
  const tags = uniqueStrings(toStringList(entry.tags)).slice(0, 8);
  const tips = uniqueStrings([
    ...stringsFromKeys(content, "actionable_tips", "tips", "wait_strategy", "interaction_strategy"),
    ...stringsFromKeys(content, "extraction_tips", "handler_strategy")
  ]).slice(0, 8);
  const assertions = uniqueStrings(stringsFromKeys(content, "output_assertions", "assertion_strategy", "required_output")).slice(0, 8);
  const failures = uniqueStrings(stringsFromKeys(content, "failure_modes", "risk_notes", "risks")).slice(0, 8);
  const selectors = uniqueStrings(stringsFromKeys(content, "selector_strategy", "preferred_selectors", "preferred_handlers")).slice(0, 8);
  const outputs = uniqueStrings(stringsFromKeys(content, "output_keys", "expected_output", "structured_output")).slice(0, 8);
  return { urlShape, tags, tips, assertions, failures, selectors, outputs };
}

function memoryMatches(value: unknown, query: string): boolean {
  if (!query) {
    return true;
  }
  return searchableText(value).includes(query.toLowerCase());
}

function searchableText(value: unknown): string {
  try {
    return JSON.stringify(value).toLowerCase();
  } catch (_error) {
    return String(value).toLowerCase();
  }
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function firstStringFromKeys(source: Record<string, unknown>, ...keys: string[]): string | null {
  for (const key of keys) {
    const first = toStringList(source[key])[0];
    if (first) {
      return first;
    }
  }
  return null;
}

function stringsFromKeys(source: Record<string, unknown>, ...keys: string[]): string[] {
  return keys.flatMap((key) => toStringList(source[key]));
}

function toStringList(value: unknown): string[] {
  if (value === null || value === undefined) {
    return [];
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed ? [trimmed] : [];
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return [String(value)];
  }
  if (Array.isArray(value)) {
    return value.flatMap((item) => toStringList(item));
  }
  if (typeof value === "object") {
    return Object.values(value as Record<string, unknown>).flatMap((item) => toStringList(item));
  }
  return [];
}

function uniqueStrings(values: string[]): string[] {
  const seen = new Set<string>();
  const unique: string[] = [];
  values.forEach((value) => {
    const normalized = value.trim();
    if (!normalized || seen.has(normalized)) {
      return;
    }
    seen.add(normalized);
    unique.push(normalized);
  });
  return unique;
}

function formatConfidence(value: number): string {
  return `${Math.round(value * 100)}%`;
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
  if (event.type.startsWith("evolution")) {
    return `${event.workflowName ?? "workflow"} evolution ${event.type.endsWith("finished") ? "finished" : "started"}`;
  }
  if (event.type.startsWith("creation")) {
    return `workflow creation ${event.type.endsWith("finished") ? "finished" : "started"}`;
  }
  if (event.type.startsWith("js-tool")) {
    return `JavaScript tool ${event.type.endsWith("finished") ? "finished" : "started"}`;
  }
  if (event.type.startsWith("update-apply")) {
    return `proposal #${event.proposalId ?? "-"} apply ${event.type.endsWith("finished") ? "finished" : "started"}`;
  }
  if (event.version) {
    return `${event.workflowName ?? "workflow"} v${event.version} ${event.headed ? "headed" : "headless"}`;
  }
  return event.type.replaceAll("-", " ");
}

function asRunEvent(value: unknown, fallbackType: string): RunEvent {
  if (value && typeof value === "object") {
    const event = value as RunEvent;
    return {
      ...event,
      type: event.type ?? fallbackType
    };
  }
  return {
    type: fallbackType,
    output: value
  };
}

function controlStatus(value: unknown): string {
  if (value && typeof value === "object" && "status" in value) {
    return String((value as { status?: unknown }).status);
  }
  return "finished";
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
  if (message.includes("No handler registered for 'webmcp:create-workflow'")) {
    return "Electron main process is stale. Stop the app and run npm run dev again.";
  }
  if (message.includes("No handler registered for 'webmcp:export-js-tool'")) {
    return "Electron main process is stale. Stop the app and run npm run dev again.";
  }
  if (message.includes("No handler registered for 'webmcp:run-js-tool'")) {
    return "Electron main process is stale. Stop the app and run npm run dev again.";
  }
  if (message.includes("No handler registered for 'webmcp:eval-js-tool'")) {
    return "Electron main process is stale. Stop the app and run npm run dev again.";
  }
  return message;
}

createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
