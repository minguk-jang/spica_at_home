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

## 2. 목표 아키텍처

```text
사용자 요청
    ↓
AuthN / Tenant 권한 확인
    ↓
Plugin Registry 조회
    ↓
사용자별 enabled Plugin과 pinned version 결정
    ↓
Plugin capability snapshot 생성
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

각 LangGraph thread는 시작 시점에 immutable capability snapshot을 생성하고 `capability_snapshots` row에 저장한다. 실행 도중 Plugin 설정이 변경되어도 진행 중인 thread는 기존 snapshot을 사용한다.

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
name: Shopping Plugin
description: Product search and order workflow

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
```

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
- status
- created_at
- updated_at

plugin_versions
- id
- plugin_id
- version
- manifest_jsonb
- transport
- endpoint
- artifact_digest
- status
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
- status
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
- latency_ms
- error_class
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
- side-effect Tool은 `idempotency_key`와 attempt를 저장하고 중복 실행을 차단한다.

Resolver가 Registry에 접근할 수 없는 경우 새 Plugin을 fail-closed한다. 이미 검증된 snapshot을 가진 resume은 snapshot artifact와 policy를 다시 검증할 수 있을 때만 허용한다.

## 5. 내부 Resolver API

Agent가 PostgreSQL을 직접 조회하지 않도록 내부 Repository와 Resolver를 둔다.

```python
@dataclass
class AgentCapabilities:
    snapshot_id: str
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

권장 내부 endpoint 예시:

```text
GET /internal/agent-capabilities
  ?tenant_id=...
  &user_id=...
  &thread_id=...
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
    plugin_catalog,
    plugin_search,
    plugin_dispatch,
]

agent = create_deep_agent(
    model=model,
    tools=FIXED_CORE_TOOLS,
    middleware=[
        PluginRouterMiddleware(),
        PluginPolicyMiddleware(),
        AuditMiddleware(),
    ],
    checkpointer=checkpointer,
)
```

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

### 6.2 Plugin 구성과 Tool surface 선택

모든 Plugin Tool을 항상 모델에 노출하지 않는다. Plugin 수와 Tool schema 크기에 따라 두 가지 경로를 선택한다.

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
기본 Agent
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

발견 임계값은 고정 숫자가 아니라 모델 context window 대비 비율과 실제 Tool schema token 수로 설정한다. 초기 기준은 context의 1~5%를 넘으면 progressive discovery를 검토하는 방식으로 둔다.

Plugin별 Tool schema를 직접 모델에 추가해야 하는 경우에는 Plugin 활성화 또는 thread 경계에서 한 번만 추가한다. 매 turn마다 Tool을 추가하거나 제거하지 않는다. Stable Tool surface가 필요하면 고정 `plugin_dispatch`를 사용한다.

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
  server_id + version + digest cache
```

권장 실행 흐름:

1. thread 시작 시 capability snapshot을 한 번 resolve
2. cache hit이면 DB와 remote discovery를 건너뜀
3. cache miss이면 manifest와 권한을 검증
4. Skill metadata만 우선 로드
5. 실제 Skill 본문과 Tool schema는 필요할 때 로드
6. MCP connection과 handshake는 graph 생성 시점이 아니라 Plugin 활성화 시점에 수행
7. stateful browser Plugin은 thread 단위 session을 유지
8. Plugin publish, `list_changed`, entitlement 변경 시 관련 cache만 invalidate

다음 지표를 별도로 기록한다.

```text
capability_resolve_ms
profile_cache_hit
profile_build_ms
skill_materialize_ms
tool_schema_cache_hit
mcp_discovery_ms
model_first_token_ms
prompt_input_tokens
plugin_dispatch_ms
tool_execution_ms
```

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

### 7.3 Internal Tool Factory

브라우저 조작처럼 같은 process 안에서 안정적으로 제공해야 하는 기능은 내부 Tool factory로 관리할 수 있다.

```python
TRUSTED_TOOL_FACTORIES = {
    "browser": build_browser_tools,
    "search": build_search_tools,
}
```

DB의 문자열을 Python import 경로로 사용해 임의 코드를 실행하지 않는다.

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

### Phase 1. Plugin Registry 데이터 모델

- `plugins` 추가
- `plugin_versions` 추가
- `plugin_skills` 추가
- `user_plugins` 추가
- 기존 `skills`에 nullable source metadata 추가
- migration과 rollback 작성
- plugin version pin 정책 구현

### Phase 2. Capability Resolver

- `resolve_agent_capabilities()` 구현
- 사용자/tenant entitlement 검사
- Skill source materializer 구현
- Plugin snapshot hash 구현
- Tool namespace 검사
- manifest, Skill content, Tool schema cache 구현
- cache invalidation과 singleflight 구현
- 기존 `get_user_skills()`와 backward compatibility 유지

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

### Phase 5. MCP 선택 도입

- HTTP Plugin과 동일한 capability contract 유지
- MCP transport adapter 구현
- Streamable HTTP MCP server 검토
- MCP server별 license와 dependency scan
- graph 생성 시점이 아닌 Plugin 활성화 시점의 lazy connection 구현
- `tools/list` 결과 cache와 `list_changed` invalidation 구현
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

Test Plugin은 사내 staging 또는 local test server에 배포하고, 운영 데이터에는 접근하지 않는다.

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
- legacy path 제거 전 마지막 rollback checkpoint 생성

Exit criteria:

- 모든 production 대상 Skill에 owner, version, rollback path가 있다.
- 지정된 기간 동안 error budget과 latency 기준을 만족한다.
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
| Rollout | Canary flag propagation, automatic abort, drain, legacy fallback |

Release gate는 측정값을 기록하는 것으로 끝내지 않고 사전에 수치로 고정한다.

```text
resolver/profile/tool p95 and p99
first-token and total-run latency
DB query budget per run
manifest/schema/cache hit target
Tool selection accuracy target
Plugin error budget
maximum stale-policy interval
rollback completion target
maximum discovery turns
```

이 값이 정해지지 않은 상태에서는 production canary를 시작하지 않는다.

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

### 성능

- Plugin이 없는 요청은 Plugin runtime discovery를 수행하지 않는다.
- 동일한 Plugin snapshot에서 Agent profile cache hit가 발생한다.
- Agent graph는 사용자마다 재생성하지 않는다.
- Skill 본문은 필요한 시점에만 materialize한다.
- Tool schema와 MCP `tools/list` 결과는 version/digest 기준으로 cache한다.
- Plugin 수가 증가해도 Tool schema가 context threshold를 넘으면 progressive discovery로 전환한다.
- cold start와 warm start의 p50/p95를 별도로 관측한다.
- profile 동시 생성이 singleflight로 중복되지 않는다.

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
