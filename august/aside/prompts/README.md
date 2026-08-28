# Aside Prompt Archive

Aside 세션 `VqF3D5MdtDRATrHH`를 조사하면서 확인한 실행 프롬프트와 턴별 프롬프트 입력을 보존·정리한 문서 모음이다.

## Source

- Session metadata and prompt: `/Users/mingukjang/.aside/u/0/state.db`
- SQLite table/column: `sessions.system_prompt`
- Session ID: `VqF3D5MdtDRATrHH`
- Transcript and tool-call evidence: `/Users/mingukjang/.aside/u/0/sessions/2026-08-28_VqF3D5MdtDRATrHH/messages.jsonl`
- Prompt snapshot length reported by SQLite: 22,167 characters

## Reading order

1. [`system_prompt.full.md`](system_prompt.full.md): DB에서 추출한 전체 `system_prompt` 스냅샷
2. [`system_prompt/`](system_prompt/): 검토하기 쉽도록 주제별로 나눈 동일 프롬프트 섹션
3. [`pre_user_turn.md`](pre_user_turn.md): 별도 `pre_user_turn` 저장 여부와 관찰된 동적 prelude
4. [`cross-session-verification.md`](cross-session-verification.md): 다른 세션의 검증 호출과 데몬 로그 교차검증
5. [`../aside-prompt-investigation-summary.md`](../aside-prompt-investigation-summary.md): 조사 결과 요약

## Section map

| File | Contents |
|---|---|
| `01_identity-goal.md` | Aside identity and task goal |
| `02_user-communication.md` | Tone, progress updates, and final response behavior |
| `03_artifacts-response.md` | Artifacts, drafts, and citations |
| `04_browser-workflow.md` | Snapshot, action confirmation, navigation, and recovery |
| `05_context-action-policy.md` | Context search and evidence-grounded action policy |
| `06_security-boundaries.md` | Security and instruction-boundary rules |
| `07_completion-verification.md` | Completion gate and postcondition verification |
| `08_workspace-filesystem.md` | Timezone, working directory, and filesystem paths |
| `09_skills.md` | Memory and skill-loading instructions |
| `10_loaded-contexts.md` | AGENTS, SOUL, USER, and MEMORY context payloads |

The section files are documentation copies split by heading. Aside does not appear to store these sections as separate prompt files.

## Scope note

This archive excludes password stores, credentials, tokens, and authentication material. Existing `built_in_skills/` files and unrelated untracked repository files were not changed.
