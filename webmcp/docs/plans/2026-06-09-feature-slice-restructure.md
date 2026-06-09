# WebMCP Feature Slice 재구조화 구현 계획

> **Codex용 지시:** 이 계획을 실행할 때는 `superpowers:executing-plans`를
> 사용해 작업 단위별로 검증한다.

**목표:** 기존 core와 Desktop 앱을 `webmcp/` feature slice 안으로 옮겨 코드만
봐도 제품 경계와 실행 경계를 이해할 수 있게 만든다.

**구조:** Python import 이름은 `webworkflows.*`로 유지하고, 프로젝트 위치만
`webmcp/core`로 이동한다. Desktop은 `webmcp/apps/desktop`에서 `../../core`를
기본 core 경로로 계산한다.

## 작업 흐름

```mermaid
flowchart LR
  Test["구조 테스트 추가"]
  Move["git mv로 파일 이동"]
  Paths["Desktop 경로 helper 추가"]
  Docs["문서 재정리"]
  Verify["검증 명령 실행"]

  Test --> Move
  Move --> Paths
  Paths --> Docs
  Docs --> Verify
```

## Task 1: 구조 guard test

생성 파일:

- `webmcp/core/tests/test_repo_structure.py`
- `webmcp/apps/desktop/tests/projectPaths.test.cjs`

테스트는 `webmcp/core`, `webmcp/apps/desktop`, 주요 문서 entry point가 존재하는지
확인한다. Desktop path helper가 `apps/desktop`에서 `../../core`를 계산하는지도
확인한다.

## Task 2: 파일 이동

이전 core project 파일은 `webmcp/core/*`로 옮긴다. 이전 Desktop project 파일은
`webmcp/apps/desktop/*`로 옮긴다. 추적 대상 파일은 `git mv`로 옮겨 history가
이어지게 한다. ignored build output은 Git에 추가하지 않는다.

## Task 3: runtime path 보정

생성 파일:

- `webmcp/apps/desktop/electron/project-paths.cjs`

수정 파일:

- `webmcp/apps/desktop/electron/main.cjs`
- `webmcp/apps/desktop/src/main.tsx`

Electron main은 helper에서 계산한 core root, DB path, output directory, Python
runtime을 사용한다. Renderer fallback도 같은 구조를 가리키게 한다.

## Task 4: 문서 재작성

`webmcp/README.md`를 entry point로 만들고, `webmcp/docs`에 아키텍처/개발/Desktop/
워크플로우 문서를 둔다. 현재 구조를 설명하는 문서는 한글로 작성하고, 필요한
곳에는 Mermaid 다이어그램을 넣는다.

## Task 5: 검증

```bash
cd webmcp/core
python3 -m unittest tests/test_repo_structure.py tests/test_workflow_tools.py tests/test_text_default_vision_fallback.py

cd ../apps/desktop
npm run test:unit
npm run typecheck
npm run build
npm run sidecar:test
npm run sidecar:build
WEBMCP_DEV_SMOKE=1 npm run dev
```
