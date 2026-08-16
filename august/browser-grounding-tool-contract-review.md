# 브라우저 Grounding 및 Tool 실행 계약 재검토 보고서

- 작성일: 2026-08-16
- 저장소: `minguk-jang/spica_at_home`
- 대상 시스템: Chrome Extension 또는 browser daemon client와 backend agent가 결합된 웹 조작 에이전트
- 비교 대상: Aside browser, Browser Use, 현재 Spica browser-agent 방향
- 문서 상태: 재검토 완료, 단계적 구현 권고

## 1. 보고용 결론

현재 단계에서 snapshot 수집 및 직렬화 로직을 전면 개편하기보다는, 기존 snapshot을 유지하면서 **Tool 실행 계약, 사전 검증, 결과 분류, 사후 조건 검증을 먼저 구조화하는 것이 가장 안전하다.**

단, 이를 `snapshot 로직은 문제가 없다` 또는 `앞으로 snapshot을 수정하지 않는다`는 의미로 해석하면 안 된다. 정확한 결정은 다음과 같다.

> 1단계에서는 snapshot acquisition/serialization을 안정화된 입력 계층으로 취급하고 대규모 변경을 보류한다. 대신 실행 계층에 명시적인 precondition, structured result, postcondition 검증을 도입한다. 이후 오류율과 성능 telemetry를 기준으로 snapshot 개선 여부를 결정한다.

이 결정은 다음 문제를 동시에 다룬다.

- snapshot과 실제 DOM의 순서 차이
- 동일한 text를 가진 요소의 오선택
- stale reference 재사용
- click 이벤트는 실행됐지만 목표 상태가 바뀌지 않은 경우
- timeout으로 실행 여부가 불명확한 경우
- 자연어 error를 agent가 잘못 해석하는 문제

## 2. 확정 사실과 추론의 분리

### 2.1 현재 브라우저 도구 계층에서 확인되는 사실

현재 사용하는 browser tool의 외부 계약에서는 다음 동작이 관찰된다.

- `snapshot()`은 페이지를 접근성 중심의 compact tree로 반환한다.
- interactive element에는 virtual ref가 부여된다.
- ref는 실제 DOM attribute나 영구 ordinal index가 아니다.
- 새 snapshot을 생성하면 이전 snapshot의 ref는 폐기된다.
- action은 현재 페이지의 locator 기반으로 실행된다.
- action 이후에는 새 상태를 읽어 다음 판단에 사용한다.

이 사실은 현재 browser tool의 **observable contract**에 대한 설명이다. Aside 제품 내부의 전체 browser daemon, snapshot serializer, candidate ranker 구현을 공개 소스 수준으로 확정하는 근거는 아니다.

### 2.2 Aside 공개 자료에서 확인되는 사실

Aside 공식 문서는 다음 제품 기능을 공개한다.

- 여러 browser action을 포함하는 장시간 task
- active tab을 task context로 첨부
- read-only, guard, full-access 등 permission mode
- model과 speed 선택
- approval, 사용자 입력, notification wait
- Queue와 Steer를 통한 follow-up
- task transcript와 파일 artifact

출처:

- https://docs.aside.com/help/tasks
- https://docs.aside.com/help/side-panel
- https://docs.aside.com/help/troubleshooting

Aside benchmark repository는 Online-Mind2Web, Odysseys, BU Bench V1 결과를 공개한다. 다만 결과에는 model, thinking level, fast mode, timeout, step budget, grader가 함께 포함되므로 성능을 snapshot algorithm 하나의 결과로 귀속할 수 없다.

출처:

- https://github.com/at-inc/aside-benchmarks
- https://aside.com/features/browser-agent

기존 공개 artifact 분석에서 Aside는 `repl`, `openTab`, `snapshot`, `page.locator`, `page.evaluate`, `read_file`, `write_todos` 등을 조합하는 code-as-action 계열로 보인다는 단서가 확인되었다. 이 분석은 내부 구현의 확정 명세가 아니라 공개 trajectory와 runner에서 추정한 구조다.

상세 분석:

- `june/aside-web-agent-comparison-summary.md`
- `june/aside-web-agent-comparison-detailed.md`

### 2.3 아직 공개적으로 확인할 수 없는 사실

다음 사항은 공개 자료만으로 확정하지 않는다.

- Aside가 동일 text 후보를 내부적으로 어떻게 ranking하는가
- snapshot을 어떤 기준으로 pruning 또는 narrowing하는가
- click 전에 role, name, ancestor, visibility를 검증하는가
- postcondition을 Tool 내부에서 자동 판정하는가
- `ambiguous`, `stale_ref`, `no_effect` 같은 내부 enum이 존재하는가
- timeout 이후 action의 side effect 여부를 어떻게 처리하는가

따라서 `Aside가 snapshot을 특별히 잘 골라내기 때문에 성공률이 높다`고 단정해서는 안 된다. 관찰 가능한 snapshot 계약, 실행 가능한 ref, agent loop, 모델 품질, task context, 장시간 재시도, approval 및 memory 계층이 함께 성능에 영향을 준다고 보는 것이 타당하다.

## 3. 핵심 설계 판단

### 3.1 유지할 것

초기 구현에서는 다음 snapshot 계층을 유지한다.

- 현재 DOM/AX snapshot 수집 방식
- interactive element 추출 방식
- 기존 text, role, attribute, ancestor 정보
- 현재 snapshot의 prompt representation
- screenshot 또는 시각 정보 fallback

이는 snapshot을 완벽하다고 가정하는 것이 아니다. 대규모 serializer 개편으로 실행 계약 문제와 관찰 문제를 동시에 바꾸지 않기 위한 단계적 접근이다.

### 3.2 즉시 추가할 것

Tool execution boundary에 다음을 추가한다.

1. snapshot 식별자
2. DOM revision 또는 state revision
3. client-owned opaque element ref
4. 실행 전 expected identity 검증
5. 실행 여부와 목표 달성 여부의 분리
6. postcondition 검증
7. 구조화된 status와 retry policy
8. 실행 결과 telemetry

### 3.3 보류할 것

다음 기능은 1차 계약이 안정화된 뒤 telemetry를 보고 추가한다.

- snapshot serializer 전면 교체
- 모든 중복 후보를 기본 prompt에 노출
- 매 action마다 LLM 후보 ranking
- 복잡한 semantic candidate group을 기본 경로에 삽입
- 불명확한 timeout에 대한 자동 재실행

## 4. Tool 요청 계약

모든 element interaction은 snapshot 범위와 expected identity를 포함해야 한다.

```json
{
  "action": "click",
  "snapshot_id": "s_20260816_000123",
  "dom_revision": 44,
  "ref": "el_91",
  "expected": {
    "role": "button",
    "name": "test",
    "text": "test",
    "scope_ref": "section_test_cases",
    "identity_hash": "sha256:..."
  },
  "postcondition": {
    "type": "one_of",
    "checks": [
      {"type": "url_changed"},
      {"type": "dom_revision_changed"},
      {"type": "element_state_changed", "ref": "el_91"},
      {"type": "modal_opened"}
    ]
  }
}
```

### 4.1 요청 검증 규칙

Tool은 side effect 전에 다음을 검증한다.

- `snapshot_id`가 현재 실행 context와 일치하는가
- `dom_revision`이 허용된 revision인가
- `ref`가 현재 client DOM에 존재하는가
- element가 예상 role/name/text와 일치하는가
- scope 또는 ancestor가 예상 범위와 일치하는가
- visible, enabled, attached 상태인가
- 동일 text 후보가 여러 개일 때 추가 해소 없이 실행해도 되는가

검증에 실패하면 click을 실행하지 않는다.

## 5. Tool 응답 계약

Tool 응답은 자연어 error 하나가 아니라, agent runtime이 먼저 처리할 수 있는 구조화된 envelope여야 한다.

```json
{
  "status": "success",
  "execution": "executed",
  "target": {
    "ref": "el_91",
    "role": "button",
    "name": "test",
    "identity_hash": "sha256:..."
  },
  "observed": {
    "url_before": "https://example.test/cases",
    "url_after": "https://example.test/cases",
    "dom_revision_before": 44,
    "dom_revision_after": 45,
    "visible_change": true
  },
  "postcondition": {
    "status": "verified",
    "matched_check": "dom_revision_changed"
  },
  "retryable": false,
  "next_action": "continue",
  "new_snapshot_id": "s_20260816_000124",
  "message": "Target clicked and expected page-state change verified."
}
```

### 5.1 상태 enum

```text
success
stale_ref
not_found
ambiguous
wrong_target
no_effect
blocked
timeout
indeterminate
internal_error
```

### 5.2 실행 상태와 결과 상태는 분리한다

`clicked: true`만으로는 충분하지 않다. 다음 두 축을 분리한다.

```text
execution:
  not_executed | executed | unknown

postcondition:
  not_checked | verified | not_verified | failed | not_applicable
```

예를 들어 다음은 서로 다른 상황이다.

```text
execution = executed
postcondition = verified
```

실제 click과 목표 상태 변화가 모두 확인된 정상 성공이다.

```text
execution = executed
postcondition = not_verified
```

click 이벤트는 실행되었지만 목표 상태가 확인되지 않았다. 즉시 같은 action을 반복하면 안 된다.

```text
execution = unknown
postcondition = not_checked
```

timeout이나 연결 끊김으로 side effect 여부를 알 수 없다. 자동 재실행하지 말고 먼저 새 상태를 관찰해야 한다.

## 6. Agent 상태 분기 계약

Agent가 Tool 결과를 자연어 해석하기 전에 runtime이 status를 분기한다.

| status | execution | 기본 처리 | 자동 retry |
|---|---|---|---|
| `success` | `executed` | 다음 목표 진행 | 아니오 |
| `stale_ref` | `not_executed` | snapshot 갱신 후 재선택 | 예 |
| `not_found` | `not_executed` | 현재 scope 재검색 | 제한적 |
| `ambiguous` | `not_executed` | 후보 확장 또는 추가 문맥 요청 | click 금지 |
| `wrong_target` | `not_executed` 또는 `executed` | 같은 ref 폐기, 목표 재검토 | 아니오 |
| `no_effect` | `executed` | 새 상태 관찰 후 대체 전략 | 같은 action 금지 |
| `blocked` | `not_executed` | approval, CAPTCHA, 권한, human handoff | 아니오 |
| `timeout` | `unknown` | side effect 관찰 | 관찰 전 금지 |
| `indeterminate` | `unknown` | 새 snapshot과 로그 확인 | 관찰 전 금지 |
| `internal_error` | `unknown` | 시스템 오류 분리 및 안전 정지 | 정책에 따름 |

Agent에게 전달하는 자연어 표현은 구조화된 결과의 축약본이어야 한다.

```text
[Tool result]
status=stale_ref
execution=not_executed
retryable=true
next_action=refresh_snapshot
reason=dom_revision_mismatch
```

자연어 error 문장만 전달하고 모델이 이를 다시 분류하게 하지 않는다.

## 7. 실행 lifecycle

```text
request
  -> preflight identity validation
  -> if invalid: return structured failure, no side effect
  -> execute browser action
  -> collect immediate execution evidence
  -> observe fresh browser state
  -> evaluate postcondition
  -> classify status
  -> return new snapshot or snapshot reference
```

### 7.1 Preflight

Preflight는 deterministic client-side check여야 한다. 정상 경로에서는 LLM을 호출하지 않는다.

### 7.2 Execute

실행 단계는 실제 DOM에서 수행한다. 실행 도중 페이지가 변하면 stale 또는 indeterminate를 보수적으로 분류한다.

### 7.3 Observe

action 후에는 URL, DOM revision, relevant element state, modal/dialog, selected/expanded state, navigation, download 또는 network completion 같은 관찰값을 수집한다.

### 7.4 Postcondition

목표에 맞는 postcondition을 검증한다. 단순히 browser API가 click event를 받았다는 사실을 성공으로 기록하지 않는다.

## 8. 중복 요소 처리

1차 구현에서 모든 중복 후보를 기본 snapshot에 넣지 않는다.

기본 경로:

```text
단일 identity가 충분히 식별됨
  -> preflight
  -> execute

동일 text 또는 의미 요소가 중복됨
  -> ambiguous
  -> local candidate inspection
  -> 필요한 후보만 확장
  -> ref 재선택
  -> preflight
  -> execute
```

후보 확장이 필요해지면 다음 정보 순서로 확장한다.

```text
role/name/text
  -> scope/ancestor/context
  -> href/attributes
  -> sibling/position/geometry
  -> screenshot 또는 작은 resolver model
  -> human handoff
```

후보 배열의 local index는 실행 ref로 사용하지 않는다.

```text
candidate_index != execution_ref
```

## 9. Browser Use와의 비교에서 얻는 교훈

Browser Use의 현재 공개 구조는 DOM snapshot, serializer, selector map, LLM 입력, 단일 index click, error feedback을 중심으로 한다. 동일 text 후보를 위한 명시적인 first-class candidate expansion은 확인되지 않는다.

따라서 Spica가 먼저 가져올 부분은 다음이다.

- DOM hierarchy와 accessibility 정보
- cached selector/ref lookup
- interactive element metadata
- action result가 다음 agent step에 전달되는 구조
- loop detection과 bounded retry

반대로 Spica가 명시적으로 추가해야 하는 부분은 다음이다.

- snapshot-scoped client-owned ref
- expected identity precondition
- `ambiguous`, `wrong_target`, `no_effect`, `indeterminate`
- execution/postcondition 분리
- status 기반 runtime state machine
- postcondition 검증

## 10. 단계별 구현 계획

### Phase 1. 실행 계약 래퍼

- 기존 snapshot 생산 로직 유지
- 기존 click/input/navigation Tool을 공통 envelope로 감싼다
- `snapshot_id`, `dom_revision`, `ref`, expected identity 추가
- preflight 실패 시 side effect 차단
- status와 execution/postcondition 필드 추가

### Phase 2. 검증 및 telemetry

- action 전후 URL과 DOM revision 기록
- relevant element state 변화 기록
- timeout의 `execution=unknown` 처리
- structured result를 agent runtime이 먼저 분기
- 모든 action에 trace id와 retry decision 기록

### Phase 3. postcondition library

공통 postcondition을 typed helper로 제공한다.

```text
url_changed
url_matches
dom_revision_changed
modal_opened
modal_closed
selected_state_changed
expanded_state_changed
download_created
text_appeared
text_disappeared
network_completion_observed
```

### Phase 4. 후보 확장

telemetry에서 `ambiguous`와 `wrong_target`이 충분히 관찰되면 추가한다.

- duplicate group metadata
- scope-aware local search
- compact candidate response
- 후보별 context와 identity hash
- candidate response의 pagination

### Phase 5. snapshot 개선

다음 지표가 기준선보다 높을 때 snapshot serializer를 개선한다.

- preflight mismatch 비율
- `not_found` 비율
- `ambiguous` 비율
- `wrong_target` 비율
- `no_effect` 비율
- postcondition 미검증 비율
- snapshot token/byte 크기
- first Tool call latency

## 11. 수용 기준

수치 목표는 현재 baseline을 먼저 수집한 뒤 확정한다. 다만 다음 invariant는 즉시 production 계약으로 둔다.

1. preflight 실패 후 side effect가 발생하지 않는다.
2. `ambiguous` 상태에서 자동 click하지 않는다.
3. `wrong_target` ref를 같은 snapshot에서 자동 재사용하지 않는다.
4. `execution=unknown` 상태에서 자동 재실행하지 않는다.
5. side-effect action은 postcondition 결과를 남긴다.
6. 모든 retry는 status와 retry policy로 설명 가능하다.
7. agent가 자연어 error를 다시 파싱하지 않고 typed status를 소비한다.
8. snapshot 개선 여부는 telemetry와 benchmark로 결정한다.

권장 측정 항목:

```text
preflight_pass_rate
stale_ref_rate
not_found_rate
ambiguous_rate
wrong_target_rate
no_effect_rate
indeterminate_rate
postcondition_verified_rate
retry_count
same_ref_reuse_count
same_action_repeat_count
time_to_first_tool_call
total_completion_latency
snapshot_bytes
prompt_tokens
```

## 12. 리스크와 대응

### 리스크 1. Tool 결과만 좋아지고 잘못된 click은 계속 발생

대응: 결과 포맷보다 먼저 preflight를 side effect 앞에 강제한다. `wrong_target`과 `ambiguous`를 사후 판정만으로 처리하지 않는다.

### 리스크 2. postcondition을 너무 일반적으로 정의

대응: action별 postcondition helper를 제공하고, 검증 불가능하면 `not_verified` 또는 `indeterminate`로 남긴다.

### 리스크 3. timeout 후 중복 side effect

대응: `execution=unknown`을 별도 상태로 두고, 새 snapshot과 idempotency 또는 server-side operation id 확인 전 재실행하지 않는다.

### 리스크 4. 모든 후보를 prompt에 추가해 비용 증가

대응: 기본 snapshot에는 compact duplicate summary만 두고, 후보 확장은 local search와 pagination으로 제한한다.

### 리스크 5. Aside 성능을 잘못 재현

대응: 공개 benchmark 결과를 snapshot 품질의 직접 증거로 사용하지 않는다. 모델, thinking, fast mode, timeout, task context, follow-up 정책을 분리해 자체 ablation을 수행한다.

## 13. 최종 의사결정 문안

> Spica의 browser grounding 개선은 snapshot serializer 전면 개편보다 실행 계약의 명확화를 우선한다. 기존 snapshot을 유지하면서 snapshot-scoped ref, expected identity precondition, 구조화된 Tool 결과, execution/postcondition 분리, status 기반 retry policy를 도입한다. 이를 통해 stale reference, ambiguous target, wrong target, no effect, unknown side effect를 구분한다. 이후 telemetry와 회귀 benchmark를 사용해 snapshot serializer와 후보 확장 로직의 개선 필요성을 단계적으로 결정한다.

이 문안은 다음 두 가지를 동시에 보장한다.

- 현재 구현의 안정적인 정상 경로를 보존한다.
- snapshot 오류를 영구적으로 방치하지 않고 관측 가능한 개선 backlog로 남긴다.

## 참고 자료

- Aside task 문서: https://docs.aside.com/help/tasks
- Aside side panel 문서: https://docs.aside.com/help/side-panel
- Aside troubleshooting: https://docs.aside.com/help/troubleshooting
- Aside browser agent: https://aside.com/features/browser-agent
- Aside benchmark repository: https://github.com/at-inc/aside-benchmarks
- Browser Use repository: https://github.com/browser-use/browser-use
- 기존 Aside 비교 보고서: `june/aside-web-agent-comparison-detailed.md`
- 기존 Plugin architecture plan: `august/deep-agents-plugin-architecture-plan.md`
