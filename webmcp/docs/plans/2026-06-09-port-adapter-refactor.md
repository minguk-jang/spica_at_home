# WebMCP Port/Adapter 리팩토링 구현 계획

> **Claude 지시:** 이 계획을 실행할 때는 `superpowers:executing-plans`로 작업을
> 하나씩 검증한다.

**목표:** WebMCP core와 Desktop app을 Claude Code, OpenAI-compatible API, 다른
frontend로 옮기기 쉬운 port/adapter 구조로 정리한다.

**아키텍처:** Python core에는 workflow 실행과 update proposal을 감싸는 service
facade를 추가한다. Electron Desktop은 IPC handler, core client, process runner를
분리해 frontend adapter 역할만 맡게 한다.

**기술 스택:** Python unittest, SQLite, Electron main process CommonJS, Node test
runner, Vite/React, Rust sidecar.

---

### Task 1: Core 실행 service

**파일:**
- 생성: `webmcp/core/webworkflows/services/__init__.py`
- 생성: `webmcp/core/webworkflows/services/workflow_runtime.py`
- 테스트: `webmcp/core/tests/test_workflow_runtime_service.py`
- 수정: `webmcp/core/webworkflows/cli.py`

**Step 1: 실패하는 테스트 작성**

임시 DB를 seed한 뒤 `WorkflowRuntime.run_version()`을 호출하는 테스트를 만든다.
반환 dict가 CLI JSON contract와 같은 공개 key를 갖는지 확인한다:
`workflow`, `workflow_version`, `run_id`, `status`, `llm_used`,
`page_text_evidence`, `output`, `report_path`.

**Step 2: 실패 확인**

```bash
cd webmcp/core
python3 -m unittest tests/test_workflow_runtime_service.py
```

예상 결과: `webworkflows.services.workflow_runtime`가 없어 실패한다.

**Step 3: 최소 구현**

`WorkflowRuntime`에 `run_latest()`와 `run_version()`을 추가한다. 기존
`cli.run()`과 `cli.run_version()`의 orchestration을 이 service로 옮긴다.
`resolve_run_page_text()`는 browser evidence 수집 책임이므로 CLI에 남긴다.

**Step 4: 통과 확인**

```bash
cd webmcp/core
python3 -m unittest tests/test_workflow_runtime_service.py tests/test_workflow_tools.py
```

### Task 2: Synthesis provider port

**파일:**
- 생성: `webmcp/core/webworkflows/providers/__init__.py`
- 생성: `webmcp/core/webworkflows/providers/synthesis_provider.py`
- 테스트: `webmcp/core/tests/test_synthesis_provider_port.py`
- 수정: `webmcp/core/webworkflows/update_proposal.py`

**Step 1: 실패하는 테스트 작성**

`create_synthesis_backend("agent-json", workflow_json_file=...)`,
`create_synthesis_backend("codex", cwd=...)`,
`create_synthesis_backend("fake-copy", base_workflow_json=...)`가 기존 provider 이름을
유지하는 backend를 반환하는지 확인한다.

**Step 2: 실패 확인**

```bash
cd webmcp/core
python3 -m unittest tests/test_synthesis_provider_port.py
```

예상 결과: provider port 모듈이 없어 실패한다.

**Step 3: 최소 구현**

provider 선택 로직을 `create_synthesis_backend()` 뒤로 옮긴다. 기존
`backend_from_name()`은 호환 wrapper로 남겨 CLI 동작을 바꾸지 않는다.

**Step 4: 통과 확인**

```bash
cd webmcp/core
python3 -m unittest tests/test_synthesis_provider_port.py tests/test_workflow_tools.py tests/test_text_default_vision_fallback.py
```

### Task 3: Core update service

**파일:**
- 생성: `webmcp/core/webworkflows/services/update_runtime.py`
- 테스트: `webmcp/core/tests/test_workflow_update_runtime_service.py`
- 수정: `webmcp/core/webworkflows/services/__init__.py`
- 수정: `webmcp/core/webworkflows/cli.py`

**Step 1: 실패하는 테스트 작성**

임시 DB와 `agent-json` workflow JSON 파일을 준비한 뒤
`WorkflowUpdateRuntime.propose_update()`와 `apply_proposal()`을 호출한다. 반환
payload가 CLI와 같은 key를 갖는지 확인한다.

**Step 2: 실패 확인**

```bash
cd webmcp/core
python3 -m unittest tests/test_workflow_update_runtime_service.py
```

예상 결과: `webworkflows.services.update_runtime`가 없어 실패한다.

**Step 3: 최소 구현**

`WorkflowUpdateRuntime`이 base workflow를 로드하고 provider factory를 통해 backend를
선택한 뒤 기존 `WorkflowUpdateProposalService`를 호출하게 한다. CLI는 이 runtime의
payload를 그대로 JSON으로 출력한다.

**Step 4: 통과 확인**

```bash
cd webmcp/core
python3 -m unittest tests/test_workflow_update_runtime_service.py tests/test_workflow_runtime_service.py tests/test_synthesis_provider_port.py tests/test_workflow_tools.py tests/test_text_default_vision_fallback.py
```

### Task 4: Desktop core client

**파일:**
- 생성: `webmcp/apps/desktop/electron/process-runner.cjs`
- 생성: `webmcp/apps/desktop/electron/webmcp-core-client.cjs`
- 테스트: `webmcp/apps/desktop/tests/coreClient.test.cjs`
- 수정: `webmcp/apps/desktop/electron/main.cjs`

**Step 1: 실패하는 테스트 작성**

주입된 `collectProcess`를 사용하는 `createWebmcpCoreClient()` 테스트를 만든다.
`runVersion()`이 `-m webworkflows.cli run-version`을 호출하고, `cwd`를 `repoRoot`로
사용하며, `PYTHONPATH`와 `WEBWRIGHT_HEADLESS`를 headed/headless에 맞게 설정하는지
확인한다.

**Step 2: 실패 확인**

```bash
cd webmcp/apps/desktop
npm run test:unit -- tests/coreClient.test.cjs
```

예상 결과: `webmcp-core-client.cjs`가 없어 실패한다.

**Step 3: 최소 구현**

`collectProcess()`, Python command 선택, run/proposal/apply job normalization,
shell-open callback injection을 `main.cjs` 밖의 모듈로 분리한다. IPC channel 이름은
그대로 유지한다.

**Step 4: 통과 확인**

```bash
cd webmcp/apps/desktop
npm run test:unit
```

### Task 5: IPC handler boundary

**파일:**
- 생성: `webmcp/apps/desktop/electron/ipc-handlers.cjs`
- 테스트: `webmcp/apps/desktop/tests/ipcHandlers.test.cjs`
- 수정: `webmcp/apps/desktop/electron/main.cjs`

**Step 1: 실패하는 테스트 작성**

fake `ipcMain` 객체로 `registerWebmcpIpcHandlers()`가 기존 channel 이름을 등록하는지
확인한다. 대상 channel은 default paths, workflow list/detail, run, update, open-path
계열이다.

**Step 2: 실패 확인**

```bash
cd webmcp/apps/desktop
npm run test:unit -- tests/ipcHandlers.test.cjs
```

예상 결과: `ipc-handlers.cjs`가 없어 실패한다.

**Step 3: 최소 구현**

IPC 등록을 `main.cjs` 밖으로 옮긴다. paths, sidecar runner, core client, shell opener,
event sender를 dependency로 주입한다.

**Step 4: 통과 확인**

```bash
cd webmcp/apps/desktop
npm run test:unit
```

### Task 6: 문서와 전체 검증

**파일:**
- 수정: `webmcp/README.md`
- 수정: `webmcp/docs/ARCHITECTURE.md`
- 수정: `webmcp/docs/DESKTOP_APP.md`
- 수정: `webmcp/docs/DEVELOPMENT.md`
- 수정: `webmcp/core/README.md`
- 수정: `webmcp/apps/desktop/README.md`

**Step 1: 문서 업데이트**

Core use case가 service 뒤에 있고, Desktop이 adapter module을 통해 Core를 호출하며,
모델/provider 변경은 provider port에서 처리한다는 내용을 문서화한다.

**Step 2: 전체 검증**

```bash
cd webmcp/core
python3 -m unittest tests/test_repo_structure.py tests/test_workflow_runtime_service.py tests/test_workflow_update_runtime_service.py tests/test_synthesis_provider_port.py tests/test_workflow_tools.py tests/test_text_default_vision_fallback.py

cd ../apps/desktop
npm run test:unit
npm run typecheck
npm run build
npm run sidecar:test
npm run sidecar:build
WEBMCP_DEV_SMOKE=1 npm run dev
```
