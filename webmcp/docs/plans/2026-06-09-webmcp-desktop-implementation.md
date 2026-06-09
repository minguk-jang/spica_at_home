# WebMCP Desktop 구현 계획

> **Codex용 지시:** 이 계획을 실행할 때는 `superpowers:executing-plans`를
> 사용해 task 단위로 구현하고 검증한다.

**목표:** Electron + React Desktop 앱과 Rust SQLite sidecar를 구현해 WebMCP
workflow를 조회하고 실행할 수 있게 한다.

## 구현 순서

```mermaid
flowchart LR
  Scaffold["Desktop scaffold"]
  Sidecar["Rust sidecar"]
  IPC["Electron IPC"]
  UI["React UI"]
  Run["Run selected version"]
  Verify["검증"]

  Scaffold --> Sidecar
  Sidecar --> IPC
  IPC --> UI
  UI --> Run
  Run --> Verify
```

## Task 1: Desktop scaffold

생성 파일:

- `webmcp/apps/desktop/package.json`
- `webmcp/apps/desktop/tsconfig.json`
- `webmcp/apps/desktop/vite.config.ts`
- `webmcp/apps/desktop/index.html`
- `webmcp/apps/desktop/src/main.tsx`
- `webmcp/apps/desktop/src/styles.css`
- `webmcp/apps/desktop/electron/main.cjs`
- `webmcp/apps/desktop/electron/preload.cjs`

기본 목적은 `npm run dev`로 Vite와 Electron이 함께 뜨는 개발 루프를 만드는
것입니다.

## Task 2: Rust sidecar

생성 파일:

- `webmcp/apps/desktop/rust/webmcp-sidecar/Cargo.toml`
- `webmcp/apps/desktop/rust/webmcp-sidecar/src/lib.rs`
- `webmcp/apps/desktop/rust/webmcp-sidecar/src/main.rs`

Sidecar는 workflow card와 workflow detail을 SQLite에서 읽어 JSON으로 반환합니다.
쓰기 작업은 sidecar가 아니라 Python CLI가 담당합니다.

## Task 3: IPC와 UI 연결

Electron preload는 `window.webmcp` bridge를 노출합니다. Renderer는 이 bridge로
workflow 목록, detail, run event, proposal action을 호출합니다. IPC handler는
실패 시 stderr와 exit code를 UI가 볼 수 있게 전달해야 합니다.

## Task 4: 검증

```bash
npm --prefix webmcp/apps/desktop install
npm --prefix webmcp/apps/desktop run test:unit
npm --prefix webmcp/apps/desktop run typecheck
npm --prefix webmcp/apps/desktop run build
cargo test --manifest-path webmcp/apps/desktop/rust/webmcp-sidecar/Cargo.toml
```
