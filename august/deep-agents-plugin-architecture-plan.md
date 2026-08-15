# Deep Agents 기반 멀티 테넌트 Plugin Agent 구축 계획

- 작성일: 2026-08-15
- 저장소: `minguk-jang/spica_at_home`
- 대상 시스템: LangChain Deep Agents + LangGraph 기반 browser-use 계열 웹 조작 에이전트
- 현재 상태: 사용자별 Skill을 서버에서 조회하고 에이전트 실행 시 주입
- 현재 기준 패키지: `deepagents` 0.4.x
- 문서 상태: 설계 및 구현 계획

## 1. 결정 요약

### 1.1 Plugin은 Skill의 상위 개념으로 정의한다

Skill은 에이전트에게 작업 절차와 도메인 지식을 제공한다. Plugin은 다음을 함께 제공한다.

```text
Plugin
├── Manifest
├── Skill bundle
├── 실행 가능한 Tool 또는 MCP Server
├── 권한과 승인 정책
├── 인증 설정
└── 버전과 무결성 정보
```

따라서 기존 Skill 저장 구조를 폐기하지 않는다. 기존 Skill을 Plugin에 연결하고, Plugin이 없는 Skill도 계속 지원한다.

### 1.2 기존 PostgreSQL을 유지하고 확장한다

데이터베이스를 새로운 Plugin 전용 저장소로 교체하지 않는다.

- 기존 `skills` 데이터와 조회 흐름 유지
- Plugin 관련 테이블을 추가
- `Plugin Resolver`를 추가해 Skill, Tool, Policy를 하나의 capability snapshot으로 반환
- 기존 Skill loader는 Plugin Skill을 같은 backend에 materialize하는 어댑터로 재사용

### 1.3 초기 구현은 0.4.x에서 진행한다

Plugin registry, 사용자별 Plugin 활성화, 여러 Plugin Tool 등록, PostgreSQL Skill 조회는 `deepagents` 0.4.x에서 구현 가능하다.

현재 최신 버전은 0.7.6이지만 0.7에는 backend API와 기본 middleware 동작에 breaking change가 있으므로 Plugin 기능만을 이유로 바로 업그레이드하지 않는다.

권장 순서:

1. 현재 0.4.x를 유지한 채 Plugin MVP 구현
2. 현재 버전이 정확히 0.4.0이면 같은 minor 내 `0.4.12` patch upgrade를 별도 검증
3. Plugin 회귀 테스트를 추가한 뒤 0.7 upgrade branch를 별도로 검토

### 1.4 성능 결정: Hybrid Tool Surface를 기본값으로 한다

Plugin을 추가할 때마다 사용자별로 전체 Agent graph와 모든 Tool schema를 다시 구성하지 않는다.

권장 기본값은 다음과 같다.

```text
Graph topology: 고정
Core/browser Tool: 고정
공통 도메인 Tool interface: 고정
Plugin 설정과 구현 endpoint: 동적
Plugin-specific Tool: 필요한 경우에만 lazy loading
Skill 본문: progressive loading
```

Plugin이 같은 기능의 다른 구현체인 경우에는 고정된 Typed Tool interface를 사용한다.

```text
search_documents(query, source)
create_document(title, content, destination)
send_message(recipient, body, provider)
```

Plugin마다 기능과 입력 schema가 완전히 다른 경우에는 `plugin_search`, `plugin_get_schema`, `plugin_dispatch`를 사용하거나 Plugin 전용 subagent/subgraph로 격리한다. 모든 기능을 하나의 자유 형식 `payload`로 뭉치면 Tool schema가 약해져 모델 정확도가 떨어질 수 있다.

따라서 Agent Factory는 정상 요청마다 실행하는 생성기가 아니라, profile cache miss 또는 설정 변경 시에만 실행하는 builder로 정의한다.

### 1.5 Production Runtime Invariants

다음 규칙은 선택사항이 아니라 production 기본 계약으로 둔다.

1. 고정 Base Graph와 stable dispatch surface를 기본 경로로 사용한다.
2. 실행 중인 thread에서 Tool 목록이나 Tool schema를 변경하지 않는다.
3. Typed Plugin Tool은 profile 또는 thread 생성 시점에만 추가할 수 있다.
4. `plugin_dispatch`는 모델의 요청을 신뢰하지 않고 서버에서 plugin, version, operation, schema, tenant, scope, approval state를 모두 재검증한다.
5. thread resume는 현재 Registry를 다시 resolve하지 않고 최초의 immutable capability snapshot을 사용한다.
6. Plugin runtime에 도달한 요청은 side effect 여부가 불명확하면 legacy 경로로 자동 재실행하지 않는다.
7. graph/tool-definition cache, runtime context, Plugin connection/session state를 서로 분리한다.
8. Registry와 policy를 조회할 수 없을 때 새 Plugin 실행은 fail-closed하고, 검증된 기존 snapshot을 가진 resume만 허용한다.

### 1.6 Speed Model과 Fast Path

속도 목표는 `Plugin을 cache한다`가 아니라 end-to-end critical path를 예산 안에 넣는 것으로 정의한다.

```text
request queue/admission
  → AuthN / tenant lookup
  → capability snapshot resolve/create
  → profile/cache lookup
  → prompt와 Tool surface assembly
  → model queue / time-to-first-token
  → Tool selection / dispatch
  → HTTP/MCP/browser pool wait와 remote execution
  → result serialization / context update
  → checkpoint와 audit
  → first visible token / final completion
```

각 단계에 monotonic timestamp와 trace span을 남기고 다음 latency를 별도 SLO로 관리한다.

- time to first visible token
- time to first Tool call
- total completion latency
- resume latency
- Plugin Tool latency
- approval wait time는 시스템 latency와 분리해 별도 관측

하나의 absolute deadline을 DB, model, HTTP/MCP runtime, browser action까지 전달한다. retry와 backoff는 남은 deadline을 소비하며, deadline이 지난 뒤 새로운 discovery나 side effect 호출을 시작하지 않는다. Async request path에서는 blocking DB/HTTP/browser wrapper를 허용하지 않고, 불가피한 sync adapter는 별도 bounded worker pool과 queue budget을 사용한다.

요청 경로는 다음 세 가지로 나누고 thread/profile 경계에서 한 번 선택한다.

```text
Core-only fast path:
  Plugin이 없거나 공통 기능만 필요하면 Plugin discovery Tool을 노출하지 않음

Small typed path:
  작은 Plugin set은 typed Tool을 profile에 한 번 등록

Long-tail dispatch path:
  큰 Plugin set은 안정적인 plugin_dispatch만 노출
  catalog/search/schema Tool은 실제 discovery가 필요할 때만 discovery profile에 추가
```

`plugin_catalog`와 `plugin_search`를 모든 요청의 고정 Tool로 넣는 방식은 schema token과 불필요한 discovery turn을 증가시킬 수 있으므로 기본값으로 채택하지 않는다. Core-only, typed, dispatch/progressive 경로를 task success, token, prompt-cache hit, TTFT, total latency로 비교해 production 기본 경로를 확정한다.

checkpoint와 audit는 critical path에 포함하되, checkpoint에는 큰 Skill 본문, Tool schema, redacted payload를 복제하지 않고 immutable snapshot id와 작은 상태만 저장한다. checkpoint frequency, synchronous durability boundary, retention/pruning을 명시적으로 정하고 benchmark한다. side effect와 resume에 필요한 durability를 성능 때문에 끄지 않는다. 내구성이 꼭 필요하지 않은 audit는 bounded outbox/queue로 분리하고, side effect와 resume에 필요한 기록만 동기 저장한다.

독립적인 read-only Tool만 bounded fan-out으로 병렬 실행한다. run/tenant별 concurrency, queue, connection pool 상한을 두며 side-effect Tool에는 무제한 parallelism이나 hedged request를 적용하지 않는다.

### 1.7 Maintainability Model과 지원 범위

Plugin 형태를 무한히 늘리지 않기 위해 production 지원 경로를 다음으로 제한한다.

```text
Tier A: HTTP Plugin adapter       # 기본 외부/사내 Plugin 경로
Tier B: MCP adapter               # 표준화가 실제로 유리한 경우에만
Tier C: Internal Tool Factory     # core team이 소유한 process-local 기능만
Tier D: LangGraph subgraph        # 다단계 workflow에만
```

새 Plugin은 기본적으로 Tier A를 사용한다. MVP의 production support matrix는 Tier A HTTP만 포함하고, Tier B MCP는 별도 검증 후 추가한다. Tier C는 기존 core-owned factory에 한정하고, Tier D는 다단계 workflow에만 허용한다. MCP, Internal Factory, subgraph를 선택하려면 호환성, 운영 owner, latency/maintenance 근거를 담은 ADR을 남긴다. Plugin마다 임의의 transport, retry, error, auth 방식을 구현하지 않고 공통 Plugin SDK와 conformance suite를 사용한다.

모든 release에는 다음 owner와 lifecycle 정보가 있어야 한다.

```text
owner_team
technical_owner
business_owner
oncall_service
support_tier
runbook_url
status: draft | validated | staged | active | deprecated | sunset | revoked | archived
deprecation_at / sunset_at
replacement_plugin_version
```

Manifest, runtime protocol, Tool input/output, error envelope, auth/context, checkpoint state, SDK를 서로 독립적으로 versioning하고 SemVer와 N-1 compatibility policy를 적용한다. `get_user_skills()`는 별도 규칙을 계속 가지는 두 번째 resolver가 아니라 canonical Capability Resolver를 호출하는 legacy adapter로 단계적으로 바꾼다.

`config_jsonb`와 hierarchical feature flag는 typed/versioned schema로 검증한다. 모든 flag에는 owner, 생성일, 만료일, 제거 ticket, blast radius와 cleanup SLA가 있어야 한다.

## 2. 목표 아키텍처

```text
사용자 요청
    ↓
AuthN / Tenant 권한 확인
    ↓
Capability cache/revision 확인
    ├── new run: enabled Plugin과 pinned version을 bounded query로 resolve
    └── resume: 기존 immutable snapshot만 검증
    ↓
Plugin capability snapshot 생성 또는 재사용
    ├── Skill files
    ├── LangChain Tools 또는 MCP Tools
    ├── Tool namespace
    ├── Permission / approval policy
    └── plugin version hash
    ↓
고정 Base Graph / Agent Profile Cache
    ↓
LangGraph run 및 checkpoint
    ↓
Tool 실행 시 정책 재검증 / 감사 로그
```

각 LangGraph thread의 execution epoch는 시작 시점에 immutable capability snapshot을 생성하고 `capability_snapshots` row에 저장한다. 실행 도중 Plugin 설정이 변경되어도 해당 thread/run은 기존 snapshot을 사용한다.

```python
plugin_snapshot = {
    "snapshot_id": "cap_20260815_abc123",
    "plugins": {
        "browser": "1.0.0",
        "notion": "1.2.0",
        "gmail": "2.1.0",
    },
    "manifest_digests": {
        "notion": "sha256:...",
    },
    "tool_schema_hashes": {
        "notion__search": "sha256:...",
    },
    "policy_version": "policy-3",
    "runtime_contract_version": "plugin-runtime-v1",
    "graph_schema_version": "agent-graph-v4",
    "non_secret_config_hash": "sha256:...",
}
```

checkpoint에는 snapshot id와 다음 정보를 저장한다.

- tenant/user 식별자
- thread/run 식별자
- immutable `snapshot_id`
- 활성 Plugin id와 version
- manifest/artifact digest
- Tool schema hash
- 권한 및 approval 정책 버전
- graph/runtime contract 버전
- browser session id

Resume 시 현재 Registry를 다시 조회하지 않는다. snapshot이 revoke되었거나 runtime contract가 호환되지 않으면 silent fallback하지 않고 명시적으로 blocked 상태로 전환해 재승인 또는 migration을 요구한다.

Resume compatibility 규칙:

| 상황 | 새 run | 기존 snapshot resume |
|---|---|---|
| 새 Plugin version publish | 새 version 선택 가능 | 기존 version 유지 |
| 기존 version revoke | 실행 불가 | drain 후 blocked 또는 명시적 migration |
| policy가 stricter해짐 | 새 policy 사용 | 재승인 또는 blocked |
| runtime contract incompatible | 새 호환 version 필요 | 자동 resume 금지 |
| graph schema incompatible | 새 graph 사용 | migration checkpoint 필요 |
| endpoint/artifact digest 변경 | 검증 전 실행 금지 | 원래 digest 복구 또는 blocked |

API key, OAuth refresh token 같은 secret은 checkpoint나 LLM context에 저장하지 않는다.

## 3. Plugin Manifest

초기 Manifest는 YAML 파일이 아니라 PostgreSQL `JSONB`에 저장해도 된다. 단, 검색과 권한 조인이 필요한 필드는 별도 컬럼 또는 관계 테이블로 둔다.

```yaml
id: shopping
version: 1.2.0
manifest_schema_version: 1
runtime_contract_version: plugin-runtime-v1
sdk_version: plugin-sdk-v1
name: Shopping Plugin
description: Product search and order workflow

ownership:
  owner_team: commerce-platform
  technical_owner: team@example.com
  business_owner: commerce-product
  oncall_service: commerce-plugin
  support_tier: standard
  runbook_url: https://runbooks.example/plugins/shopping

compatibility:
  min_agent_contract: agent-contract-v1
  max_agent_contract: agent-contract-v1
  min_runtime_contract: plugin-runtime-v1

lifecycle:
  status: staged
  deprecation_at: null
  sunset_at: null
  replacement_plugin_version: null

skills:
  - shopping-workflow

runtime:
  transport: http          # http | mcp | internal
  endpoint: https://plugin.internal/shopping

capabilities:
  - search_products
  - add_to_cart
  - create_order

tool_namespace: shopping

scopes:
  - commerce.read
  - commerce.write

approval_required:
  - create_order

artifact_digest: sha256:...
config_schema_ref: https://schemas.example/plugins/shopping/config-v1.json
```

### 3.1 Plugin Contract와 Lifecycle

Plugin release는 다음 계약을 함께 versioning한다.

```text
manifest schema
runtime protocol
Tool input/output schema
error envelope
auth/context propagation
health/readiness
timeout/cancellation/idempotency
checkpoint state
SDK version
```

- schema hash는 정규화된 validated schema에서 생성하며 임의 JSON serialization 순서에 의존하지 않는다.
- major version은 호환되지 않는 변경, minor version은 backward-compatible 추가, patch version은 구현/문서 수정으로 정의한다.
- Plugin runtime은 지원하는 `min/max_*_contract`를 선언하고 Agent는 publish 전에 compatibility를 검증한다.
- 최소 현재 client와 N-1 client/runtime을 contract test로 유지한다.
- runtime은 구조화된 error envelope, health/readiness endpoint, cancellation, deadline, idempotency, trace propagation을 공통으로 제공한다.

Lifecycle은 다음 상태 머신을 사용한다.

```text
draft → validated → staged → active → deprecated → sunset → archived
                         └→ revoked
```

`revoked`는 신규 실행과 resume 정책을 분리해 적용한다. deprecation에는 replacement version, migration guide, sunset date, exception owner가 필요하다. Registry에서 active version을 publish하기 전에 manifest lint, schema compatibility, SDK conformance, security/SBOM, integration test, load smoke를 통과해야 한다.

필수 원칙:

- Tool 이름은 `plugin_id__tool_name` 형태로 namespace를 붙인다.
- Manifest의 Tool schema와 실제 runtime schema가 다르면 실행을 거부한다.
- version은 mutable tag가 아니라 immutable release를 가리킨다.
- Plugin 설명과 Skill 본문은 권한 정책보다 낮은 신뢰 레벨의 입력으로 취급한다.

## 4. PostgreSQL 확장안

### 4.1 기존 테이블

기존 `skills` 테이블은 유지한다.

가능하다면 다음 nullable 컬럼만 추가한다.

```text
source_type             # user | project | plugin
plugin_version_id       # nullable foreign key
skill_key               # unique key for override and lookup
content_hash            # cache invalidation
status                  # active | archived
```

기존 Skill API가 있다면 하위 호환을 유지한다.

```python
get_user_skills(user_id) -> list[Skill]
```

### 4.2 추가 테이블

```text
plugins
- id
- slug
- display_name
- description
- owner_tenant_id
- owner_team
- technical_owner
- business_owner
- oncall_service
- support_tier
- runbook_url
- status
- created_at
- updated_at

plugin_versions
- id
- plugin_id
- version
- manifest_schema_version
- runtime_contract_version
- sdk_version
- config_schema_version
- min_agent_contract
- max_agent_contract
- manifest_jsonb
- transport
- endpoint
- artifact_digest
- status
- deprecation_at
- sunset_at
- replacement_plugin_version_id
- published_at

plugin_skills
- plugin_version_id
- skill_id
- mount_path
- priority

user_plugins
- user_id
- tenant_id
- plugin_id
- pinned_version
- enabled
- config_jsonb
- created_at
- updated_at

capability_snapshots
- id
- tenant_id
- user_id
- thread_id
- snapshot_hash
- manifest_digests_jsonb
- tool_schema_hashes_jsonb
- policy_version
- runtime_contract_version
- graph_schema_version
- non_secret_config_hash
- migrator_version
- status
- expires_at
- last_used_at
- created_at

plugin_permissions
- plugin_version_id
- tool_name
- scope
- risk_level
- approval_required
- policy_version

plugin_runs
- run_id
- thread_id
- tenant_id
- user_id
- snapshot_id
- plugin_id
- plugin_version
- tool_name
- status
- attempt
- idempotency_key
- approval_id
- trace_id
- queued_at
- dispatched_at
- completed_at
- latency_ms
- error_class
- receipt_ref
- redacted_input_jsonb
- redacted_output_jsonb
- retention_until
- created_at
```

`manifest_jsonb`와 `config_jsonb`는 확장성을 위해 사용한다. 사용자 권한, version pin, Tool allowlist처럼 조회 빈도가 높은 필드는 JSONB 안에만 숨기지 않는다.

### 4.3 Database invariants

Migration에는 다음 제약조건과 운영 규칙을 포함한다.

- 모든 테이블에 명시적인 primary key와 foreign key를 둔다.
- `(plugin_id, version)`은 unique이며 publish 이후 version row를 수정하지 않는다.
- `plugin_permissions`는 `plugin_version_id`에 연결해 pinned thread의 정책이 바뀌지 않게 한다.
- `capability_snapshots`는 immutable insert-only record로 운영하고 삭제 대신 status를 변경한다.
- 모든 resolver query는 `tenant_id`를 포함하고, 가능한 환경에서는 PostgreSQL RLS를 적용한다.
- `user_plugins`, `plugin_versions`, `plugin_permissions`, `capability_snapshots`에 tenant-aware composite index를 추가한다.
- snapshot 생성은 entitlement, version, policy를 하나의 transaction에서 읽고 snapshot hash를 저장한다.
- `config_jsonb`에는 secret 값이 아니라 secret manager reference만 저장한다.
- `plugin_runs`는 보존 기간, partition, redaction 정책을 적용한다.
- tenant별 concurrency, payload, runtime connection, storage quota와 noisy-neighbor 방어를 적용한다.
- side-effect Tool은 `idempotency_key`와 attempt를 저장하고 중복 실행을 차단한다.
- 같은 `thread_id`와 execution epoch에 대해 snapshot이 하나만 생성되도록 unique constraint와 idempotent create를 적용한다.
- `manifest_jsonb`, `config_jsonb`, Tool schema는 각각 schema version과 canonical serialization을 사용한다.
- snapshot에는 큰 Skill 본문과 schema를 복제하지 않고 immutable artifact reference와 digest만 저장한다.
- snapshot, plugin_runs, audit/outbox를 위한 scheduled retention worker, partition maintenance, archive/legal hold 정책을 둔다.
- DB migration은 expand → dual-read/write → backfill → cutover → contract 순서로 수행하고 lock timeout, progress, abort, roll-forward를 정의한다.
- graph/checkpoint state migration은 source/target version별 migrator registry와 fixture를 통해 검증한다.

Resolver가 Registry에 접근할 수 없는 경우 새 Plugin을 fail-closed한다. 이미 검증된 snapshot을 가진 resume은 snapshot artifact와 policy를 다시 검증할 수 있을 때만 허용한다.

## 5. 내부 Resolver API

Agent가 PostgreSQL을 직접 조회하지 않도록 내부 Repository와 Resolver를 둔다.

```python
@dataclass
class AgentCapabilities:
    snapshot_id: str
    run_id: str
    execution_epoch: int
    skills: list[SkillSource]
    tools: list[BaseTool]
    plugin_snapshot: dict[str, str]
    policy: PluginPolicy
    runtime_contract_version: str
    graph_schema_version: str


async def resolve_agent_capabilities(
    *,
    user_id: str,
    tenant_id: str,
    thread_id: str,
    run_id: str,
    execution_epoch: int,
) -> AgentCapabilities:
    ...
```

Resolver의 책임:

1. 사용자와 tenant의 enabled Plugin 조회
2. entitlement과 scope 검증
3. pinned version 또는 현재 승인 버전 결정
4. Skill source materialize
5. Tool factory 또는 remote runtime client 생성
6. Tool namespace 충돌 검사
7. Plugin snapshot hash 생성
8. 실행 정책 반환
9. canonical effective-capability projection을 반환하고, legacy `get_user_skills()`는 이 Resolver/Repository를 호출하는 compatibility adapter로 유지

Legacy와 Plugin path가 각자 entitlement, version, Skill precedence를 구현하지 않는다. dual-read 기간에는 결과를 비교하지만 business rule의 source of truth는 하나로 둔다.

권장 내부 endpoint 예시:

```text
# snapshot 생성은 idempotent command이므로 GET과 분리
PUT /internal/threads/{thread_id}/capability-snapshot
  Idempotency-Key: <thread-start-key>

# 기존 snapshot 조회/검증
GET /internal/capability-snapshots/{snapshot_id}
```

Capability Resolver의 hot path는 명시적으로 분리한다.

```text
new run + valid warm cache:
  cache lookup/revision check → one idempotent snapshot insert if persistence is required

new run + cache miss or stale security revision:
  entitlement/version/permission/skill metadata를 bounded batched query로 조회
  Plugin/Skill마다 N+1 query 금지

resume:
  현재 Registry를 resolve하지 않음
  snapshot id, artifact digest, policy compatibility만 최소 read로 검증
```

모든 benchmark에 다음을 기록하고 query plan regression을 둔다.

```text
DB query count
DB pool wait
transaction duration
rows/bytes returned
snapshot insert latency
EXPLAIN plan hash
```

응답 예시:

```json
{
  "snapshot_id": "cap_20260815_abc123",
  "plugins": [
    {
      "id": "notion",
      "version": "1.2.0",
      "skills": ["notion-workflow"],
      "tools": ["notion__search", "notion__create_page"],
      "scopes": ["notion.read", "notion.write"]
    }
  ],
  "skill_sources": ["/plugins/notion/skills"],
  "policy_version": "policy-3"
}
```

## 6. Deep Agent 연결 방식

### 6.1 기본 방식: 고정 Base Graph와 Agent Profile Cache

정상 요청마다 사용자별 Agent graph를 새로 compile하지 않는다. 프로세스 또는 Agent 설정 단위로 고정된 Base Graph를 만들고, 사용자별 Plugin 설정은 runtime context와 Plugin Router에 전달한다.

```python
FIXED_CORE_TOOLS = [
    *core_browser_tools,
    *stable_domain_tools,
]

# Thread/profile 경계에서만 선택한다. 실행 중 mutation은 금지한다.
PLUGIN_TYPED_TOOLS = resolved_typed_plugin_tools
PLUGIN_DISPATCH_TOOLS = [plugin_dispatch]
PLUGIN_DISCOVERY_TOOLS = [plugin_catalog, plugin_search, plugin_get_schema]

agent = create_deep_agent(
    model=model,
    tools=profile_tools,  # FIXED_CORE_TOOLS + thread/profile-bound selected tools
    middleware=[
        PluginRouterMiddleware(),
        PluginPolicyMiddleware(),
        AuditMiddleware(),
    ],
    checkpointer=checkpointer,
)
```

thread/profile 경계에서는 다음처럼 한 번만 Tool surface를 선택한다.

```python
if not active_plugins:
    selected_tools = FIXED_CORE_TOOLS
elif small_typed_profile:
    selected_tools = [*FIXED_CORE_TOOLS, *PLUGIN_TYPED_TOOLS]
elif discovery_profile:
    selected_tools = [
        *FIXED_CORE_TOOLS,
        *PLUGIN_DISPATCH_TOOLS,
        *PLUGIN_DISCOVERY_TOOLS,
    ]
elif needs_long_tail:
    selected_tools = [*FIXED_CORE_TOOLS, *PLUGIN_DISPATCH_TOOLS]
else:
    selected_tools = [*FIXED_CORE_TOOLS, *PLUGIN_DISPATCH_TOOLS]

profile_tools = selected_tools
```

`discovery_profile`은 host-side index가 task에 필요한 capability를 찾을 때만 선택한다. 이 선택은 thread 시작 후 변경하지 않는다. 실제 Deep Agents 0.4.x에서 profile별 Tool binding이 안전한지 먼저 검증하고, 불확실하면 고정 `plugin_dispatch` profile을 사용한다.

사용자별 값은 graph 안에 closure로 고정하지 않는다.

```python
runtime_context = {
    "user_id": user_id,
    "tenant_id": tenant_id,
    "thread_id": thread_id,
    "plugin_snapshot": plugin_snapshot,
    "browser_session_id": browser_session_id,
}
```

공통 기능은 고정된 Typed Tool로 제공하고, Plugin마다 schema가 다른 기능은 `plugin_dispatch`로 라우팅한다. Dynamic Typed Tool을 사용하더라도 profile 또는 thread 생성 시점에만 추가하며, 실행 중인 thread의 Tool 목록을 변경하지 않는다.

`PluginRouterMiddleware`는 매 model/tool turn마다 Registry를 다시 조회하지 않고 runtime context의 verified snapshot을 읽는 cheap no-op fast path를 가져야 한다. Security-critical scope/approval과 side-effect 정책만 실행 직전에 bounded validation한다.

`plugin_dispatch`는 다음을 모델과 별개로 server-side에서 검증한다.

```text
allowed tenant
snapshot_id and plugin_version
operation and input schema
scope and entitlement
approval state and expiry
endpoint and artifact digest
```

Agent profile cache를 사용하는 경우 다음 값을 cache key에 포함한다.

```text
plugin_snapshot_hash
model_id
policy_version
runtime_contract_version
graph_schema_version
agent_config_version
core_tool_schema_version
```

사용자 ID 자체는 graph cache key로 사용하지 않는 것을 우선한다. 단, Tool이 사용자별 secret이나 page 객체를 closure로 캡처한다면 해당 graph는 공유하지 않고 runtime context 기반 wrapper로 바꿔야 한다.

profile cache miss가 발생하면 한 요청만 profile을 생성하도록 singleflight 또는 분산 lock을 적용한다. Plugin enable, disable, publish가 발생하면 관련 profile만 invalidate하고 인기 조합은 background warm-up한다.

Profile cache key의 `plugin_snapshot_hash`에는 tenant-scoped entitlement revision, endpoint identity, non-secret config hash, policy version, Tool schema digest가 포함되어야 한다. 이 정보가 hash에 포함된다는 것을 보장할 수 없으면 tenant_id를 cache key에 추가한다.

인증 token, API key, browser page 객체, 사용자별 secret, mutable runtime client는 Agent profile cache에 포함하지 않는다. Immutable graph/tool definition cache와 thread-scoped runtime connection/session state를 분리한다.

Profile에 포함되는 Tool 정의는 immutable하고 thread-safe해야 한다. connection, session, retry state를 보유한 mutable Tool instance는 profile cache에 공유하지 않고 invocation-time factory 또는 runtime context에서 생성한다.

### 6.2 Plugin 구성과 Tool surface 선택

모든 Plugin Tool을 항상 모델에 노출하지 않는다. Plugin 수와 Tool schema 크기에 따라 세 가지 경로를 선택한다.

#### Small Plugin Set

활성 Plugin 수가 적고 Tool schema가 작으면 profile을 만들 때 필요한 Typed Tool을 한 번 등록한다.

```text
Plugin 3개, Tool 15개 이하 등 작은 조합
    ↓
profile cache에 Tool schema 포함
    ↓
다음 요청부터 cache 재사용
```

이 경우 불필요한 discovery turn이 없어 일반적인 browser workflow에 유리하다.

#### Large Plugin Set

활성 Plugin이 많거나 Tool definition이 context window의 상당 부분을 차지하면 progressive discovery를 사용한다.

```text
discovery profile
├── plugin_catalog
├── plugin_search
├── plugin_get_schema
└── plugin_dispatch

plugin_search("문서 관리")
    ↓
필요한 Plugin 후보만 반환
    ↓
plugin_get_schema(plugin_id, operation)
    ↓
plugin_dispatch(plugin_id, operation, arguments)
```

발견 임계값은 고정 숫자가 아니라 모델 context window 대비 비율과 실제 Tool schema token 수로 설정한다. 초기 기준은 context의 1~5%를 넘으면 progressive discovery를 검토하는 방식으로 둔다. 이 값은 휴리스틱일 뿐 release gate가 아니며 task success와 latency benchmark로 확정한다.

Discovery에는 hard limit을 둔다.

```text
max discovery turns
max candidate Plugins/tools returned
max schema bytes per turn
max total discovery tokens
max discovery wall-clock deadline
```

`plugin_search`는 전체 manifest를 모델에 반환하지 않고 host-side index에서 top-k candidate만 반환한다. discovery turn을 넘겨도 자동으로 무한히 재시도하지 않고, 사용 가능한 capability와 이유를 구조화해 사용자 또는 상위 Agent에 반환한다.

Plugin별 Tool schema를 직접 모델에 추가해야 하는 경우에는 Plugin 활성화 또는 thread 경계에서 한 번만 추가한다. 매 turn마다 Tool을 추가하거나 제거하지 않는다. Stable Tool surface가 필요하면 고정 `plugin_dispatch`를 사용한다.

다음 세 경로를 동일한 task fixture로 비교한다.

```text
static typed Tool
stable dispatch
progressive discovery
```

비교값은 Tool selection accuracy만이 아니라 성공률, 추가 model turn, prompt-cache hit, input/output token, TTFT, total latency, runtime error율, 운영 복잡도다. 가장 빠른 경로가 아니라 성공한 작업당 latency와 cost가 가장 낮은 경로를 기본값으로 선택한다.

공통 기능은 다음처럼 명확한 Typed Tool로 유지한다.

```text
search_documents(query, source)
create_document(title, content, destination)
browser_action(action, target)
```

완전히 새로운 기능이나 복잡한 workflow는 Plugin 전용 Tool, subagent, 또는 LangGraph subgraph로 분리한다. 자유 형식 `payload` 하나로 모든 Plugin을 표현하는 방식은 긴 꼬리 기능에만 사용한다.

Raw `StateGraph`를 직접 구성할 때는 compile 이후 ToolNode의 Tool 목록이 자동 변경된다고 가정하지 않는다. 고정 graph + middleware 기반 노출, profile 재생성, 고정 dispatch node 중 하나를 명시적으로 선택한다.

### 6.3 Cache, lazy loading, latency 관측

Plugin을 사용하지 않는 요청에서 Plugin runtime에 연결하거나 전체 Skill을 materialize하지 않는다.

Cache는 다음 세 계층으로 분리한다.

```text
graph/tool-definition cache: immutable, cross-user 재사용 가능
runtime context: thread/user 단위, secret reference와 snapshot 포함
Plugin connection/session: thread 또는 runtime 단위, mutable client 보관
```

Cache 운영 규칙:

- manifest, Tool schema, Skill content는 immutable version/digest key로 cache한다.
- mutable BaseTool, MCP client, credential, browser session은 graph cache에 넣지 않는다.
- TTL, memory bound, negative cache, stale-read limit을 설정한다.
- replica 간 invalidation은 audited event 또는 transactional notification으로 전파한다.
- entitlement/policy cache가 stale하면 새 실행은 fail-closed한다.
- cache stampede와 cross-tenant hit를 별도 테스트한다.
- cache key는 canonicalized config, authorization context, schema digest, endpoint identity를 포함한다.
- stale-while-revalidate는 일반 manifest/schema에만 허용하고 권한 revoke와 side-effect policy에는 허용하지 않는다.
- invalidation event 유실을 대비해 monotonic registry revision과 periodic reconciliation을 사용한다.
- expiry jitter와 bounded stale fallback으로 동시 만료 stampede를 막는다.

Singleflight는 profile만이 아니라 다음 key를 별도로 관리한다.

```text
capability snapshot
profile/tool definition
manifest/schema discovery
MCP connection/session
browser session startup
```

각 singleflight에는 leader/waiter cancellation, lock timeout/fencing, negative result TTL, per-tenant concurrency limit을 정의한다. side-effecting operation은 singleflight 대상이 아니다.

```text
Plugin manifest:
  plugin_id + version + digest cache

Skill metadata:
  name + description cache

Skill content:
  content_hash 기반 cache

Tool schema:
  plugin_id + version + schema_hash cache

MCP tools/list:
  server_id + version + digest + auth/cache scope + pagination key cache
  honor ttlMs and invalidate immediately on list_changed
```

MCP `tools/list`와 discovery cache는 `cacheScope`가 public인지 private인지에 따라 공유 범위를 결정한다. private 결과는 authorization context별로 격리하고, pagination page와 requestState를 cache key에서 누락하지 않는다. prompt cache를 유지하기 위해 stable Tool prefix를 보존하고, 대화 중 Tool array를 재정렬하거나 대량 교체하지 않는다.

권장 실행 흐름:

1. thread 시작 시 capability snapshot을 한 번 resolve
2. cache hit이면 registry read와 remote discovery를 건너뛰되, 새 thread의 immutable snapshot persistence가 필요하면 idempotent insert만 수행
3. cache miss이면 manifest와 권한을 검증
4. Skill metadata만 우선 로드
5. 실제 Skill 본문과 Tool schema는 필요할 때 로드
6. MCP connection과 handshake는 graph 생성 시점이 아니라 Plugin 활성화 시점에 수행
7. stateful browser Plugin은 thread 단위 session을 유지
8. Plugin publish, `list_changed`, entitlement 변경 시 관련 cache만 invalidate

다음 지표를 별도로 기록한다.

```text
request_queue_ms
auth_tenant_lookup_ms
capability_resolve_ms
db_pool_wait_ms
db_query_count
snapshot_insert_ms
profile_cache_hit
profile_build_ms
prompt_assembly_ms
skill_materialize_ms
tool_schema_cache_hit
mcp_discovery_ms
http_pool_wait_ms
mcp_initialize_ms
model_queue_ms
model_first_token_ms
first_visible_token_ms
prompt_input_tokens
plugin_dispatch_ms
tool_execution_ms
checkpoint_save_ms
audit_outbox_ms
final_completion_ms
```

모든 model call은 다음 token/context breakdown을 남긴다.

```text
system_tokens
history_tokens
skill_tokens
tool_schema_tokens
browser_state_tokens
tool_result_tokens
output_tokens
discovery_turn_count
prompt_cache_hit
```

Checkpoint save, audit write, remote response serialization은 각각 동기/비동기 경계를 문서화하고 별도 latency budget을 둔다.

cold start와 warm start를 분리해 p50/p95를 측정한다. 특히 `profile_build_ms`와 `mcp_discovery_ms`를 Agent graph compile 비용과 혼동하지 않는다.

## 7. Plugin Runtime 선택

### 7.1 HTTP Runtime

초기 MVP에는 HTTP가 가장 단순하다.

```text
Deep Agent
  ↓ LangChain Tool wrapper
Plugin API
  ↓
외부 서비스 / 브라우저 / 사내 API
```

장점:

- 기존 REST API를 재사용하기 쉬움
- 인증, rate limit, tracing, retry를 기존 API gateway에 적용 가능
- Deep Agents 0.4와 결합이 단순함
- MCP dependency와 protocol lifecycle을 먼저 도입하지 않아도 됨

단점:

- Tool discovery를 직접 구현해야 함
- Tool schema와 API schema를 동기화해야 함

HTTP runtime 운영 계약:

- async HTTP client와 host별 keep-alive/HTTP2 connection pool을 사용한다.
- pool size, pool wait timeout, DNS/TCP/TLS, request/response first-byte 시간을 관측한다.
- timeout은 connect, write, read, total deadline으로 분리하고 retry는 error class와 idempotency에 따라 제한한다.
- connection 생성과 health check는 bounded singleflight로 묶고, pool exhaustion은 backpressure로 처리한다.
- 모든 요청은 trace context, tenant, snapshot, idempotency key를 전달한다.

### 7.2 MCP Runtime

여러 Tool을 표준화하고 외부 Plugin 생태계를 만들 필요가 있을 때 도입한다.

```text
Deep Agent
  ↓ langchain-mcp-adapters
MCP Client
  ↓ Streamable HTTP
MCP Plugin Server
```

MCP를 쓰더라도 Plugin Registry는 자체적으로 유지한다. MCP server가 사용자 권한, tenant entitlement, version pin을 대신 결정하게 두지 않는다.

MCP runtime 운영 계약:

- `initialize`와 `tools/list` handshake는 runtime identity, contract version, authorization context에 맞는 session pool에서 재사용한다.
- stateful MCP server는 thread session을 connection과 분리하고, session idle timeout/close/reconnect를 명시한다.
- shared session은 immutable/read-only capability에만 사용하고, browser/credential state는 thread 단위로 격리한다.
- connection/handshake 생성은 singleflight하고 pool wait, initialize, tools/list, first byte를 관측한다.
- `tools/list`의 `ttlMs`, `cacheScope`, pagination, `list_changed`를 보존하며 auth context가 다른 결과는 공유하지 않는다.
- burst 시 무제한 prewarm하지 않고 high-probability Plugin에만 bounded warm-up을 적용한다.

### 7.3 Internal Tool Factory

브라우저 조작처럼 같은 process 안에서 안정적으로 제공해야 하는 기능은 내부 Tool factory로 관리할 수 있다.

```python
TRUSTED_TOOL_FACTORIES = {
    "browser": build_browser_tools,
    "search": build_search_tools,
}
```

DB의 문자열을 Python import 경로로 사용해 임의 코드를 실행하지 않는다.

### 7.4 Plugin SDK와 Conformance

Plugin SDK는 단순한 helper library가 아니라 유지보수 경계를 제공한다.

```text
typed manifest/config models
canonical schema hashing
context/auth/idempotency helpers
standard error envelope
health/readiness endpoint helpers
deadline/cancellation propagation
OpenTelemetry propagation
local runtime harness
contract-test runner
schema compatibility linter
package/sign/publish CLI
```

Registry publish 전에 모든 Plugin version은 다음 certification을 통과한다.

```text
manifest/config validation
schema compatibility
HTTP/MCP contract
auth/RLS and tenant isolation
failure/retry/idempotency
load/soak smoke
security/SBOM/license scan
N-1 agent/runtime compatibility
```

SDK와 contract는 현재 버전과 N-1 지원 기간을 명시한다. Plugin team이 개별적으로 만든 retry, tracing, error, credential, cache 구현은 production 경로로 허용하지 않는다.

## 8. 브라우저 에이전트 특화 고려사항

Plugin runtime은 전역 browser page를 보관하지 않는다.

각 Tool 호출에 다음 context를 전달한다.

```text
user_id
tenant_id
thread_id
run_id
browser_session_id
allowed_domains
plugin_scopes
```

브라우저 Plugin이 필요한 경우:

- browser session은 사용자와 thread 단위로 격리
- Plugin이 다른 사용자 session id를 임의로 지정하지 못하게 함
- navigation, click, type은 core browser layer에서 정책 처리
- 구매, 제출, 삭제, 메시지 발송은 승인 대상 지정
- Plugin output은 문자열보다 구조화된 결과를 우선
- Tool 결과에 provenance와 side-effect 상태 포함

브라우저 경로는 remote Plugin latency와 분리해 다음 구간을 관측한다.

```text
page/session acquisition
browser queue wait
navigation DNS/TLS/network wait
DOM 또는 screenshot capture
action execution
wait condition
result serialization
browser state tokens/bytes
```

대표 task를 simple read, multi-page navigation, login/session reuse, long workflow로 나눠 process-cold, browser-cold, browser-warm을 각각 benchmark한다. DOM/screenshot은 무조건 전체를 model context에 넣지 않고 byte/token budget, pagination, viewport/region 정책을 적용한다. browser context/page는 cancellation과 run 종료 시 반드시 close/release한다.

## 9. 보안 정책

### 반드시 적용할 정책

- DB에 저장된 Python 코드 직접 실행 금지
- Plugin service는 allowlist된 endpoint와 artifact만 사용
- 모든 Tool call 실행 시점에 tenant/user/scope 재검증
- secret은 Vault 또는 secret manager에서 runtime에 주입
- Skill과 Tool description은 prompt injection 가능한 untrusted content로 취급
- Tool name과 manifest의 capability를 server-side에서 대조
- 고위험 Tool은 LangGraph interrupt 또는 별도 approval flow 적용
- Tool input/output과 Plugin version을 redacted audit log에 기록
- Plugin runtime outbound domain과 rate limit 제한
- version과 artifact digest pinning
- endpoint allowlist와 SSRF 방어
- registry/runtime 장애 시 fail-closed
- circuit breaker, bulkhead, cancellation, payload limit 적용
- approval replay, approval expiry, version revoke 검증
- tenant RLS와 cache cross-tenant isolation 검증

### 9.1 실행 상태와 Retry 계약

`plugin_runs.status`는 임의 문자열이 아니라 다음 상태 머신으로 제한한다.

```text
queued → approved → dispatched → succeeded
                         ├→ retryable_failure
                         ├→ permanent_failure
                         ├→ ambiguous
                         └→ cancelled
```

표준 error envelope에는 `error_class`, `retryable`, `side_effect_state`, `receipt_ref`, `retry_after`, `user_action`을 포함한다.

- validation/auth/policy 오류는 retry하지 않는다.
- connect/read timeout은 side effect가 실행되지 않았다는 증거가 있을 때만 retry한다.
- side-effect Tool은 idempotency와 receipt가 확인된 경우에만 제한적으로 retry한다.
- retry는 총 deadline, attempt budget, exponential backoff, circuit breaker threshold를 따른다.
- cancellation은 Agent → wrapper → gateway → runtime → browser까지 전파한다.
- `ambiguous`는 자동 legacy fallback하지 않고 durable reconciliation queue와 operator workflow로 처리한다.

### 9.2 Telemetry와 Operator Control Plane

모든 계층은 다음 telemetry contract를 공유한다.

```text
request_id, trace_id, span_id
tenant_id, user_id, thread_id, run_id, snapshot_id
 plugin_id, plugin_version, tool_name, attempt
 endpoint, transport, outcome, error_class
```

Agent → Tool wrapper → gateway → Plugin runtime → downstream까지 OpenTelemetry context를 전파한다. RED metric, queue/pool saturation, cache staleness, error-budget burn, retry/ambiguous outcome을 Plugin별 dashboard와 alert로 제공한다. redaction, sampling, retention, high-cardinality 제한도 공통 SDK에서 적용한다.

운영자는 audited control plane에서 다음 작업을 수행할 수 있어야 한다.

- effective Plugin/config/flag/snapshot resolution 조회
- snapshot, checkpoint, approval, idempotency receipt 조회
- runtime health와 dependency 상태 확인
- 특정 cache key warm/invalidate
- plugin/version/tool disable 또는 kill switch
- runtime drain/quiesce
- 명시적으로 idempotent한 작업만 retry
- redacted diagnostic bundle export

모든 operator action에는 actor, reason, change/ticket id, old/new state를 기록한다.

### 위험도 예시

| Risk | 예시 | 기본 정책 |
|---|---|---|
| low | 검색, 페이지 읽기 | 자동 실행 |
| medium | Notion 페이지 작성, 이메일 draft | 정책에 따라 승인 |
| high | 주문, 결제, 삭제, 메시지 발송 | 사용자 승인 필수 |
| critical | credential 변경, 권한 변경, 대량 전송 | 별도 workflow와 이중 확인 |

## 10. 라이선스 및 회사 사용 검토

아래 구성요소는 확인 시점 기준 permissive license 계열이다.

| 구성요소 | 라이선스 | 참고 |
|---|---|---|
| Deep Agents | MIT | 공식 저장소 및 package metadata |
| LangChain | MIT | 공식 저장소 |
| LangGraph | MIT | 공식 저장소 |
| langchain-mcp-adapters | MIT | 공식 저장소 |
| MCP Python SDK | MIT | 공식 저장소 |
| FastAPI | MIT | 공식 저장소 |
| PostgreSQL | PostgreSQL License | BSD/MIT와 유사한 permissive license |
| pgvector 선택 사용 | PostgreSQL License 계열 | extension 자체 라이선스 별도 확인 |

주의사항:

- MCP는 protocol 이름이지 모든 MCP server의 라이선스를 보장하지 않는다.
- Plugin server와 transitive dependency의 라이선스를 각각 검사한다.
- MIT 라이선스인 adapter를 사용해도 연결하는 외부 서비스의 API 약관은 별도다.
- LangGraph OSS library 라이선스와 hosted/deployment 제품의 사용 조건은 별도 검토한다.
- 회사 정책상 MIT만 허용하지 않는다면 Apache-2.0, BSD, ISC 등 permissive license allowlist를 정의한다.
- 배포 전 SBOM과 license notice를 생성한다.

라이선스가 엄격한 환경의 기본 조합:

```text
PostgreSQL
+ FastAPI
+ 공식 MCP Python SDK 선택 사용
+ LangChain / LangGraph / Deep Agents library
+ 자체 Plugin Registry
+ 자체 Plugin Runtime
```

## 11. 단계별 구현 계획

### Phase 0. 현재 시스템 inventory

- 현재 Deep Agents 정확한 patch version 확인
- LangChain, LangGraph, langchain-core lock 확인
- 현재 Skill 테이블과 API 필드 목록화
- Skill을 Deep Agents backend에 주입하는 지점 확인
- browser tool의 context와 session lifecycle 확인
- 현재 uncommitted 변경사항과 배포 환경 확인
- Plugin이 없는 baseline과 Plugin 1개/5개/20개 조건의 cold/warm latency 측정
- `capability_resolve_ms`, `profile_build_ms`, `mcp_discovery_ms`, `model_first_token_ms` 측정 지점 추가
- 현재 모델 provider의 prompt caching 조건과 Tool schema token 수 확인
- end-to-end stage span과 absolute deadline propagation 구현
- DB pool, HTTP/MCP pool, browser queue wait 계측
- benchmark fixture를 다음 축으로 정의

```text
no Plugin / 1 / 5 / 20 Plugins
warm / process-cold / cache-cold / connection-cold
HTTP / MCP
static typed / dispatch / progressive discovery
non-browser / browser
1 / 10 / 100 / 1,000 concurrent requests
```

- production model, region, gateway, DB, browser runtime을 사용하는 대표 benchmark 준비

### Phase 1. Plugin Registry 데이터 모델

- `plugins` 추가
- `plugin_versions` 추가
- `plugin_skills` 추가
- `user_plugins` 추가
- 기존 `skills`에 nullable source metadata 추가
- migration과 rollback 작성
- plugin version pin 정책 구현
- manifest/config schema version과 lifecycle/owner 필드 추가
- expand/dual-read/backfill/cutover/contract migration runbook 작성

### Phase 1.5. Plugin SDK와 Release Train

- typed manifest/config model과 canonical schema hash 구현
- 공통 error, health/readiness, deadline, cancellation, idempotency, tracing helper 구현
- local runtime harness와 contract-test CLI 구현
- schema compatibility linter와 N-1 compatibility fixture 구현
- dependency lock, Python/browser/container/LangChain/LangGraph/Deep Agents/MCP SDK matrix 고정
- dependency update → compatibility CI → staging → canary → production release train 정의
- CVE severity/SLA, SBOM/license scan, artifact retention, release owner와 rollback gate 정의

### Phase 2. Capability Resolver

- `resolve_agent_capabilities()` 구현
- 사용자/tenant entitlement 검사
- Skill source materializer 구현
- Plugin snapshot hash 구현
- Tool namespace 검사
- manifest, Skill content, Tool schema cache 구현
- cache invalidation과 singleflight 구현
- 기존 `get_user_skills()`와 backward compatibility 유지
- new-run/resume의 query shape와 query budget 검증
- batched query와 EXPLAIN plan regression test 작성
- snapshot create를 idempotent하게 만들고 N+1 query를 차단
- Resolver 실패/재시도/error state를 표준 error envelope로 변환

### Phase 3. 첫 번째 Plugin

- 별도 staging에서 동작하는 read-only Test Plugin을 첫 runtime으로 선정
- HTTP runtime으로 시작
- LangChain Tool wrapper 추가
- Tool input/output schema 추가
- audit log와 timeout/retry 추가
- 0.4.x 고정 Base Graph와 Agent Profile Cache에 연결

### Phase 4. 멀티 Plugin과 승인

- 두 개 이상의 Plugin을 한 Agent에 등록
- Plugin 간 결과 전달 테스트
- 독립 작업의 병렬화와 의존 작업의 순차화 테스트
- 위험 Tool approval 적용
- tool collision과 tenant isolation 테스트
- static Typed Tool과 `plugin_dispatch` 경로의 Tool 선택 정확도 비교
- Plugin 수 증가에 따른 prompt token과 first-token latency 측정
- 동일 profile 동시 생성에 대한 singleflight 테스트
- capability snapshot, schema, connection, browser startup singleflight 테스트
- leader/waiter cancellation, lock timeout/fencing, negative result TTL 테스트
- 독립적인 read-only Tool의 bounded parallel scheduler와 fan-out 상한 검증

### Phase 5. MCP 선택 도입

- HTTP Plugin과 동일한 capability contract 유지
- MCP transport adapter 구현
- Streamable HTTP MCP server 검토
- MCP server별 license와 dependency scan
- graph 생성 시점이 아닌 Plugin 활성화 시점의 lazy connection 구현
- `tools/list` 결과 cache와 `list_changed` invalidation 구현
- TTL/cacheScope/pagination/auth context를 포함한 cache key 검증
- HTTP keep-alive/HTTP2 pool, MCP initialize/session pool, bounded pool wait 구현
- connection/handshake singleflight와 idle close/reconnect 검증
- 필요할 때만 on-demand activation 구현

### Phase 6. 복잡한 Plugin을 LangGraph subgraph로 분리

- 다단계 workflow를 subgraph로 식별
- typed input/output contract 정의
- interrupt, retry, compensation 처리
- main Agent에서 plugin subgraph를 호출하는 route 추가

### Phase 7. 업그레이드 평가

0.4.x에서 다음 조건이 충족된 뒤 0.7 upgrade를 별도 branch에서 진행한다.

- 기존 Skill regression 통과
- 멀티 Plugin regression 통과
- checkpoint resume 통과
- HITL resume 통과
- browser session isolation 통과
- Tool audit log 검증
- backend와 todo 동작 차이 검증
- Plugin 1개/5개/20개 cold/warm latency 회귀 기준 통과
- profile cache hit율과 MCP discovery cache hit율 기준 통과
- prompt input token 증가량과 first-token latency 기준 통과
- current/N-1 dependency와 Plugin SDK compatibility CI 통과
- checkpoint migrator와 retention/pruning 검증
- production representative load/soak 및 connection/browser capacity 기준 통과

## 12. 안전한 전환을 위한 Migration Milestones

Plugin 전환은 기존 Skill-only 경로를 한 번에 바꾸는 Big Bang migration으로 진행하지 않는다. 기존 경로를 보존한 상태에서 테스트 Plugin을 먼저 등록하고, shadow, canary, rollback을 거쳐 실제 Skill을 하나씩 Plugin으로 전환한다.

### 12.1 전환 원칙

- 기존 `get_user_skills()`와 Skill-only Agent 실행 경로는 마지막까지 유지한다.
- 모든 새 기능은 feature flag 뒤에 둔다.
- DB migration은 backward-compatible하게 작성한다.
- Plugin runtime 오류와 기존 Skill loader 오류를 구분해 기록한다.
- Plugin version은 immutable release로 고정한다.
- side-effect 실행이 불확실한 경우 legacy 경로로 자동 재실행하지 않는다.
- Plugin Resolver 실패처럼 실행 전 발생한 오류만 안전한 범위에서 legacy fallback을 허용한다.
- 실제 Plugin migration은 read-only Skill부터 시작한다.

권장 feature flag 예시:

```text
plugin_registry_read
plugin_capability_snapshot
plugin_test_runtime
plugin_tool_execution
plugin_skill_source
plugin_canary_tenants
plugin_legacy_fallback
```

기본값은 모두 off로 시작하고, flag별로 독립적으로 rollback할 수 있어야 한다.

Feature flag 운영 규칙:

- 적용 순서는 global → tenant → plugin → version → tool의 가장 좁은 범위를 우선한다.
- 권한, policy, registry를 확인할 수 없으면 fail-closed한다.
- flag 변경은 actor, reason, old/new value, effective time을 audit한다.
- replica 간 propagation SLA와 stale flag의 최대 허용 시간을 정의한다.
- 새 run에는 최신 flag를 적용하고, resume run은 원래 snapshot과 flag compatibility를 확인한다.
- plugin/version/tool 단위 kill switch를 제공한다.
- canary error budget 초과 시 자동으로 신규 Plugin 실행을 중지한다.

### 12.2 Test Plugin 정의

첫 Plugin은 실제 외부 서비스가 아니라 deterministic test Plugin으로 만든다. 목적은 기능 시연이 아니라 다음 경로를 모두 검증하는 것이다.

```text
PostgreSQL registry
  → manifest/version 조회
  → Skill materialize
  → Agent Tool 등록 또는 dispatch
  → Plugin runtime 호출
  → policy/audit/checkpoint
  → 오류와 rollback
```

Test Plugin은 사내 staging 또는 local test server에 배포하고, 운영 데이터에는 접근하지 않는다. 단, local fixture의 latency를 production SLO 근거로 사용하지 않는다. production과 동일한 gateway, TLS, region, network path, connection pool을 재현하는 remote benchmark 환경을 별도로 둔다.

권장 구성:

```text
test-plugin/
├── plugin.yaml
├── skills/
│   └── test-plugin-workflow/SKILL.md
├── runtime/
│   ├── http_server.py
│   └── mcp_server.py       # MCP 검증 시 선택
└── tests/
    ├── test_manifest.py
    ├── test_runtime_contract.py
    └── test_failure_modes.py
```

최소 Tool set:

| Tool | 목적 | side effect |
|---|---|---|
| `test__echo` | 입력과 context 검증 | 없음 |
| `test__create_record` | Tool schema, approval, audit 검증 | staging DB 또는 ephemeral store에만 기록 |
| `test__fail` | deterministic error와 retry 검증 | 없음 |
| `test__delay` | timeout과 latency 관측 | 없음 |

`test__create_record`는 production DB가 아닌 별도 `plugin_test_records` 또는 in-memory store만 사용한다. `test__fail`과 `test__delay`는 의도적으로 오류와 지연을 발생시켜 resilience를 검증한다.

Test Plugin은 다음 failure/abuse fixture도 제공한다.

```text
malformed_output
schema_drift
unauthorized_tenant
auth_failure
ambiguous_timeout
duplicate_delivery
approval_expired
approval_replay
rate_limit
payload_too_large
```

HTTP runtime과 선택적인 MCP runtime이 같은 capability contract와 오류 분류를 반환하는지 parity test를 작성한다. `test__create_record`의 side effect는 idempotency key로 중복 실행되지 않아야 한다.

Test Plugin의 Skill에는 실제 외부 서비스 지식 대신 다음을 명시한다.

- 어떤 상황에 `test__echo`를 사용하는지
- `test__create_record`가 승인 대상임
- `test__fail` 오류를 사용자에게 어떻게 보고하는지
- Plugin version과 snapshot을 결과에 어떻게 기록하는지

### 12.3 Server 저장 및 등록 흐름

Test Plugin을 server에서 저장하고 사용하는 전체 경로를 먼저 완성한다.

```text
1. plugin_versions에 test Plugin manifest/version 등록
2. plugin_skills로 기존 skills 또는 새 Skill bundle 연결
3. user_plugins에서 staging tenant에만 enable
4. runtime endpoint를 staging test server로 설정
5. Plugin Resolver가 capability snapshot 생성
6. Agent가 Skill과 Tool을 사용
7. plugin_runs에 redacted audit 기록
```

DB에는 실행 코드를 저장하지 않는다.

- Manifest, version, Skill reference, endpoint, digest, policy는 PostgreSQL에 저장
- runtime 코드는 배포된 staging service 또는 trusted package로 관리
- DB의 문자열을 Python import 경로로 사용해 임의 코드를 실행하지 않음
- endpoint와 artifact digest를 allowlist와 대조

초기 Test Plugin은 HTTP runtime으로 시작한다. 기존 API gateway와 observability를 재사용하기 쉽고, Deep Agents 0.4.x에 연결하는 경계가 단순하기 때문이다. 이후 동일한 capability contract를 사용해 MCP runtime을 추가한다.

### 12.4 Milestone M0: Legacy baseline 고정

목표: Plugin을 추가하지 않아도 기존 동작이 변하지 않는다는 기준을 만든다.

작업:

- 기존 Skill-only 실행 경로의 golden task 목록 작성
- 동일한 사용자 입력에 대한 expected tool sequence와 결과 저장
- Skill loader, browser session, checkpoint resume의 regression test 작성
- Plugin이 없는 요청의 p50/p95 latency 기록
- 기존 API response와 DB query count 기록
- request queue, resolver, prompt assembly, model TTFT, Tool/remote, browser, checkpoint/audit, final completion stage 기록
- DB pool wait, HTTP/MCP pool wait, browser queue wait 기록
- current production model/network/gateway/DB/browser와 Test Plugin fixture의 차이 기록
- 현재 uncommitted 작업 및 배포 설정을 별도로 보관

Exit criteria:

- baseline test가 반복 실행에서 동일하게 통과한다.
- Plugin 관련 flag가 모두 off일 때 기존 trace와 결과가 유지된다.
- rollback 시 baseline 경로로 돌아가는 smoke test가 통과한다.

Rollback:

- 아무 변경도 하지 않고 기존 Skill-only 경로 유지

### 12.5 Milestone M1: Additive Registry Migration

목표: 기존 테이블과 API를 깨지 않고 Plugin metadata를 저장한다.

작업:

- `plugins`, `plugin_versions`, `plugin_skills`, `user_plugins` migration 추가
- 필요한 경우 `skills`에 nullable source metadata 추가
- 모든 신규 컬럼에 안전한 default 또는 nullable 설정 적용
- migration 전후 `get_user_skills()` 결과 비교
- migration rollback script 작성
- registry read flag를 off로 둔 상태에서 배포

Exit criteria:

- 기존 Skill query가 동일한 결과를 반환한다.
- migration을 적용한 뒤 legacy application이 정상 동작한다.
- migration rollback과 재적용이 검증된다.
- expand/dual-read/backfill/cutover/contract 순서와 mixed-version 동작이 검증된다.
- manifest/config schema migration과 checkpoint migrator fixture가 검증된다.
- Test Plugin manifest를 staging DB에 등록할 수 있다.

Rollback:

- `plugin_registry_read=off`
- 신규 테이블을 읽지 않고 기존 Skill API만 사용
- 데이터 삭제가 필요한 rollback은 별도 승인 후 수행

### 12.6 Milestone M2: Test Plugin Runtime과 Contract Test

목표: Agent가 server에 등록된 Test Plugin을 안전하게 발견하고 호출한다.

작업:

- Test Plugin HTTP runtime 배포
- health check, timeout, retry, idempotency key 구현
- manifest의 Tool schema와 runtime schema 비교
- `test__echo`, `test__create_record`, `test__fail`, `test__delay` contract test 작성
- malformed output, schema drift, auth/RLS, duplicate delivery, ambiguous timeout, approval replay 테스트 작성
- HTTP/MCP contract parity 검증
- Tool namespace, version, digest 검증
- payload limit, rate limit, cancellation, resource exhaustion 검증
- standard error envelope와 plugin_runs state transition 검증
- SDK conformance CLI와 schema compatibility linter 통과
- health/readiness, tracing, deadline propagation 검증
- staging tenant에만 `plugin_test_runtime=on`

Exit criteria:

- 잘못된 schema, 잘못된 version, 비허용 endpoint가 차단된다.
- 성공, validation error, timeout, server error가 각각 구조화되어 반환된다.
- `test__create_record`는 승인 없이 실행되지 않는다.
- 모든 실행에 `plugin_id`, version, run_id, thread_id가 audit된다.

Rollback:

- `plugin_test_runtime=off`
- Test Plugin endpoint 차단
- 기존 Skill-only 경로는 계속 사용

### 12.7 Milestone M3: Shadow Capability Resolver

목표: 실제 Agent Tool surface를 바꾸지 않고 Plugin Resolver를 검증한다.

작업:

- 요청마다 legacy Skill resolver와 Plugin Resolver를 함께 실행
- Plugin capability snapshot을 생성하되 Agent 실행에는 사용하지 않음
- 두 resolver 결과의 Skill key, permission, version, cache 상태 비교
- Resolver latency와 DB query count 측정
- DB pool wait, rows/bytes, transaction duration, snapshot insert latency 측정
- batched query와 EXPLAIN plan hash 비교
- 불일치 결과를 audit 또는 debug log에만 기록

Exit criteria:

- 내부 사용자 요청에서 snapshot 생성 실패율이 0에 가깝고 원인이 분류된다.
- legacy와 Plugin Skill metadata가 의도한 범위에서 일치한다.
- Plugin Resolver cache hit와 invalidation이 검증된다.
- 기존 사용자 응답과 first-token latency에 변화가 없다.

Rollback:

- `plugin_capability_snapshot=off`
- legacy resolver만 실행

### 12.8 Milestone M4: Dual Loader와 Test Plugin Agent Path

목표: 기존 Skill과 Plugin Skill을 같은 Agent 실행에서 안전하게 비교한다.

작업:

- legacy Skill source와 Plugin Skill source를 같은 test thread에 주입하는 adapter 구현
- 고정 Base Graph에 Test Plugin의 공통 Typed Tool 또는 `plugin_dispatch` 연결
- Tool 실행 전 policy 검사와 실행 후 audit 비교
- checkpoint 저장과 resume 테스트
- plugin snapshot이 thread 단위로 고정되는지 확인
- Agent가 사용자별 secret이나 browser page를 profile cache에 캡처하지 않는지 검사
- checkpoint에 snapshot reference만 저장하고 large Skill/schema/payload를 중복 저장하지 않는지 검사
- checkpoint save, audit outbox, prompt assembly latency와 retention/pruning 검증

Exit criteria:

- Test Plugin 사용 thread가 성공적으로 완료되고 resume된다.
- legacy Skill-only thread의 결과가 바뀌지 않는다.
- Plugin이 disabled이거나 권한이 없으면 Tool이 실행되지 않는다.
- Plugin runtime 오류가 전체 Agent graph 오류로 확산되지 않는다.

Rollback:

- `plugin_tool_execution=off`
- Agent는 기존 core Tool과 legacy Skill만 사용

### 12.9 Milestone M5: Staging Canary와 Rollback Drill

목표: 실제 서비스 흐름과 동일한 조건에서 제한된 사용자에게만 Plugin을 제공한다.

작업:

- 내부 staging tenant를 canary 대상으로 지정
- `plugin_canary_tenants` allowlist 운영
- Test Plugin과 기존 Skill-only 경로의 결과와 latency 비교
- Plugin runtime down, stale version, cache miss, permission denial 상황 재현
- 운영자가 flag를 끄고 legacy 경로로 복귀하는 rollback drill 수행
- in-flight Plugin call drain과 quiesce 절차 검증
- ambiguous timeout과 side-effect receipt를 수동/자동으로 분류
- canary 자동 abort threshold와 fail-closed 조건 확정
- dashboard와 alert 기준 확정
- operator control plane의 inspect, invalidate/warm, disable, drain, diagnostic export 권한과 audit 검증
- standard error state machine, retry budget, reconciliation queue 검증

Canary 중 비교할 지표:

```text
legacy_success_rate
plugin_success_rate
capability_resolve_ms
profile_cache_hit
mcp_discovery_ms
model_first_token_ms
plugin_tool_error_rate
approval_latency
rollback_time
```

Exit criteria:

- 내부 canary에서 정한 error budget 이내다.
- rollback이 목표 시간 안에 완료된다.
- 오류가 legacy, resolver, runtime, model, browser 계층으로 분류된다.
- side-effect가 중복 실행되지 않는다.

Rollback:

1. 신규 run에 대한 `plugin_tool_execution=off`
2. Plugin runtime을 drain하고 in-flight call 완료 또는 blocked 상태 확인
3. ambiguous outcome은 idempotency receipt로 reconciliation
4. `plugin_skill_source=off`
5. `plugin_capability_snapshot=off`
6. 마지막으로 `plugin_registry_read=off`

이미 runtime에 도달한 요청은 legacy 경로로 자동 재실행하지 않는다. Resume thread는 원래 snapshot이 호환되는지 확인한 뒤 계속하거나 명시적 재승인을 요구한다.

### 12.10 Milestone M6: 실제 Read-only Skill 1개 전환

목표: 위험도가 낮은 기존 Skill 한 개를 Plugin으로 변환한다.

선정 조건:

- 외부 side effect가 없거나 매우 낮음
- deterministic한 expected result를 만들 수 있음
- 사용자 credential을 직접 다루지 않음
- 실패 시 기존 Skill-only 경로로 쉽게 복귀 가능

작업:

- 기존 Skill을 Plugin Skill bundle로 포장
- 기존 Skill key와 Plugin Skill key를 mapping
- 기존 Skill과 Plugin Skill을 같은 golden task로 실행
- shadow 또는 dual-run으로 결과 비교
- 내부 canary 후 점진적으로 tenant 확대

Exit criteria:

- 기존 golden task의 결과와 Tool sequence가 허용 범위 내에서 일치한다.
- Plugin version pin과 rollback이 작동한다.
- Skill content cache와 Plugin metadata cache가 의도대로 invalidate된다.
- 최소 한 번의 실제 rollback drill을 통과한다.

Rollback:

- 해당 Skill의 mapping만 legacy source로 되돌린다.
- Plugin 전체를 disable하지 않고 영향 범위가 있는 Skill만 rollback한다.

### 12.11 Milestone M7: Plugin 확대와 Long-tail 경로

목표: 두 개 이상의 Plugin을 조합하고, Plugin 수 증가에 따른 성능 저하를 통제한다.

작업:

- 두 번째 read-only Plugin 추가
- 공통 Typed Tool과 `plugin_dispatch`의 적용 범위 확정
- Plugin 1개/5개/20개 조건에서 cold/warm benchmark 실행
- Tool schema context threshold 초과 시 progressive discovery 전환
- cache warm-up, singleflight, `list_changed` invalidation 검증
- Plugin 간 데이터 전달과 tenant isolation 테스트
- registry outage, plugin outage, cache stampede, long schema, concurrency load test
- Tool selection accuracy, approval latency, DB query budget, p95/p99 비교
- static typed/dispatch/progressive discovery의 성공한 작업당 latency와 cost 비교
- 1/10/100/1,000 concurrency 및 cache/connection stampede load/soak 테스트
- HTTP/MCP connection pool, handshake reuse, pool exhaustion 테스트
- browser process/session/page queue와 DOM/screenshot token budget 테스트
- browser session concurrency, HITL resume, checkpoint compatibility 테스트

Exit criteria:

- Plugin 수 증가에도 정한 p95와 token budget을 만족한다.
- 공통 기능은 Typed Tool로, long-tail 기능은 dispatch 또는 subgraph로 분리되어 있다.
- Plugin 하나의 장애가 다른 Plugin과 legacy 경로에 전파되지 않는다.

### 12.12 Milestone M8: 운영 전환과 Legacy Deprecation

목표: 충분한 운영 기간과 회귀 검증 후 legacy 경로를 단계적으로 정리한다.

작업:

- Plugin 전환율과 legacy fallback 비율 관측
- Plugin version publish/rollback runbook 확정
- license/SBOM/security scan 자동화
- legacy Skill과 Plugin Skill의 중복 데이터 정리 계획 수립
- deprecation 기간과 owner 지정
- deprecated/revoked version의 tenant/thread consumer discovery
- sunset 전 warning, new enable 차단, replacement version migration dry-run 제공
- legacy path 제거 전 마지막 rollback checkpoint 생성

Exit criteria:

- 모든 production 대상 Skill에 owner, version, rollback path가 있다.
- 모든 Plugin version이 SDK conformance와 N-1 compatibility를 통과한다.
- 지정된 기간 동안 error budget과 latency 기준을 만족한다.
- deprecation consumer discovery, migration guide, sunset enforcement가 동작한다.
- legacy fallback을 당장 켤 수 있는 상태로 보존한다.
- 운영 승인 후에만 legacy Skill을 archive한다.

### 12.13 전환 완료 체크리스트

```text
[ ] 기존 Skill-only baseline test 통과
[ ] additive DB migration과 rollback 검증
[ ] Test Plugin이 server registry에 등록됨
[ ] Test Plugin Skill이 PostgreSQL에서 조회됨
[ ] Test Plugin runtime contract test 통과
[ ] Test Plugin Agent 실행과 checkpoint resume 통과
[ ] disabled/unauthorized Plugin 차단 확인
[ ] timeout/failure/cache invalidation 검증
[ ] canary flag와 legacy fallback 검증
[ ] 실제 read-only Skill 1개 전환 완료
[ ] Plugin 수 증가 benchmark 통과
[ ] version pin과 rollback runbook 완료
```

### 12.14 Production-readiness test matrix와 release gate

Canary 전에 다음 테스트 계층을 모두 통과해야 한다.

| 계층 | 필수 검증 |
|---|---|
| Unit | Manifest validation, resolver, policy, namespace, snapshot hash |
| Integration | PostgreSQL migration, RLS, transaction snapshot, cache invalidation |
| Contract | HTTP/MCP Tool schema, malformed output, timeout, error class |
| Agent | Deep Agents 0.4.x graph, middleware ordering, runtime context propagation |
| Migration | Mixed-version app/DB, forward/backward compatibility, rollback |
| Security | Auth/RLS, tenant isolation, SSRF, secret reference, prompt injection boundary |
| Reliability | Retry, idempotency, cancellation, circuit breaker, bulkhead, ambiguous outcome |
| Browser | Session isolation, concurrent tabs, allowed domains, browser checkpoint resume |
| HITL | Approval expiry, replay, revoke, interrupt/resume |
| Performance | 1/5/20 Plugin cold/warm, concurrency, cache stampede, long schema |
| Capacity | DB/HTTP/MCP/browser pool, queueing, noisy neighbor, soak, 1/10/100/1,000 concurrency |
| Browser performance | Session/page acquisition, navigation, DOM/screenshot, action and result serialization latency |
| Checkpoint | Minimal snapshot reference, save latency, retention, pruning, state migrator |
| Observability | Trace propagation, RED metrics, cardinality/redaction, alert and error-budget burn |
| Operator | Effective config, snapshot/checkpoint inspection, cache control, drain, kill switch, diagnostic export |
| SDK/Release | Manifest lint, schema compatibility, N-1, SBOM/license, artifact promotion and rollback |
| Rollout | Canary flag propagation, automatic abort, drain, legacy fallback |

Release gate는 측정값을 기록하는 것으로 끝내지 않고 사전에 수치로 고정한다.

```text
resolver/profile/tool p95 and p99
first-visible-token, first-tool-call, resume, and total-run latency
request queue, DB/HTTP/MCP/browser pool wait budget
DB query/rows/bytes budget per run
checkpoint-save and audit-outbox budget
manifest/schema/cache hit target
system/history/skill/schema/browser/result token budget
prompt-cache hit target and discovery-turn budget
Tool selection accuracy and successful-task latency/cost target
Plugin error budget and retry/ambiguous outcome budget
maximum stale-policy interval
maximum per-run/tenant concurrency and fan-out
rollback completion target
maximum discovery turns
```

이 값이 정해지지 않은 상태에서는 production canary를 시작하지 않는다.

### 12.15 Maintainability gate

Production Plugin은 기능이 동작하는 것만으로 인증하지 않는다.

```text
unit
→ contract
→ integration
→ failure injection
→ load/soak smoke
→ N-1 compatibility
→ staging canary
```

CI는 빠른 manifest/schema/unit/contract 단계와 느린 integration/load/security 단계를 분리한다. full Agent golden suite는 release candidate와 변경 영향이 있는 경우에만 실행하고, flaky test는 quarantine owner와 복구 기한을 가진다.

각 Plugin version은 owner_team, oncall, support tier, runbook, SLO, dependency/SBOM, rollback path, deprecation/sunset 정보를 가져야 한다. publish/revoke/drain/rollback 권한과 escalation 시간을 명시한다.

운영 중에는 다음을 자동 보고한다.

- tenant/thread별 사용량과 의존 consumer
- deprecated/revoked version 사용량
- replacement version migration 진행률
- flag 만료 및 cleanup 지연
- cache/storage/connection/snapshot capacity
- Plugin별 error budget burn과 test certification 상태

이 gate를 통과하지 않은 Plugin은 Registry에 `active`로 publish하지 않는다.

## 13. 완료 조건

### 기능

- 사용자별 enabled Plugin을 조회할 수 있다.
- 한 Agent가 두 개 이상의 Plugin을 사용할 수 있다.
- 기존 Skill과 Plugin Skill을 함께 사용할 수 있다.
- Plugin version을 thread 단위로 고정할 수 있다.
- Plugin Tool 결과를 다른 Plugin Tool의 입력으로 전달할 수 있다.
- read-only Plugin과 side-effect Plugin을 구분할 수 있다.

### 운영

- Plugin을 enable/disable할 수 있다.
- 새 version을 publish하고 이전 version으로 rollback할 수 있다.
- Plugin Tool call을 audit할 수 있다.
- timeout, retry, rate limit을 적용할 수 있다.
- Plugin runtime 장애가 전체 Agent 장애로 번지지 않는다.
- Immutable release row와 tenant-aware DB constraint가 적용된다.
- snapshot을 재사용하는 resume compatibility matrix가 통과한다.
- in-flight와 ambiguous side effect rollback drill이 통과한다.
- production-readiness test matrix가 통과한다.
- 표준 Plugin SDK/conformance suite와 N-1 compatibility가 통과한다.
- owner, oncall, runbook, SLO, release/rollback 권한이 지정된다.
- standard error state machine과 reconciliation workflow가 운영된다.
- operator control plane과 redacted diagnostic bundle이 감사 가능하게 동작한다.

### 성능

- Plugin이 없는 요청은 Plugin runtime discovery를 수행하지 않는다.
- 동일한 Plugin snapshot에서 Agent profile cache hit가 발생한다.
- Agent graph는 사용자마다 재생성하지 않는다.
- Skill 본문은 필요한 시점에만 materialize한다.
- Tool schema와 MCP `tools/list` 결과는 version/digest 기준으로 cache한다.
- Plugin 수가 증가해도 Tool schema가 context threshold를 넘으면 progressive discovery로 전환한다.
- cold start와 warm start의 p50/p95를 별도로 관측한다.
- profile 동시 생성이 singleflight로 중복되지 않는다.
- snapshot/schema/connection/browser startup singleflight와 pool backpressure가 동작한다.
- end-to-end deadline이 DB/model/Plugin/browser까지 전파된다.
- checkpoint/audit overhead와 large result/token budget이 제한된다.
- connection reuse와 browser warm/cold capacity가 목표를 만족한다.

### 전환

- 모든 legacy Skill-only golden task가 Plugin flag off 상태에서 통과한다.
- Test Plugin이 server registry, Skill storage, runtime, Agent, audit까지 end-to-end로 검증된다.
- Plugin Resolver 실패 시 안전한 범위에서 legacy fallback이 작동한다.
- side-effect가 있는 Plugin 오류에 대해 자동 legacy 재실행을 하지 않는다.
- canary tenant와 rollback flag가 운영 환경에서 검증된다.
- 실제 read-only Skill 1개 이상이 rollback 가능한 상태로 Plugin 전환된다.
- Plugin version pin, migration rollback, runtime rollback 절차가 문서화되어 있다.
- revoked, unavailable, incompatible snapshot에 대한 resume 동작이 정의되어 있다.
- plugin runtime에 도달한 요청을 legacy로 자동 재실행하지 않는 것이 검증되어 있다.
- deprecated version consumer discovery와 sunset enforcement가 동작한다.
- canonical Resolver와 legacy adapter의 결과가 migration 기간에 비교 가능하다.
- config/flag의 owner, expiry, cleanup SLA가 검증된다.

### 보안

- 사용자가 권한 없는 Plugin을 활성화할 수 없다.
- Tool 실행 시점에 scope가 재검증된다.
- secret이 LLM message, Skill 파일, checkpoint에 남지 않는다.
- 다른 tenant의 Skill, Tool, browser session이 노출되지 않는다.
- 고위험 side effect는 승인 없이 실행되지 않는다.

## 14. 조사 출처

- [Deep Agents PyPI](https://pypi.org/project/deepagents/)
- [Deep Agents 0.4.0 PyPI](https://pypi.org/project/deepagents/0.4.0/)
- [Deep Agents repository](https://github.com/langchain-ai/deepagents)
- [Deep Agents releases](https://github.com/langchain-ai/deepagents/releases)
- [Deep Agents changelog](https://docs.langchain.com/oss/python/releases/changelog)
- [Deep Agents overview](https://docs.langchain.com/oss/python/deepagents/overview)
- [Deep Agents skills](https://docs.langchain.com/oss/python/deepagents/skills)
- [Deep Agents tools and MCP](https://docs.langchain.com/oss/python/deepagents/tools)
- [LangChain tools and dynamic tool registration](https://docs.langchain.com/oss/python/langchain/tools)
- [LangChain MCP](https://docs.langchain.com/oss/python/langchain/mcp)
- [LangChain context engineering](https://docs.langchain.com/oss/python/deepagents/context-engineering)
- [LangChain MCP client best practices](https://modelcontextprotocol.io/docs/2026-07-28/develop/clients/client-best-practices)
- [LangChain MCP Adapters](https://github.com/langchain-ai/langchain-mcp-adapters)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [LangGraph](https://github.com/langchain-ai/langgraph)
- [LangGraph durable execution and checkpoints](https://docs.langchain.com/oss/javascript/langgraph/durable-execution)
- [MCP caching](https://modelcontextprotocol.io/specification/draft/server/utilities/caching)
- [FastAPI](https://github.com/fastapi/fastapi)
- [PostgreSQL License](https://www.postgresql.org/about/licence/)
- [pgvector](https://github.com/pgvector/pgvector)

## 15. 추가 결정이 필요한 항목

이 문서 작성과 초기 MVP에는 추가 정보가 필요하지 않다. 구현을 시작할 때 아래 항목만 확정하면 된다.

1. 현재 설치된 정확한 `deepagents` patch version이 0.4.0인지 0.4.x인지
2. 첫 번째 Plugin의 실행 transport를 HTTP로 시작할지 MCP로 시작할지
3. Plugin scope가 user 단위인지 tenant 단위인지
4. OAuth/API credential을 어떤 secret manager에서 관리할지
5. side-effect Tool의 승인 수준과 감사 보존 기간
6. Plugin을 사내 전용으로 둘지 외부 Plugin도 허용할지
7. static Typed Tool과 progressive discovery 전환 임계값
8. profile cache TTL, invalidation, warm-up 정책
9. cold/warm latency와 first-token latency의 목표 p95
10. Test Plugin의 staging runtime 배포 방식
11. canary tenant 선정 기준과 rollback owner
12. legacy Skill fallback을 유지할 기간
13. in-flight call drain과 ambiguous side-effect reconciliation 정책
14. snapshot revoke/upgrade 시 resume compatibility 정책
15. feature flag scope, precedence, propagation SLA, automatic abort 기준
16. production-readiness release gate의 p95/p99와 error budget
17. Core-only/typed/dispatch/progressive discovery 중 production 기본 fast path
18. end-to-end deadline, DB query/rows budget, pool/concurrency budget
19. HTTP keep-alive/HTTP2와 MCP session/handshake pool 정책
20. checkpoint/audit의 동기 저장 범위, outbox, retention/pruning
21. Plugin SDK, manifest/runtime/tool/error contract의 current/N-1 지원 기간
22. Plugin owner/oncall/support tier/SLO와 publish/revoke/drain/rollback 권한
23. feature flag와 config의 최대 수, expiry, cleanup SLA
24. deprecated consumer discovery와 checkpoint/graph state migrator 정책

초기 구현 권장안은 다음과 같다.

```text
deepagents 0.4.x 유지
PostgreSQL 유지
기존 Skill API 유지
Plugin Registry 추가
HTTP Tool wrapper로 첫 Plugin 구현
MCP는 transport adapter로 후속 도입
0.4.x regression 이후 0.7 upgrade 검토
```
