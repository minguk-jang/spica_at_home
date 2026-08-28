# Aside 실행 프롬프트 조사 요약

## 조사 대상

- 세션 ID: `VqF3D5MdtDRATrHH`
- 세션 제목: `Aside 작업 로그의 Todo 완료 검증 로직 확인`
- 조사일: 2026-08-28
- 프롬프트 원본: `/Users/mingukjang/.aside/u/0/state.db`
- 프롬프트 위치: `sessions.system_prompt`
- 실행 로그: `/Users/mingukjang/.aside/u/0/sessions/2026-08-28_VqF3D5MdtDRATrHH/messages.jsonl`

## 핵심 결론

Aside의 완료 검증은 `write_todos` 내부 검증 로직이나 `git push` 전용 hook으로 보이지 않는다. 실행 프롬프트가 작업 완료 전 실제 수행 여부, 근거, 요청 조건, 응답 형식, 필요한 외부 side effect 확인을 요구하고, 모델이 도구 결과를 받은 뒤 작업에 맞는 후속 도구를 선택하는 구조다.

```text
도구 실행
  -> 도구 결과 수신
  -> 모델이 완료 조건과 외부 side effect 확인 필요성 판단
  -> bash/repl/browser 등 후속 도구 호출
  -> 결과 확인
  -> Todo 상태 갱신
  -> 최종 응답
```

## `system_prompt` 구성

전체 프롬프트는 다음 영역으로 구성되어 있다.

1. Aside의 identity와 목표
2. 사용자 커뮤니케이션 및 완료 응답 방식
3. artifact, draft, citation 처리
4. 브라우저 snapshot 중심 실행 규칙
5. context 검색 및 evidence 기반 action policy
6. security와 instruction boundary
7. completion and verification 정책
8. timezone, working directory, filesystem access
9. memory와 skill-loading 지침
10. `AGENTS.md`, `SOUL.md`, `USER.md`, `MEMORY.md`의 로드 컨텍스트

전체 원문은 [`prompts/system_prompt.full.md`](prompts/system_prompt.full.md)에 보존했고, 검토용 분할본은 [`prompts/system_prompt/`](prompts/system_prompt/)에 정리했다.

## 완료 검증 정책

프롬프트의 `Completion and Verification` 영역은 다음을 요구한다.

- 모든 요청 deliverable이 완료되거나 명시적으로 `[blocked]` 처리될 때까지 미완료로 취급
- 이전 snapshot은 재검증하지 않는 한 현재 상태로 제시하지 않음
- 실제 요청을 수행했는지 확인
- 결과가 inspected evidence에 기반하는지 확인
- 개수, 형식, 필터, 출처 경계 등 요청 조건을 충족했는지 확인
- 최종 응답 형식이 요청과 일치하는지 확인
- 필요한 외부 side effect가 확인되었는지 확인

이 정책에는 `git push`, GitHub, reload, 특정 selector 같은 GitHub 전용 절차는 없다.

## `pre_user_turn` 조사 결과

별도의 `pre_user_turn` 컬럼, 파일, literal identifier는 확인되지 않았다. 다만 첫 번째 실행의 `session_runs.user_message`에는 다음 `system-message`가 사용자 메시지 앞에 기록되어 있었다.

```text
Relevant skill docs are available. Read with read_file if needed:
- aside: /Users/mingukjang/.aside/u/0/skills/builtin/aside/SKILL.md
```

이는 관찰된 per-run skill prelude다. Aside 내부에 항상 같은 이름의 `pre_user_turn` 프롬프트가 존재한다는 의미로 확대 해석하지 않는다.

자세한 증거와 해석 경계는 [`prompts/pre_user_turn.md`](prompts/pre_user_turn.md)에 기록했다.

## Git push 이후 확인 흐름

관련 세션 로그에서 관찰된 대표 순서는 다음과 같다.

1. `bash`로 `git push origin main` 실행
2. 모델이 `repl`에서 GitHub 페이지 reload 및 snapshot 실행
3. 페이지의 원격 상태 재확인
4. `git status`, `git rev-parse HEAD`, `git rev-parse origin/main`, `git show --stat` 실행
5. 검증 Todo를 `completed`로 갱신
6. 최종 응답 작성

따라서 페이지 확인은 `write_todos`가 자동 호출한 검증기가 아니라, 프롬프트의 완료 검증 요구와 현재 작업 맥락을 바탕으로 모델이 생성한 일반 도구 호출이다.

## 다른 세션 교차검증

추가로 프롬프트가 저장된 26개 세션과 해당 `messages.jsonl`, 데몬 로그를 비교했다. 20개의 full/root prompt에는 길이와 버전 차이가 있어도 `Completion and Verification`, `write_todos`, 필요한 외부 side effect 확인 항목이 공통으로 들어 있었다. 반면 6개의 약 1,437자 child/audit prompt에는 이 공통 완료 정책이 없었다.

실제 마지막 확인 동작은 일관된 자동 프로세스가 아니었다.

- `2TNOGRTe2OPsUVRP`: push 뒤 GitHub `reload`/`snapshot`과 `git status`/remote SHA 확인을 반복했다.
- `LrIitPpOkUtYKUba`, `uCqtjLeE4uaFhv6o`, `lqqY3NhoZSy3dlI7`: push 뒤 명령줄의 fetch/rev-parse/status/log 결과를 확인했지만, 최종 GitHub 페이지 snapshot은 없었다.
- `Mb8Qb67RAJFlba7y`, `QGNmRbEeQ23IJvrG`, `vsHJllAQiAOh5eAA`: 명시적인 최종 `verify` Todo가 없거나 작업 자체의 재조회로 종료했다.

즉, 검증해야 한다는 기준은 prompt에 있지만, 실제 검증은 모델이 `bash`·`repl` 등 일반 도구를 후속 호출해 수행한다. 동일한 정책이 모든 세션에서 같은 검증을 강제하지는 않는다. `TaskCompletionNotification`은 데몬의 sound/send/read 완료 알림으로 확인됐고, 사용자 요청의 postcondition을 자동 판정하는 `verify` hook은 조사한 로그와 runtime config에서 관찰되지 않았다. 설치 바이너리 문자열 검색에서도 `verify_request`·`pre_user_turn` 같은 전용 식별자는 확인되지 않았지만, 이것만으로 내부 동작의 부재를 증명할 수는 없다.

따라서 결론은 **prompt-only 텍스트는 아니지만, 런타임 강제 verifier도 아니다**이다. 보다 정확히는 “prompt가 유도하는 모델 수준의 검증”이다. 세션별 근거와 해석 경계는 [`prompts/cross-session-verification.md`](prompts/cross-session-verification.md)에 분리했다.

## 확인된 한계

- `write_todos` 상태에는 acceptance criteria, 검증 명령, 증거, 검증 주체가 자동으로 연결되지 않는다.
- 로그에 hook 호출이 없다는 사실은 해당 캡처된 실행에서 hook이 동작하지 않았음을 보여주지만, 모든 Aside 버전과 모든 환경에 hook이 없다는 것을 증명하지는 않는다.
- `system_prompt`는 세션 시점의 스냅샷이다. Aside 업데이트나 세션별 설정에 따라 달라질 수 있다.

## 문서 구조

```text
august/aside/
├── built_in_skills/                 # 기존 자료, 변경하지 않음
├── prompts/
│   ├── README.md
│   ├── system_prompt.full.md
│   ├── system_prompt/
│   │   ├── 01_identity-goal.md
│   │   ├── 02_user-communication.md
│   │   ├── 03_artifacts-response.md
│   │   ├── 04_browser-workflow.md
│   │   ├── 05_context-action-policy.md
│   │   ├── 06_security-boundaries.md
│   │   ├── 07_completion-verification.md
│   │   ├── 08_workspace-filesystem.md
│   │   ├── 09_skills.md
│   │   └── 10_loaded-contexts.md
│   └── pre_user_turn.md
└── aside-prompt-investigation-summary.md
```
