# Deep-first 실행 프로파일 및 단계별 구현 계획

- 작성일: 2026-08-16
- 저장소: `minguk-jang/spica_at_home`
- 대상 시스템: LangChain Deep Agents 0.4.x와 LangGraph 기반 browser-use 계열 에이전트
- 현재 상태: quick 수준의 실행만 안정적으로 사용 중
- 문서 상태: 기존 Plugin 설계를 보완하는 실행 깊이 milestone

## 1. 결정 요약

현재 quick 기능을 기준으로 deep을 덧붙이는 대신, **deep 수준의 기준 실행을 먼저 확립한 다음 같은 실행 코어에서 quick을 제한된 프로파일로 도출한다.**

이 순서를 택하는 이유는 deep을 나중에 추가할 때 다음 문제가 생길 수 있기 때문이다.

- quick 전용 가정이 graph, state, tool contract 곳곳에 흩어짐
- planning, context compaction, retry, subagent, verification을 뒤늦게 추가하면서 상태와 checkpoint가 바뀜
- quick에서만 통하는 prompt와 tool surface가 deep 작업을 제한함
- deep을 별도 graph로 만들면서 공통 로직이 복제됨
- browser action과 research evidence가 나중에 붙으면서 실행 계약이 뒤집힘

### 핵심 원칙

1. **하나의 공통 Agent assembly source와 안정적인 Base Graph를 기본으로 유지한다.**
2. `deep_reference`를 capability와 예산의 상한선으로 정의한다.
3. `quick`은 원칙적으로 deep graph의 복사본이 아니라 제한된 `RunProfile`이다.
4. profile은 thread 또는 run 시작 시점에 고정하고 실행 중에는 변경하지 않는다.
5. safety, approval, tenant 권한은 effort와 분리한다.
6. deep 기능은 한 번에 모두 넣지 않고 planning, budget, browser, research 순서로 확장한다.
7. v0.4 기본 middleware 때문에 quick의 overhead를 제거할 수 없거나 state schema가 호환되지 않을 때만, 같은 assembly와 contract에서 profile별 compiled bundle을 만든다. 수동으로 유지하는 별도 root graph는 만들지 않는다.

## 2. 실행 모델

```text
요청
  -> tenant/auth/capability 확인
  -> immutable RunProfile 선택
  -> AgentBundle 선택 및 실행
       ├── 공통 Base Graph 또는 측정된 profile bundle
       ├── planning
       ├── tool dispatch
       ├── browser/research capability
       ├── budget and retry guard
       └── verification/finalization
  -> checkpoint와 telemetry
```

### 2.1 Profile은 graph가 아니라 정책이다

```python
class RunProfile:
    name: str
    allowed_capabilities: frozenset[str]
    planning: str
    allow_subagents: bool
    allow_interactive_browser: bool
    max_model_calls: int
    max_tool_calls: int
    max_parallel_tasks: int
    max_active_time_seconds: int
    verification: str
```

처음부터 `quick`과 `deep`의 수치를 추측하지 않는다. 먼저 `deep_reference`를 측정하고, 그 결과에서 quick의 제한을 정한다.

```text
deep_reference
  ├── deep_research
  └── deep_browser
        ↓ 제한과 capability를 줄여 도출
      quick
```

### 2.2 선행 Agent 구조

Deep milestone을 시작하기 전에 다음 경계를 코드에 존재시킨다. 실제 클래스명과 디렉터리명은 저장소에 맞게 정하되, 책임은 분리되어야 한다.

```text
API / CLI / Worker entrypoint
  -> RunCoordinator
      -> Auth / Tenant / Capability / RunProfile
      -> AgentFactory
          -> immutable AgentBundle
              -> AgentRunner
                  -> common middleware
                  -> ToolGateway
                  -> ChildWorkerGateway
  -> Checkpoint / Audit / Result
```

필수 구성:

- `RunCoordinator` 또는 동등한 단일 실행 조정자: API, queue worker, resume 경로가 직접 Agent를 생성하거나 호출하지 않게 한다.
- `AgentFactory`와 immutable `AgentBundle`: graph 생성, middleware 조합, Tool surface 선택, profile metadata를 한 곳에서 관리한다.
- `AgentRunner`: invoke, stream, resume의 공통 계약을 제공한다.
- `RunContext`: `run_id`, `thread_id`, tenant, profile, capability snapshot, deadline, policy version을 보관하는 immutable context다.
- `AgentState`: messages, todo, plan, evidence, tool result, budget ledger처럼 checkpoint 가능한 상태만 보관한다.
- `RuntimeHandles`: browser page, connection, client, mutable session처럼 checkpoint와 graph cache에 넣으면 안 되는 일시 객체다.
- `EffortPolicy`와 `SafetyPolicy`: planning, budget, subagent와 권한, approval, allowed domain을 서로 다른 정책으로 관리한다.
- `ToolGateway`: precondition, auth, budget, approval, execute, observe, postcondition, audit를 공통 경계에서 처리한다.
- `ChildWorkerGateway`: child profile, capability allowlist, deadline, budget slice, output schema를 전달한다.

`AgentBundle`은 다음처럼 profile별 compiled bundle을 수용할 수 있어야 한다.

```python
@dataclass(frozen=True)
class AgentBundle:
    runner: Runnable
    profile_id: str
    policy_version: str
    tool_surface_hash: str
    graph_schema_version: str
```

기본 구현은 하나의 Base Graph와 runtime policy를 사용한다. 다만 Deep Agents 0.4.x의 기본 planning/subagent middleware를 실제로 제거할 수 없는 경우, Factory가 같은 state schema, Tool contract, middleware source에서 quick/deep bundle을 만들 수 있어야 한다. 이 fallback은 D-1에서 준비만 하고, 선택 여부는 D5 benchmark 이후 결정한다.

### 2.3 실행 중 profile 변경 금지

기존 Plugin 설계의 immutable capability snapshot 원칙을 그대로 적용한다.

- profile은 thread/run 시작 시 선택한다.
- checkpoint에 `profile_id`, `policy_version`, `capability_snapshot_id`를 기록한다.
- 실행 중 quick에서 deep으로 바꾸지 않는다.
- 사용자가 더 깊은 실행을 요청하면 새 run 또는 명시적인 child run으로 handoff한다.
- 같은 graph를 사용하더라도 현재 run의 tool surface와 policy는 고정한다.

## 3. 기존 문서와의 충돌 검토

### 3.1 `deep-agents-plugin-architecture-plan.md`

대부분 충돌하지 않는다.

| 기존 내용 | 판정 | 이번 문서의 정리 |
|---|---|---|
| 고정 Base Graph | 방향 일치 | 공통 assembly source와 하나의 Base Graph를 기본으로 하되, v0.4 overhead가 측정되면 같은 assembly에서 profile bundle을 만든다. |
| runtime context와 immutable snapshot | 일치 | RunProfile도 snapshot 경계에서 고정한다. |
| 실행 중 Tool schema mutation 금지 | 일치 | profile 변경은 새 run에서만 수행한다. |
| HTTP Plugin을 MVP로 사용 | 일치 | deep milestone 초반에는 Plugin DB를 기다리지 않고 static fixture로 검증한다. |
| Plugin-specific subgraph는 복잡한 workflow에만 사용 | 일치 | deep baseline에서는 별도 supervisor graph를 만들지 않는다. |
| 0.4.x 유지 후 0.7 upgrade 평가 | 일치 | D7에서 별도 branch로 평가한다. 단, D-1의 구조적 seam을 먼저 확보한다. |
| Core-only fast path | 순서 변경 | 먼저 deep 기준을 만들고, 그 후 quick 제한을 fast path로 검증한다. |
| Phase 3에서 첫 Plugin 구현 | 순서 변경 | agent execution contract가 안정된 뒤 실제 Plugin runtime을 연결한다. |
| Agent Profile Cache | 보완 | immutable AgentBundle definition과 runtime context, mutable connection을 분리하고 Factory에서 build spec별로 cache한다. |

기존 문서의 Plugin Registry, PostgreSQL, capability snapshot, transport 선택 milestone은 유지한다. 이번 문서는 그 위에 올라가는 **agent execution depth의 순서**만 정의한다.

### 3.2 `browser-grounding-tool-contract-review.md`

충돌하지 않는다. 오히려 deep-first 순서에서 먼저 참조해야 한다.

- precondition과 postcondition은 deep browser를 추가하기 전에 적용한다.
- `stale_ref`, `ambiguous`, `wrong_target`, `no_effect`, `indeterminate` 상태는 모든 profile에서 공통으로 유지한다.
- quick이든 deep이든 side-effect Tool의 승인과 실행 불확실성 정책은 완화하지 않는다.
- snapshot serializer 전면 개편은 여전히 telemetry 이후로 미룬다.

### 3.3 의도적으로 바꾸는 내용

기존 Plugin 문서의 전체 migration 순서를 폐기하지 않는다. 다만 현재 quick-only 상태에서 곧바로 Plugin, MCP, long-tail discovery까지 진행하면 deep 실행 문제와 Plugin runtime 문제가 동시에 발생한다.

따라서 실행 순서는 다음처럼 분리한다.

```text
D-1 agent 구조와 리팩토링 경계
  -> D0 현재 quick baseline과 실행 계약
  -> deep browser/research capability
  -> quick profile 도출
  -> Plugin runtime 연결
  -> MCP와 long-tail discovery
  -> 0.7 upgrade 평가
```

## 4. 외부 구현에서 확인한 방향

### 4.1 Browser Use

Browser Use는 quick/deep용 root graph를 별도로 유지하지 않고 하나의 `Agent`에 실행 설정을 주입한다.

주요 설정은 다음과 같다.

- `max_steps`
- `max_actions_per_step`
- `max_failures`
- `step_timeout`
- `llm_timeout`
- `enable_planning`
- `flash_mode`
- loop detection
- message compaction
- fallback model

참고:

- [Browser Use Agent parameters](https://docs.browser-use.com/open-source/customize/agent/all-parameters)
- [Browser Use Agent quickstart](https://docs.browser-use.com/open-source/customize/agent)
- [Browser Use production architecture](https://browser-use.com/posts/production-architecture-browser-use)

Browser Use의 production architecture도 Agent를 worker에서 실행하고, worker 시간 제한에 도달하면 상태를 저장한 뒤 continuation을 재큐잉하는 방식을 사용한다. 실행 깊이를 graph 복제로 해결하지 않고 settings, worker, checkpoint, continuation으로 해결한다.

### 4.2 Browserbase

Browserbase의 Deep Agents 통합은 effort라는 이름보다 비용과 위험도에 따른 escalation을 사용한다.

```text
search
  -> static fetch
  -> rendered extraction
  -> interactive browser task
```

- 저렴한 search/fetch는 main planner에 둔다.
- JS가 필요한 읽기 작업은 rendered extraction으로 올린다.
- click, login, form submission은 browser-specialist에 위임한다.
- interactive task는 `interrupt_on` 승인 뒤 실행한다.

참고:

- [Browserbase Deep Agents integration](https://docs.browserbase.com/integrations/langchain/deepagents)
- [Browserbase Agents](https://www.browserbase.com/blog/introducing-browserbase-agents)

이 패턴은 `deep_browser`를 별도 root graph로 만드는 대신 capability와 비용 escalation으로 구현하는 근거로 사용한다.

### 4.3 Deep Agents

Deep Agents 공식 Deep Research 예제도 처음부터 Open Deep Research 전체 graph를 복제하지 않는다.

- 하나의 Deep Agent
- 하나의 researcher subagent
- 검색 도구
- todo/planning
- 연구용 prompt
- delegation limit

참고:

- [Deep Agents Deep Research guide](https://docs.langchain.com/oss/python/deepagents/deep-research)
- [Deep Agents README](https://github.com/langchain-ai/deepagents)
- [Deep Agents v0.7 release note](https://github.com/langchain-ai/deepagents/issues/5071)

## 5. Profile 정책

수치는 기준선 측정 후 확정한다. 아래는 capability 차이를 정의하는 초기 구조다.

| capability | `deep_reference` | `deep_research` | `deep_browser` | `quick` |
|---|---:|---:|---:|---:|
| planning | 허용 | 허용 | 허용 | 최소화 또는 제한 |
| context compaction | 허용 | 허용 | 허용 | 필요 시만 |
| researcher subagent | 선택 | 허용 | 금지 또는 선택 | 금지 |
| browser render | 선택 | 선택 | 허용 | 금지 |
| interactive browser | 승인 후 | 승인 후 | 승인 후 | 금지 |
| evidence collection | 기본 | 필수 | 선택 | 최소 citation |
| independent verification | 기준선 측정 | 허용 | postcondition 필수 | deterministic check |
| max failure/retry | 기준선 | 기준선 이상 | browser별 제한 | 작게 |
| active time/tool budget | 상한 | 상한 내 분배 | browser cost 포함 | 작게 |

`deep_reference`는 모든 기능을 무조건 켠다는 뜻이 아니다. 나중에 quick을 만들 때 무엇을 줄여도 되는지 판단할 수 있는 기준 실행이다.

## 6. 단계별 Milestone

### D-1. Agent 구조 및 리팩토링 준비

목표: 저장소별 구현을 추측하지 않고, D0 이후의 deep/quick 변경이 들어갈 수 있는 안전한 구조적 seam을 먼저 만든다.

D-1은 대규모 재작성 단계가 아니다. 현재 quick 동작을 pass-through로 보존하면서 Agent 생성, 실행, Tool, state, checkpoint의 책임을 분리하는 단계다.

작업:

1. **Read-only 구조 조사**
   - Agent 생성 함수와 모든 호출자
   - graph 생성 및 compile 위치
   - middleware 등록 순서와 Deep Agents 기본 middleware
   - Tool registry, Tool factory, retry/timeout 위치
   - subagent 생성과 child state 전달 위치
   - browser session/page 생성, 해제, 재사용 위치
   - streaming, interrupt, checkpoint, resume 경로
   - 테스트와 실제 실행/배포 진입점
2. **구조 산출물 작성**
   - `agent-architecture-inventory.md`
   - `agent-entrypoint-callgraph.md`
   - `agent-state-and-checkpoint-contract.md`
   - `agent-refactor-risk-register.md`
   - 각 산출물에는 실제 파일 경로, symbol, 호출 흐름, 확인되지 않은 가정을 기록한다.
3. **Pass-through seam 추가**
   - `RunCoordinator` 또는 동등한 실행 조정자
   - `RunContext`, `AgentState`, `RuntimeHandles` 분리
   - `AgentFactory`와 immutable `AgentBundle`
   - `AgentRunner`의 invoke/stream/resume 계약
   - 모든 Tool이 통과하는 `ToolGateway`
   - child worker에 profile과 budget을 전달하는 경계
4. **계약 테스트 추가**
   - 기존 quick golden task 결과와 Tool sequence 보존
   - checkpoint/resume와 HITL 동작 보존
   - concurrent run 간 profile, tenant, browser session leakage 차단
   - secret이 state, trace, checkpoint에 기록되지 않음
   - 기존 API response와 streaming contract 보존
   - AgentFactory가 실행 중 graph나 profile을 mutation하지 않음

하지 않는 것:

- deep 기능 활성화
- Plugin Registry, MCP, researcher, browser-specialist 추가
- snapshot serializer 전면 개편
- quick/deep graph를 수동으로 복사
- prompt만으로 budget, retry, permission을 강제

완료 조건:

- Agent를 직접 호출하는 진입점이 Coordinator/Runner 뒤로 모인다.
- Agent 생성과 compile이 Factory 뒤로 숨겨진다.
- Context, checkpoint state, ephemeral runtime handle이 구분된다.
- EffortPolicy와 SafetyPolicy가 구분된다.
- 모든 side-effect 가능 Tool에 공통 precondition/approval/postcondition 경계가 있다.
- 기존 quick이 pass-through profile로 같은 결과를 낸다.
- 하나의 Base Graph와 profile별 compiled bundle 중 어느 방식을 선택할지 benchmark로 결정할 수 있다.
- D-1 변경 자체의 latency와 regression이 기록된다.

### D0. 현재 quick baseline 고정

목표: 현재 quick의 동작을 control group으로 보존한다.

작업:

- 정확한 `deepagents`, LangChain, LangGraph patch version 기록
- 현재 quick golden task 작성
- tool call 수, model call 수, latency, cost, timeout, 실패 상태 측정
- browser action의 기존 성공률과 오류 유형 측정
- checkpoint/resume와 HITL smoke test 작성
- 기존 결과와 API contract snapshot 보관

하지 않는 것:

- deep 기능 추가
- Tool schema 재구성
- snapshot serializer 전면 변경
- Plugin Registry migration

완료 조건:

- 같은 입력을 반복해 baseline 결과를 재현한다.
- 기존 quick 경로를 flag off로 즉시 복구할 수 있다.

### D1. Deep reference skeleton

목표: 현재 graph를 복제하지 않고 deep 실행을 위한 capability envelope를 만든다.

작업:

- D-1에서 만든 공통 assembly source와 현재 Base Graph를 기준으로 고정
- `deep_reference` RunProfile을 추가
- planning, context management, retry, finalization을 deep 기준으로 활성화
- 현재 browser/tool contract를 common layer로 이동
- profile과 policy를 runtime context에 전달
- 모든 execution trace에 profile과 policy version을 기록

초기에는 새 Plugin이나 MCP를 추가하지 않는다. 현재 core/browser tools만 사용해 multi-step 작업을 실행한다.

완료 조건:

- deep_reference가 기존 quick보다 긴 multi-step task를 완주한다.
- 기존 quick golden task는 동일하게 통과한다.
- deep_reference와 quick이 수동으로 유지하는 별도 root graph fork를 사용하지 않는다.
- 기본은 하나의 Base Graph이며, v0.4 기본 middleware 때문에 profile bundle이 필요하면 동일한 Factory와 state/tool contract에서 생성된다.

### D2. Deep control plane

목표: deep을 오래 실행할 수 있게 하되 무한 loop를 허용하지 않는다.

작업:

- active time budget
- model/tool call budget
- retry/failure budget
- per-tool timeout
- bounded parallelism
- budget warning과 graceful wind-down
- budget 초과 시 final answer 또는 partial result
- parent-child budget propagation을 위한 runtime context
- checkpoint에 profile, budget ledger, snapshot id 저장

Tool과 middleware는 prompt가 아니라 실행 경계에서 budget을 검사한다.

완료 조건:

- deep_reference가 설정된 budget을 넘지 않는다.
- budget 초과 시 side effect Tool을 새로 시작하지 않는다.
- timeout으로 실행 여부가 불명확한 action은 자동 재실행하지 않는다.
- quick과 deep 모두 같은 budget middleware를 사용한다.

### D3. Deep browser capability

목표: Browserbase식 escalation과 Browser Use식 bounded action loop를 추가한다.

순서:

```text
search
  -> static fetch
  -> rendered extraction
  -> browser-specialist
  -> interactive task + approval
```

작업:

- search/fetch와 rendered browser를 분리
- browser-specialist를 하나의 worker capability로 등록
- `max_actions_per_step`, `max_steps`, `max_failures`에 해당하는 정책 추가
- browser session과 page lifecycle을 thread context에 둔다.
- `snapshot_id`, `dom_revision`, expected identity, postcondition을 모든 action에 적용
- `stale_ref`, `ambiguous`, `wrong_target`, `no_effect`, `indeterminate` 처리
- interactive action에 approval과 allowed-domain 정책 적용

완료 조건:

- read-only static 작업이 browser session 없이 완료된다.
- JS 페이지에서만 rendered browser로 escalation된다.
- interactive action은 approval 없이 실행되지 않는다.
- wrong target과 unknown side effect가 자동 재실행되지 않는다.

### D4. Deep research capability

목표: deep_reference 위에 research 품질을 단계적으로 추가한다.

작업:

1. researcher subagent 하나
2. 검색 횟수와 delegation round 제한
3. URL/title/excerpt/retrieved_at evidence packet
4. citation coverage 검사
5. 필요할 때만 독립 verifier
6. 그 이후에만 병렬 researcher와 compression 검토

초기에는 Open Deep Research의 전체 supervisor graph를 복사하지 않는다. 공식 Deep Agents research 패턴으로 먼저 benchmark를 만들고, prompt-only 제어로 부족한 부분만 middleware 또는 workflow capability로 승격한다.

완료 조건:

- researcher 결과가 URL과 evidence를 포함한다.
- unsupported claim과 citation 누락을 측정할 수 있다.
- deep research가 budget 안에서 종료된다.
- researcher subagent 장애가 parent 전체 장애로 전파되지 않는다.

### D5. Deep에서 Quick 도출

목표: deep_reference에서 실제 측정값을 기반으로 quick을 만든다.

줄이는 순서:

1. independent verifier 비활성화
2. researcher subagent 비활성화
3. rendered/interactive browser 비활성화
4. planning을 최소화
5. context와 retry 범위 축소
6. model/tool/time budget 축소
7. quick allowlist 적용

각 단계마다 latency, cost, success rate, failure mode를 비교한다. 한 번에 모든 기능을 끄지 않는다.

완료 조건:

- quick은 deep_reference와 같은 state/schema/verification contract를 사용한다.
- quick의 latency와 비용이 목표에 맞는다.
- quick에서 subagent와 interactive browser가 실행되지 않는다.
- deep 기능을 다시 켤 때 graph source를 복제하지 않는다.

만약 v0.4에서 model-facing tool filtering이 불안정하면 우선 stable dispatch surface와 execution guard를 사용한다. quick의 tool schema와 기본 middleware 비용이 실제 SLO를 넘을 때만 D-1 Factory가 profile bundle을 생성하도록 한다. 이 경우에도 state, Tool contract, middleware source는 공유하고 수동 graph fork는 만들지 않는다.

### D6. Plugin capability snapshot 연결

목표: deep 실행이 안정된 뒤 사용자별 Plugin과 연결한다.

작업:

- D1-D5에서는 deterministic static capability fixture를 사용한다.
- 이후 canonical Capability Resolver의 immutable snapshot을 RunProfile과 결합한다.
- Plugin tool surface는 thread/profile 경계에서만 선택한다.
- 실행 중 registry를 다시 조회하지 않는다.
- Plugin runtime과 browser session state를 graph definition cache에서 분리한다.
- HTTP Plugin을 먼저 연결하고 MCP는 별도 milestone로 둔다.

완료 조건:

- deep/quick profile과 Plugin snapshot이 checkpoint에 기록된다.
- 같은 thread resume에서 capability가 바뀌지 않는다.
- Plugin runtime 장애가 core deep agent에 전파되지 않는다.
- 기존 Skill-only 경로로 rollback할 수 있다.

### D7. v0.4와 최신 버전 비교

목표: deep 구현이 안정된 뒤에만 upgrade 가치를 측정한다.

비교 branch:

```text
branch A: 현재 v0.4.x + RunProfile middleware
branch B: deepagents 0.7.6 + HarnessProfile/opt-in middleware
```

측정 항목:

- quick tool surface 구성 비용
- deep planning/subagent 동작
- checkpoint/resume
- browser session isolation
- middleware ordering
- prompt/tool schema token
- first token과 total latency
- dependency와 기존 Skill regression

0.7.6의 HarnessProfile은 static model/provider 설정에 활용하고, per-run effort는 계속 application-level RunProfile로 유지한다. HarnessProfile만으로 orchestration effort를 해결한다고 가정하지 않는다.

완료 조건:

- v0.4 branch의 baseline과 D1-D6 regression이 통과한다.
- 0.7.6 upgrade branch가 dependency와 state migration을 통과한다.
- upgrade가 줄이는 custom code와 증가시키는 migration risk를 비교할 수 있다.

### D8. 필요할 때만 명시적 workflow로 승격

다음 조건 중 하나가 발생할 때만 별도 coordinator/subgraph/workflow capability를 추가한다.

- prompt 기반 delegation이 반복적으로 budget을 초과함
- fan-out/fan-in 결과가 parent context를 과도하게 키움
- citation/evidence aggregation이 deterministic stage를 필요로 함
- browser/research worker의 child budget을 parent에서 보장할 수 없음
- deep benchmark가 정한 품질 기준을 넘지 못함

이때도 전체 root graph를 복제하지 않고, 공통 Base Graph에서 호출되는 specialized worker 또는 subgraph로 한정한다.

## 7. 공통 실행 계약

모든 profile은 같은 Tool contract를 사용한다.

```text
precondition
  -> execute
  -> observe
  -> postcondition
  -> typed status
```

필수 상태:

```text
success
stale_ref
ambiguous
wrong_target
no_effect
blocked
timeout
indeterminate
```

profile이 달라도 다음 safety invariant는 바뀌지 않는다.

- approval bypass: 0
- budget overrun: 0
- tenant/capability snapshot leakage: 0
- unknown side effect 자동 재실행: 0
- wrong target 자동 반복: 0

## 8. Upgrade 판단

### 지금 업데이트하지 않는 조건

- v0.4에서 공통 assembly와 Base Graph 또는 측정된 profile bundle로 D1-D5가 구현됨
- quick/deep tool surface를 execution guard로 충분히 제한할 수 있음
- 현재 dependency와 checkpoint가 안정적임
- 최신 HarnessProfile이 필요한 명확한 문제가 없음

### 업데이트하는 조건

- v0.4에서 planning/task/filesystem 제어가 private workaround 없이는 불가능함
- quick profile의 tool schema와 middleware overhead가 목표를 초과함
- 0.7.6의 profile과 opt-in middleware가 custom code를 실질적으로 줄임
- dependency와 state migration을 별도 branch에서 검증함
- upgrade 후 기존 quick와 deep_reference regression이 통과함

최신 버전으로 올려도 다음은 별도로 구현해야 한다.

- per-run orchestration effort
- cumulative time/token budget
- browser execution contract
- research evidence와 citation verifier
- Deep Research 품질 정책

## 9. 운영 및 품질 gate

### Deep gate

- deep_reference multi-step completion rate
- budget 준수율
- checkpoint/resume 성공률
- child worker failure isolation
- browser postcondition verified rate
- citation-supported claim 비율

### Quick gate

- quick total latency와 cost
- quick의 forbidden capability 실행 수: 0
- quick의 success rate가 baseline보다 하락하지 않음
- quick에서 deep capability 호출 시 deterministic denial

### Maintainability gate

- Agent assembly source는 하나
- 공통 Tool contract source는 하나
- 공통 budget/approval middleware source는 하나
- profile별 차이는 정책 데이터와 capability manifest로 표현
- 하나의 Base Graph를 기본으로 사용하되, profile bundle은 ADR과 benchmark 승인 후에만 허용
- 두 번째 root graph를 수동으로 유지하지 않음

## 10. 권장 실행 순서 요약

```text
D-1 agent 구조 및 리팩토링 경계
  -> D0 현재 quick baseline 고정
  -> D1 deep_reference skeleton
  -> D2 deep control plane
  -> D3 deep browser
  -> D4 deep research
  -> D5 deep에서 quick 도출
  -> D6 Plugin capability snapshot 연결
  -> D7 v0.4와 0.7.6 비교
  -> D8 필요할 때만 workflow/subgraph 승격
```

현재 quick만 안정적인 상태라면 먼저 D-1에서 저장소의 Agent 경계를 확인하고 pass-through seam을 만든다. 그 다음 D0에서 quick을 고정하고, D1에서 공통 assembly를 deep 기준으로 확장한다. quick은 나중에 deep의 제한된 view로 만들되, v0.4의 실제 overhead가 크면 같은 assembly에서 profile bundle을 선택한다.

## 참고 자료

- [Deep Agents repository](https://github.com/langchain-ai/deepagents)
- [Deep Agents Deep Research guide](https://docs.langchain.com/oss/python/deepagents/deep-research)
- [Deep Agents profiles](https://docs.langchain.com/oss/python/deepagents/profiles)
- [Browser Use agent parameters](https://docs.browser-use.com/open-source/customize/agent/all-parameters)
- [Browser Use production architecture](https://browser-use.com/posts/production-architecture-browser-use)
- [Browserbase Deep Agents integration](https://docs.browserbase.com/integrations/langchain/deepagents)
- [Browserbase Agents](https://www.browserbase.com/blog/introducing-browserbase-agents)
- [기존 Plugin architecture plan](./deep-agents-plugin-architecture-plan.md)
- [Browser grounding/tool contract review](./browser-grounding-tool-contract-review.md)
