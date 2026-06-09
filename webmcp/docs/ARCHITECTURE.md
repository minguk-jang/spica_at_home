# WebMCP 아키텍처

이 문서는 `webmcp/` feature slice의 책임 경계와 런타임 흐름을 설명합니다.
핵심 원칙은 간단합니다. Core는 워크플로우를 실행하고 저장하며, Desktop은
그 워크플로우를 확인하고 조작하는 앱입니다.

## 책임 경계

```mermaid
flowchart LR
  subgraph Slice["webmcp/"]
    subgraph Core["core/"]
      CLI["webworkflows.cli"]
      Executor["WorkflowExecutor"]
      Storage["WorkflowSkillStore"]
      Handlers["handlers/*.py"]
      Plugin["plugins/webwright-text-vision"]
    end

    subgraph App["apps/desktop/"]
      React["React renderer"]
      IPC["Electron preload/main"]
      Rust["Rust SQLite sidecar"]
    end

    Docs["docs/"]
  end

  React --> IPC
  IPC --> Rust
  IPC --> CLI
  CLI --> Executor
  Executor --> Handlers
  CLI --> Storage
  Rust --> Storage
  Core --> Plugin
```

`apps/desktop`는 `core`에 의존합니다. 반대로 `core`는 Desktop을 몰라야
합니다. 이 방향을 지키면 CLI, Codex 플러그인, Desktop 앱이 같은 workflow
engine을 공유하면서도 서로를 불필요하게 끌어안지 않습니다.

## 런타임 데이터 흐름

```mermaid
sequenceDiagram
  participant UI as React
  participant Main as Electron main
  participant Sidecar as Rust sidecar
  participant CLI as Python CLI
  participant Browser as Playwright/Webwright
  participant DB as SQLite

  UI->>Main: listWorkflows / workflowDetail
  Main->>Sidecar: webmcp-sidecar 명령
  Sidecar->>DB: 읽기 전용 조회
  DB-->>Sidecar: workflow JSON
  Sidecar-->>Main: JSON 응답
  Main-->>UI: 카드/상세 정보

  UI->>Main: runVersion / proposeUpdate
  Main->>CLI: python -m webworkflows.cli ...
  CLI->>Browser: live evidence 수집
  Browser-->>CLI: page text, screenshot, URL
  CLI->>DB: run/update 기록
  CLI-->>Main: stdout JSON
  Main-->>UI: 실행 이벤트
```

## 기본 경로

Desktop의 기본 경로는 `webmcp/apps/desktop` 기준으로 계산합니다. 이 로직은
테스트 가능한 `electron/project-paths.cjs`에 있습니다.

```mermaid
flowchart TB
  AppRoot["webmcp/apps/desktop"]
  CoreRoot["../../core"]
  DB["../../core/outputs/webmcp_plugin_cold_iter_check/workflows.sqlite"]
  Runs["../../core/outputs/desktop_runs"]
  Python["../../core/reference/webwright/.venv/bin/python"]

  AppRoot --> CoreRoot
  AppRoot --> DB
  AppRoot --> Runs
  AppRoot --> Python
```

## Source of Truth

```mermaid
flowchart TD
  DB["SQLite DB<br/>metadata, versions, steps, resources, runs"]
  Code["Python source<br/>webworkflows/*.py"]
  Preview["Desktop script preview<br/>검사용 단일 파일"]

  DB -->|handler id 저장| Code
  Code -->|실제 실행| DB
  DB -->|step/resource 표시| Preview
  Code -->|handler source inline| Preview
```

워크플로우 정의는 DB에 저장되지만, 실행 가능한 Python 함수는 source file에
남습니다. Desktop의 Implementation preview는 감사와 이해를 위한 생성물이며,
실제 실행의 source of truth가 아닙니다.
