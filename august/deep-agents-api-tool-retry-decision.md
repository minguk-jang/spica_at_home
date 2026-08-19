# Deep Agents API Tool 실행 및 Retry 설계 결정

- 작성일: 2026-08-19
- 저장소: `minguk-jang/spica_at_home`
- 대상 시스템: LangChain Deep Agents 0.4.x와 LangGraph 기반 browser-use 계열 에이전트
- 대상 흐름: 페이지 진입 시 API 목록을 주입하고, Agent가 API arguments를 채워 API 실행 Tool을 호출하는 구조
- 문서 상태: 설계 결정

## 1. 결론

API spec은 이미 저장되어 있고 수정할 수 없으므로, spec에 API별 공백 규칙이나 repair 규칙을 추가하지 않는다.

현재 구조의 기본 결정은 다음과 같다.

1. 저장된 API spec은 **read-only source of truth**로 사용한다.
2. 페이지 진입 시 API 목록을 가져오는 Discovery Middleware와 API 실행 경계를 분리한다.
3. API retry의 핵심은 Deep Agents 전용 Middleware가 아니라, API 실행 Tool이 호출하는 공통 `ApiExecutor`에 둔다.
4. 개별 API Tool마다 retry 코드를 복사하지 않는다. 모든 API Tool은 공통 Executor를 호출하는 얇은 진입점으로 유지한다.
5. API의 의미적 arguments 오류는 API를 실제로 호출해 확인하고, `400/422` 오류를 같은 arguments로 반복하지 않는다.
6. 의미적 arguments 오류는 구조화된 ToolMessage로 Agent에 전달하고, Agent의 correction turn은 최대 1회만 허용한다.
7. `429`, `5xx`, connection error, timeout 같은 일시적 오류는 LLM을 다시 호출하지 않고 `ApiExecutor`가 제한된 backoff retry를 수행한다.
8. timeout으로 side effect 여부가 불명확하면 idempotency 또는 상태 조회 없이 재호출하지 않는다.
9. 전체 tool call 수, deadline, telemetry, approval 같은 cross-cutting 정책은 추후 Deep Agents Middleware가 담당할 수 있지만, API별 의미 판단과 API 호출 retry를 Middleware에 중복 구현하지 않는다.

핵심 원칙은 다음과 같다.

> Immutable API spec으로 구조를 검증하고, API 응답으로 의미를 검증한다. API 실행 retry는 공통 `ApiExecutor`가 소유하고, Agent correction은 Deep Agents의 다음 tool turn으로 제한한다.

## 2. 현재 실행 흐름

```text
페이지 진입
  -> Discovery Middleware
  -> 서버 API catalog/spec 조회
  -> Agent context에 read-only API 정보 주입
  -> Agent가 api_id와 arguments 생성
  -> execute_registered_api Tool 호출
  -> 공통 ApiExecutor
  -> 실제 API 호출
  -> 결과 분류
  -> 성공, transport retry, Agent correction, reconcile 또는 중단
```

Discovery Middleware는 API 목록을 발견하고 전달하는 역할만 한다. API 호출 후 retry를 수행하거나 arguments 의미를 해석하지 않는다.

## 3. 권장 컴포넌트 경계

### 3.1 Discovery Middleware

담당 범위:

- 현재 페이지, tenant, 사용자 capability에 맞는 API 목록 조회
- 저장된 API spec을 Agent가 볼 수 있도록 전달
- capability snapshot 또는 spec version 기록

하지 않는 일:

- API 실행
- API 응답 오류 retry
- API별 arguments 보정
- Agent에게 추가 LLM 호출

### 3.2 `execute_registered_api` Tool

API 실행 Tool은 얇은 진입점으로 유지한다.

```python
@tool
def execute_registered_api(api_id: str, args: dict):
    return api_executor.execute(api_id, args)
```

실제 구현에서는 `api_id`와 `args`를 받은 뒤 API client를 직접 호출하지 않고 공통 `ApiExecutor`로 위임한다.

### 3.3 `ApiExecutor`

공통 Executor가 담당한다.

- read-only spec 조회
- spec 기반 구조 검증
- API request 생성
- 실제 API 호출
- HTTP/API 오류 분류
- transport retry와 deadline 관리
- 반복 arguments 감지
- idempotency 또는 상태 조회 경로 선택
- 구조화된 `ToolExecutionResult` 또는 `ToolMessage` 반환
- 실행 telemetry 기록

`ApiExecutor`에는 API별 공백 규칙을 기본으로 저장하지 않는다. spec에 없는 의미를 임의로 추론하지 않고, API 응답을 의미 검증의 기준으로 사용한다.

### 3.4 Deep Agents Middleware

초기 API retry의 주 구현 위치로 사용하지 않는다. 다음과 같은 공통 실행 정책이 필요해질 때 외부 계층으로 추가한다.

- run 전체의 model/tool call limit
- 전체 deadline과 budget ledger
- approval 정책
- tenant 및 capability enforcement
- 모든 Tool에 대한 tracing과 audit
- 동일 tool call loop의 전역 차단
- 예외를 Agent가 볼 수 있는 ToolMessage로 변환

Deep Agents Middleware와 `ApiExecutor` 양쪽에 같은 retry를 넣으면 retry가 중첩된다. 예를 들어 Middleware 3회와 Executor 3회를 동시에 설정하면 하나의 Agent turn이 최대 9번 API를 호출할 수 있으므로, 실패 종류별 retry owner를 하나로 정해야 한다.

## 4. API spec의 사용 방식

API spec은 수정하지 않고 다음 용도로만 사용한다.

```text
- api_id와 endpoint 매칭
- HTTP method와 request 구성
- required field 확인
- JSON 타입 확인
- spec에 이미 존재하는 enum/format/pattern 검증
- response decoding
```

spec에 없는 규칙은 기본적으로 Gateway가 추측하지 않는다.

예를 들어 `to` 필드가 spec에 단순히 `string`으로만 정의되어 있다면, 시스템이 임의로 내부 공백을 제거하거나 문자열을 재작성하지 않는다. API 호출 후 반환된 validation error를 Agent correction 경로로 보낸다.

### 4.1 선택적인 실행 overlay

반복적으로 관찰되는 오류를 최적화할 필요가 생기면, 원본 spec을 수정하지 않고 별도의 versioned execution overlay를 둘 수 있다.

```text
api_id -> execution profile

mail.send:
  side_effect: true
  retry class: side_effecting
  approval: required

search.contacts:
  side_effect: false
  retry class: read_only
```

이 overlay는 spec의 arguments 정의를 덮어쓰지 않는다. retry class, approval, idempotency, timeout 같은 실행 정책만 보완한다. 초기 구현에서는 overlay 없이 보수적인 default를 사용해도 된다.

## 5. 오류 분류와 처리

| 상황 | API 호출 | 담당 | 처리 |
|---|---:|---|---|
| spec 기반 required/type 오류 | 하지 않음 | `ApiExecutor` | 구조화된 invalid arguments 결과를 Agent에 전달 |
| `400/422` invalid arguments | 이미 호출됨 | Agent correction | 같은 arguments로 retry하지 않고 correction 최대 1회 |
| `408/429/5xx` | 호출됨 | `ApiExecutor` | 같은 arguments로 exponential backoff, 최대 2회 |
| connection error | 결과 불명확 | `ApiExecutor` | side effect와 idempotency 정책에 따라 retry 또는 reconcile |
| `401/403` | 호출됨 | Auth/permission layer | 인증 또는 권한 복구 후 중단 |
| `409` | 호출됨 | `ApiExecutor` | conflict 의미 확인, blind retry 금지 |
| timeout 후 결과 불명확 | 호출 여부 불명확 | reconcile layer | idempotency/status 조회, 확인 불가하면 중단 |
| not found/business error | 호출됨 | Agent | retry하지 않고 대체 전략 또는 실패 보고 |
| 동일 arguments와 동일 오류 반복 | 제한 | loop guard | 즉시 중단 |

### 5.1 Retry 기본값

초기 권장값은 다음과 같다.

```text
transport retry: 최대 2회
Agent argument correction: 최대 1회
동일 args + 동일 error 반복: 1회 이후 중단
전체 API execution deadline: RunContext deadline 준수
```

`400/422`를 transport retry 대상으로 넣지 않는다. API가 arguments를 거부한 상태에서 같은 payload를 다시 보내는 것은 비용만 늘리고 성공 확률을 높이지 않는다.

## 6. LLM correction 정책

별도의 error-analysis LLM은 기본으로 추가하지 않는다.

```text
API error
  -> 별도 analyzer LLM
  -> corrected args
  -> API retry
```

이 구조는 latency와 비용이 증가하고, analyzer가 또 다른 잘못된 arguments를 생성할 수 있다.

대신 기존 Agent loop에 구조화된 ToolMessage를 반환한다.

```json
{
  "status": "invalid_arguments",
  "api_id": "mail.send",
  "field": "to",
  "upstream_code": "INVALID_ARGUMENT",
  "upstream_message": "Invalid recipient email address",
  "retryable": true,
  "instruction": "Correct only the 'to' argument. Do not repeat the previous arguments.",
  "attempt": 1,
  "previous_args_hash": "sha256:..."
}
```

Agent가 같은 arguments와 같은 오류를 다시 생성하면 `ApiExecutor` 또는 전역 loop guard가 재호출을 차단한다.

## 7. 메일 보내기 예시

### 7.1 Agent의 첫 호출

저장된 spec을 바탕으로 Agent가 다음을 생성한다고 가정한다.

```json
{
  "api_id": "mail.send",
  "args": {
    "to": "minguk @example.com",
    "subject": "회의 일정",
    "body": "내일 10시에 뵙겠습니다."
  }
}
```

### 7.2 Executor의 사전 검증

`ApiExecutor`는 spec에 있는 required/type/format만 확인한다. spec에 email format이나 pattern이 있으면 그 검증을 적용한다. spec에 해당 규칙이 없으면 임의로 공백을 제거하지 않는다.

### 7.3 API 응답

메일 API가 다음 응답을 반환한다고 가정한다.

```json
{
  "status": 422,
  "code": "INVALID_ARGUMENT",
  "field": "to",
  "message": "Invalid recipient email address"
}
```

`ApiExecutor`는 같은 payload를 다시 보내지 않고 Agent에 `invalid_arguments` ToolMessage를 반환한다.

### 7.4 Agent correction

Agent는 한 번만 수정한다.

```json
{
  "api_id": "mail.send",
  "args": {
    "to": "minguk@example.com",
    "subject": "회의 일정",
    "body": "내일 10시에 뵙겠습니다."
  }
}
```

이때 최종 recipient가 바뀌었으므로 side effect approval이 있다면 승인 대상은 수정된 최종 arguments로 평가한다.

### 7.5 transport 오류

수정된 호출이 `429` 또는 `503`을 받으면 `ApiExecutor`가 LLM을 다시 호출하지 않고 같은 arguments로 backoff retry한다.

### 7.6 timeout

메일 API 호출 후 timeout이 발생하면 메일이 이미 발송되었을 수 있다. idempotency 또는 status query가 없으면 자동으로 다시 보내지 않는다.

## 8. 실행 결과 계약

API Tool은 자연어 error 문자열만 반환하지 않는다.

```json
{
  "status": "invalid_arguments",
  "execution": "executed",
  "postcondition": "not_applicable",
  "retryable": true,
  "retry_owner": "agent_correction",
  "attempt": 1,
  "api_id": "mail.send",
  "upstream": {
    "status_code": 422,
    "code": "INVALID_ARGUMENT",
    "field": "to"
  },
  "next_action": "correct_arguments_once"
}
```

가능한 `retry_owner`는 다음으로 제한한다.

```text
none
api_executor
agent_correction
reconcile
human
```

이 필드는 Middleware와 Executor가 같은 오류를 중복 처리하지 않도록 하는 계약이다.

## 9. 구현 순서

### Phase 1: 공통 실행 경계

- `execute_registered_api`를 공통 `ApiExecutor`에 연결
- 원본 spec을 read-only로 조회
- API client 직접 호출을 Tool별 코드에서 제거
- `ToolExecutionResult`와 typed error envelope 도입

### Phase 2: 오류 분류

- HTTP status와 일반적인 API error body 분류
- `400/422`, `429`, `5xx`, timeout, auth, unknown outcome 분리
- `retry_owner`와 attempt budget 도입
- raw error는 redaction 후 telemetry에 기록

### Phase 3: Agent correction

- invalid arguments를 구조화된 ToolMessage로 반환
- 수정 가능 turn을 1회로 제한
- `api_id + args_hash + error fingerprint` 반복 감지
- 별도 error-analysis LLM은 추가하지 않음

### Phase 4: side effect 보호

- approval을 최종 corrected arguments 기준으로 평가
- idempotency가 있는 API에만 자동 재호출 허용
- timeout 후 status query 또는 reconcile 경로 추가
- 확인 불가능한 side effect는 fail-closed

### Phase 5: telemetry 기반 선택적 최적화

다음 오류 fingerprint를 기록한다.

```text
api_id
spec_version
status_code
upstream_error_code
field
args_hash
attempt
retry_owner
final_status
latency
```

특정 API 오류가 반복되면 그때 별도 execution overlay나 API adapter를 추가한다. 원본 API spec은 계속 수정하지 않는다.

## 10. 테스트와 production gate

필수 테스트:

1. spec required/type 오류가 API 호출 전에 차단되는가
2. API `422`가 같은 arguments로 반복되지 않는가
3. invalid arguments가 Agent correction ToolMessage로 전달되는가
4. Agent correction이 최대 1회인가
5. 동일 args와 동일 오류가 반복되면 중단하는가
6. `429/5xx`는 LLM 없이 backoff retry하는가
7. timeout 후 side effect API가 blind retry되지 않는가
8. idempotency가 있는 API의 재시도가 중복 side effect를 만들지 않는가
9. non-API Tool에 API retry 정책이 적용되지 않는가
10. Discovery Middleware와 API execution retry가 서로 중복 호출하지 않는가
11. approval 이후 arguments가 바뀌면 최종 arguments가 다시 검토되는가
12. raw arguments와 upstream error에서 secret이 telemetry로 노출되지 않는가

초기 production gate:

```text
- 동일 invalid payload의 무한 retry: 0건
- side-effect API의 unknown outcome blind retry: 0건
- approval bypass: 0건
- retry budget 초과: 0건
- API correction 후 duplicate send: 0건
- retry owner가 없는 typed error: 0건
```

## 11. 최종 설계 문장

> 현재 시스템에서는 Discovery Middleware가 read-only API catalog/spec을 Agent에 주입하고, 모든 API 실행 Tool은 공통 `ApiExecutor`를 호출한다. `ApiExecutor`는 immutable spec으로 구조를 검증한 뒤 API를 호출하고, transport 오류만 자체 retry한다. `400/422` arguments 오류는 같은 payload로 재시도하지 않고 구조화된 ToolMessage로 Agent correction을 최대 1회 허용한다. Deep Agents Middleware는 전체 run budget, approval, telemetry, loop guard 같은 cross-cutting 정책을 담당하되 API별 의미 오류와 API 호출 retry를 중복 구현하지 않는다.
