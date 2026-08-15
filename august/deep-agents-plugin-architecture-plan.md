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
Deep Agent Factory
    ↓
LangGraph run 및 checkpoint
    ↓
Tool 실행 시 정책 재검증 / 감사 로그
```

각 LangGraph thread는 시작 시점의 Plugin version snapshot을 사용한다. 실행 도중 Plugin 설정이 변경되어도 진행 중인 thread는 기존 버전을 유지한다.

```python
plugin_snapshot = {
    "browser": "1.0.0",
    "notion": "1.2.0",
    "gmail": "2.1.0",
}
```

checkpoint에는 다음 정보를 저장한다.

- tenant/user 식별자
- 활성 Plugin id와 version
- capability hash
- 권한 정책 버전
- browser session id

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

plugin_permissions
- plugin_id
- tool_name
- scope
- risk_level
- approval_required

plugin_runs
- run_id
- thread_id
- tenant_id
- user_id
- plugin_id
- plugin_version
- tool_name
- status
- redacted_input_jsonb
- redacted_output_jsonb
- created_at
```

`manifest_jsonb`와 `config_jsonb`는 확장성을 위해 사용한다. 사용자 권한, version pin, Tool allowlist처럼 조회 빈도가 높은 필드는 JSONB 안에만 숨기지 않는다.

## 5. 내부 Resolver API

Agent가 PostgreSQL을 직접 조회하지 않도록 내부 Repository와 Resolver를 둔다.

```python
@dataclass
class AgentCapabilities:
    skills: list[SkillSource]
    tools: list[BaseTool]
    plugin_snapshot: dict[str, str]
    policy: PluginPolicy


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

### 6.1 초기 권장 방식: Agent Factory

세션이 시작될 때 활성 Plugin의 Tool과 Skill을 합쳐 Agent를 만든다.

```python
async def build_agent(context: RuntimeContext):
    capabilities = await resolver.resolve_agent_capabilities(
        user_id=context.user_id,
        tenant_id=context.tenant_id,
        thread_id=context.thread_id,
    )

    return create_deep_agent(
        model=model,
        skills=materialize_skill_files(capabilities.skills),
        tools=[
            *core_browser_tools,
            *capabilities.tools,
        ],
        middleware=[
            PluginPolicyMiddleware(capabilities.policy),
            AuditMiddleware(capabilities.plugin_snapshot),
        ],
        checkpointer=checkpointer,
    )
```

Agent cache를 사용할 경우 다음 값을 cache key에 포함한다.

```text
tenant_id
plugin_snapshot_hash
model_id
policy_version
agent_config_version
```

인증 token이나 사용자별 secret을 Agent cache에 포함하지 않는다.

### 6.2 Plugin 수가 많아질 때: On-demand activation

모든 Plugin Tool을 처음부터 모델에 노출하지 않는다.

```text
기본 Agent
├── plugin_catalog
└── activate_plugin

activate_plugin("notion")
    ↓
다음 model call부터 Notion Tool 추가
```

0.4에서 이 동작이 불안정하거나 현재 LangChain middleware API와 맞지 않으면 다음 순서로 구현한다.

1. 세션 시작 시 활성 Plugin 전체를 고정 등록
2. Plugin 수가 늘면 `plugin_dispatch` 고정 Tool을 사용
3. 이후 dynamic middleware로 전환

Raw `StateGraph`를 직접 구성할 때는 compile 이후 ToolNode의 Tool 목록이 자동 변경된다고 가정하지 않는다. Plugin 조합별 재생성, middleware 기반 노출, 고정 dispatch node 중 하나를 명시적으로 선택한다.

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
- 기존 `get_user_skills()`와 backward compatibility 유지

### Phase 3. 첫 번째 Plugin

- read-only 기능을 가진 내부 Plugin 하나 선정
- HTTP runtime으로 시작
- LangChain Tool wrapper 추가
- Tool input/output schema 추가
- audit log와 timeout/retry 추가
- 0.4.x Agent Factory에 연결

### Phase 4. 멀티 Plugin과 승인

- 두 개 이상의 Plugin을 한 Agent에 등록
- Plugin 간 결과 전달 테스트
- 독립 작업의 병렬화와 의존 작업의 순차화 테스트
- 위험 Tool approval 적용
- tool collision과 tenant isolation 테스트

### Phase 5. MCP 선택 도입

- HTTP Plugin과 동일한 capability contract 유지
- MCP transport adapter 구현
- Streamable HTTP MCP server 검토
- MCP server별 license와 dependency scan
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

## 12. 완료 조건

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

### 보안

- 사용자가 권한 없는 Plugin을 활성화할 수 없다.
- Tool 실행 시점에 scope가 재검증된다.
- secret이 LLM message, Skill 파일, checkpoint에 남지 않는다.
- 다른 tenant의 Skill, Tool, browser session이 노출되지 않는다.
- 고위험 side effect는 승인 없이 실행되지 않는다.

## 13. 조사 출처

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
- [LangChain MCP Adapters](https://github.com/langchain-ai/langchain-mcp-adapters)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [LangGraph](https://github.com/langchain-ai/langgraph)
- [FastAPI](https://github.com/fastapi/fastapi)
- [PostgreSQL License](https://www.postgresql.org/about/licence/)
- [pgvector](https://github.com/pgvector/pgvector)

## 14. 추가 결정이 필요한 항목

이 문서 작성과 초기 MVP에는 추가 정보가 필요하지 않다. 구현을 시작할 때 아래 항목만 확정하면 된다.

1. 현재 설치된 정확한 `deepagents` patch version이 0.4.0인지 0.4.x인지
2. 첫 번째 Plugin의 실행 transport를 HTTP로 시작할지 MCP로 시작할지
3. Plugin scope가 user 단위인지 tenant 단위인지
4. OAuth/API credential을 어떤 secret manager에서 관리할지
5. side-effect Tool의 승인 수준과 감사 보존 기간
6. Plugin을 사내 전용으로 둘지 외부 Plugin도 허용할지

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
