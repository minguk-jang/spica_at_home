use rusqlite::{params, Connection, OptionalExtension};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::path::Path;

pub type SidecarResult<T> = Result<T, String>;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct WorkflowCard {
    pub id: i64,
    pub name: String,
    pub slug: String,
    pub description: String,
    pub domain: String,
    pub task_type: String,
    pub status: String,
    pub latest_version: i64,
    pub version_count: i64,
    pub step_count: i64,
    pub run_count: i64,
    pub update_count: i64,
    pub last_run_status: Option<String>,
    pub last_run_duration_ms: Option<i64>,
    pub last_run_at: Option<String>,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct WorkflowVersion {
    pub id: i64,
    pub version: i64,
    pub summary: String,
    pub body_md: String,
    pub input_schema: Value,
    pub output_schema: Value,
    pub status: String,
    pub created_from_run_id: Option<i64>,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct WorkflowArgument {
    pub id: i64,
    pub version_id: i64,
    pub name: String,
    pub description: String,
    pub value_type: String,
    pub required: bool,
    pub default_value: Value,
    pub validation: Value,
    pub examples: Value,
    pub is_dynamic: bool,
    pub order_index: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct WorkflowStep {
    pub id: i64,
    pub version_id: i64,
    pub order_index: i64,
    pub name: String,
    pub description: String,
    pub step_type: String,
    pub handler_ref: Option<String>,
    pub action: Value,
    pub argument_bindings: Value,
    pub assertions: Value,
    pub fallback_policy: Value,
    pub update_policy: Value,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct WorkflowResource {
    pub id: i64,
    pub version_id: i64,
    pub resource_type: String,
    pub name: String,
    pub description: String,
    pub content_json: Value,
    pub content_text: String,
    pub load_when: Value,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct WorkflowHandler {
    pub id: i64,
    pub name: String,
    pub description: String,
    pub module: String,
    pub function: String,
    pub input_schema: Value,
    pub output_schema: Value,
    pub allowed_domains: Value,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct WorkflowRun {
    pub id: i64,
    pub version_id: i64,
    pub user_request: String,
    pub input: Value,
    pub status: String,
    pub llm_used: bool,
    pub started_at: String,
    pub finished_at: Option<String>,
    pub duration_ms: Option<i64>,
    pub output: Value,
    pub report_path: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct StepRun {
    pub id: i64,
    pub run_id: i64,
    pub step_id: i64,
    pub status: String,
    pub input: Value,
    pub output: Value,
    pub evidence: Value,
    pub error: Value,
    pub started_at: String,
    pub finished_at: Option<String>,
    pub duration_ms: Option<i64>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct UpdateEvent {
    pub id: i64,
    pub from_version_id: Option<i64>,
    pub to_version_id: Option<i64>,
    pub run_id: Option<i64>,
    pub update_type: String,
    pub reason: String,
    pub diff: Value,
    pub approved_by: Option<String>,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct WorkflowUpdateProposal {
    pub id: i64,
    pub skill_id: i64,
    pub base_version_id: i64,
    pub proposed_version: i64,
    pub instruction: String,
    pub discovery_provider: String,
    pub synthesizer_provider: String,
    pub synthesizer_model: String,
    pub status: String,
    pub proposed_workflow: Value,
    pub diff: Value,
    pub evidence: Value,
    pub synthesis_duration_ms: Option<i64>,
    pub error: Value,
    pub applied_version_id: Option<i64>,
    pub approved_by: Option<String>,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct WorkflowDetail {
    pub workflow: WorkflowCard,
    pub versions: Vec<WorkflowVersion>,
    pub arguments: Vec<WorkflowArgument>,
    pub steps: Vec<WorkflowStep>,
    pub resources: Vec<WorkflowResource>,
    pub handlers: Vec<WorkflowHandler>,
    pub runs: Vec<WorkflowRun>,
    pub step_runs: Vec<StepRun>,
    pub update_events: Vec<UpdateEvent>,
    pub proposals: Vec<WorkflowUpdateProposal>,
}

pub fn list_workflows(db_path: &Path) -> SidecarResult<Vec<WorkflowCard>> {
    let conn = connect(db_path)?;
    let mut stmt = conn
        .prepare(
            r#"
            select
                s.id,
                s.name,
                s.slug,
                s.description,
                s.domain,
                s.task_type,
                s.status,
                coalesce(v.version, 0) as latest_version,
                (select count(*) from workflow_skill_versions vv where vv.skill_id = s.id) as version_count,
                (select count(*) from workflow_skill_steps st where st.version_id = s.latest_version_id) as step_count,
                (select count(*) from workflow_runs r where r.skill_id = s.id) as run_count,
                (select count(*) from skill_update_events e where e.skill_id = s.id) as update_count,
                (select r.status from workflow_runs r where r.skill_id = s.id order by r.id desc limit 1) as last_run_status,
                (select r.duration_ms from workflow_runs r where r.skill_id = s.id order by r.id desc limit 1) as last_run_duration_ms,
                (select coalesce(r.finished_at, r.started_at) from workflow_runs r where r.skill_id = s.id order by r.id desc limit 1) as last_run_at,
                s.updated_at
            from workflow_skills s
            left join workflow_skill_versions v on v.id = s.latest_version_id
            order by s.updated_at desc, s.id desc
            "#,
        )
        .map_err(error_string)?;

    let rows = stmt
        .query_map([], |row| {
            Ok(WorkflowCard {
                id: row.get("id")?,
                name: row.get("name")?,
                slug: row.get("slug")?,
                description: row.get("description")?,
                domain: row.get("domain")?,
                task_type: row.get("task_type")?,
                status: row.get("status")?,
                latest_version: row.get("latest_version")?,
                version_count: row.get("version_count")?,
                step_count: row.get("step_count")?,
                run_count: row.get("run_count")?,
                update_count: row.get("update_count")?,
                last_run_status: row.get("last_run_status")?,
                last_run_duration_ms: row.get("last_run_duration_ms")?,
                last_run_at: row.get("last_run_at")?,
                updated_at: row.get("updated_at")?,
            })
        })
        .map_err(error_string)?;

    rows.collect::<Result<Vec<_>, _>>().map_err(error_string)
}

pub fn workflow_detail(db_path: &Path, workflow_id: i64) -> SidecarResult<WorkflowDetail> {
    let conn = connect(db_path)?;
    let workflow = workflow_card(&conn, workflow_id)?;
    let latest_version_id: i64 = conn
        .query_row(
            "select latest_version_id from workflow_skills where id = ?",
            params![workflow_id],
            |row| row.get(0),
        )
        .map_err(error_string)?;

    Ok(WorkflowDetail {
        workflow,
        versions: versions(&conn, workflow_id)?,
        arguments: arguments(&conn, latest_version_id)?,
        steps: steps(&conn, latest_version_id)?,
        resources: resources(&conn, latest_version_id)?,
        handlers: handlers(&conn, latest_version_id)?,
        runs: runs(&conn, workflow_id)?,
        step_runs: step_runs(&conn, workflow_id)?,
        update_events: update_events(&conn, workflow_id)?,
        proposals: proposals(&conn, workflow_id)?,
    })
}

fn connect(db_path: &Path) -> SidecarResult<Connection> {
    if !db_path.exists() {
        return Err(format!("DB path does not exist: {}", db_path.display()));
    }
    Connection::open(db_path).map_err(error_string)
}

fn workflow_card(conn: &Connection, workflow_id: i64) -> SidecarResult<WorkflowCard> {
    conn.query_row(
        r#"
        select
            s.id,
            s.name,
            s.slug,
            s.description,
            s.domain,
            s.task_type,
            s.status,
            coalesce(v.version, 0) as latest_version,
            (select count(*) from workflow_skill_versions vv where vv.skill_id = s.id) as version_count,
            (select count(*) from workflow_skill_steps st where st.version_id = s.latest_version_id) as step_count,
            (select count(*) from workflow_runs r where r.skill_id = s.id) as run_count,
            (select count(*) from skill_update_events e where e.skill_id = s.id) as update_count,
            (select r.status from workflow_runs r where r.skill_id = s.id order by r.id desc limit 1) as last_run_status,
            (select r.duration_ms from workflow_runs r where r.skill_id = s.id order by r.id desc limit 1) as last_run_duration_ms,
            (select coalesce(r.finished_at, r.started_at) from workflow_runs r where r.skill_id = s.id order by r.id desc limit 1) as last_run_at,
            s.updated_at
        from workflow_skills s
        left join workflow_skill_versions v on v.id = s.latest_version_id
        where s.id = ?
        "#,
        params![workflow_id],
        |row| {
            Ok(WorkflowCard {
                id: row.get("id")?,
                name: row.get("name")?,
                slug: row.get("slug")?,
                description: row.get("description")?,
                domain: row.get("domain")?,
                task_type: row.get("task_type")?,
                status: row.get("status")?,
                latest_version: row.get("latest_version")?,
                version_count: row.get("version_count")?,
                step_count: row.get("step_count")?,
                run_count: row.get("run_count")?,
                update_count: row.get("update_count")?,
                last_run_status: row.get("last_run_status")?,
                last_run_duration_ms: row.get("last_run_duration_ms")?,
                last_run_at: row.get("last_run_at")?,
                updated_at: row.get("updated_at")?,
            })
        },
    )
    .optional()
    .map_err(error_string)?
    .ok_or_else(|| format!("workflow not found: {workflow_id}"))
}

fn versions(conn: &Connection, workflow_id: i64) -> SidecarResult<Vec<WorkflowVersion>> {
    let mut stmt = conn
        .prepare(
            r#"
            select id, version, summary, input_schema_json, output_schema_json, body_md,
                   status, created_from_run_id, created_at
            from workflow_skill_versions
            where skill_id = ?
            order by version desc
            "#,
        )
        .map_err(error_string)?;
    let rows = stmt
        .query_map(params![workflow_id], |row| {
            Ok(WorkflowVersion {
                id: row.get("id")?,
                version: row.get("version")?,
                summary: row.get("summary")?,
                input_schema: parse_json_text(row.get::<_, String>("input_schema_json")?),
                output_schema: parse_json_text(row.get::<_, String>("output_schema_json")?),
                body_md: row.get("body_md")?,
                status: row.get("status")?,
                created_from_run_id: row.get("created_from_run_id")?,
                created_at: row.get("created_at")?,
            })
        })
        .map_err(error_string)?;
    rows.collect::<Result<Vec<_>, _>>().map_err(error_string)
}

fn arguments(conn: &Connection, version_id: i64) -> SidecarResult<Vec<WorkflowArgument>> {
    let mut stmt = conn
        .prepare(
            r#"
            select id, version_id, name, description, type, required, default_value_json,
                   validation_json, examples_json, is_dynamic, order_index
            from workflow_skill_arguments
            where version_id = ?
            order by order_index
            "#,
        )
        .map_err(error_string)?;
    let rows = stmt
        .query_map(params![version_id], |row| {
            Ok(WorkflowArgument {
                id: row.get("id")?,
                version_id: row.get("version_id")?,
                name: row.get("name")?,
                description: row.get("description")?,
                value_type: row.get("type")?,
                required: row.get::<_, i64>("required")? != 0,
                default_value: parse_optional_json_text(row.get("default_value_json")?),
                validation: parse_json_text(row.get::<_, String>("validation_json")?),
                examples: parse_json_text(row.get::<_, String>("examples_json")?),
                is_dynamic: row.get::<_, i64>("is_dynamic")? != 0,
                order_index: row.get("order_index")?,
            })
        })
        .map_err(error_string)?;
    rows.collect::<Result<Vec<_>, _>>().map_err(error_string)
}

fn steps(conn: &Connection, version_id: i64) -> SidecarResult<Vec<WorkflowStep>> {
    let mut stmt = conn
        .prepare(
            r#"
            select id, version_id, order_index, name, description, step_type, handler_ref,
                   action_json, argument_bindings_json, assertions_json,
                   fallback_policy_json, update_policy_json
            from workflow_skill_steps
            where version_id = ?
            order by order_index
            "#,
        )
        .map_err(error_string)?;
    let rows = stmt
        .query_map(params![version_id], |row| {
            Ok(WorkflowStep {
                id: row.get("id")?,
                version_id: row.get("version_id")?,
                order_index: row.get("order_index")?,
                name: row.get("name")?,
                description: row.get("description")?,
                step_type: row.get("step_type")?,
                handler_ref: row.get("handler_ref")?,
                action: parse_json_text(row.get::<_, String>("action_json")?),
                argument_bindings: parse_json_text(row.get::<_, String>("argument_bindings_json")?),
                assertions: parse_json_text(row.get::<_, String>("assertions_json")?),
                fallback_policy: parse_json_text(row.get::<_, String>("fallback_policy_json")?),
                update_policy: parse_json_text(row.get::<_, String>("update_policy_json")?),
            })
        })
        .map_err(error_string)?;
    rows.collect::<Result<Vec<_>, _>>().map_err(error_string)
}

fn resources(conn: &Connection, version_id: i64) -> SidecarResult<Vec<WorkflowResource>> {
    let mut stmt = conn
        .prepare(
            r#"
            select id, version_id, resource_type, name, description, content_json, content_text, load_when_json
            from workflow_skill_resources
            where version_id = ?
            order by id
            "#,
        )
        .map_err(error_string)?;
    let rows = stmt
        .query_map(params![version_id], |row| {
            Ok(WorkflowResource {
                id: row.get("id")?,
                version_id: row.get("version_id")?,
                resource_type: row.get("resource_type")?,
                name: row.get("name")?,
                description: row.get("description")?,
                content_json: parse_optional_json_text(row.get("content_json")?),
                content_text: row
                    .get::<_, Option<String>>("content_text")?
                    .unwrap_or_default(),
                load_when: parse_json_text(row.get::<_, String>("load_when_json")?),
            })
        })
        .map_err(error_string)?;
    rows.collect::<Result<Vec<_>, _>>().map_err(error_string)
}

fn handlers(conn: &Connection, version_id: i64) -> SidecarResult<Vec<WorkflowHandler>> {
    if !table_exists(conn, "handler_registry")? {
        return Ok(Vec::new());
    }
    let mut stmt = conn
        .prepare(
            r#"
            select distinct h.id, h.name, h.description, h.module, h.function,
                   h.input_schema_json, h.output_schema_json, h.allowed_domains_json
            from handler_registry h
            join workflow_skill_steps s on s.handler_ref = h.name
            where s.version_id = ?
            order by h.name
            "#,
        )
        .map_err(error_string)?;
    let rows = stmt
        .query_map(params![version_id], |row| {
            Ok(WorkflowHandler {
                id: row.get("id")?,
                name: row.get("name")?,
                description: row.get("description")?,
                module: row.get("module")?,
                function: row.get("function")?,
                input_schema: parse_json_text(row.get::<_, String>("input_schema_json")?),
                output_schema: parse_json_text(row.get::<_, String>("output_schema_json")?),
                allowed_domains: parse_json_text(row.get::<_, String>("allowed_domains_json")?),
            })
        })
        .map_err(error_string)?;
    rows.collect::<Result<Vec<_>, _>>().map_err(error_string)
}

fn runs(conn: &Connection, workflow_id: i64) -> SidecarResult<Vec<WorkflowRun>> {
    let mut stmt = conn
        .prepare(
            r#"
            select id, version_id, user_request, input_json, status, llm_used, started_at,
                   finished_at, duration_ms, output_json, report_path
            from workflow_runs
            where skill_id = ?
            order by id desc
            limit 100
            "#,
        )
        .map_err(error_string)?;
    let rows = stmt
        .query_map(params![workflow_id], |row| {
            Ok(WorkflowRun {
                id: row.get("id")?,
                version_id: row.get("version_id")?,
                user_request: row.get("user_request")?,
                input: parse_json_text(row.get::<_, String>("input_json")?),
                status: row.get("status")?,
                llm_used: row.get::<_, i64>("llm_used")? != 0,
                started_at: row.get("started_at")?,
                finished_at: row.get("finished_at")?,
                duration_ms: row.get("duration_ms")?,
                output: parse_optional_json_text(row.get("output_json")?),
                report_path: row.get("report_path")?,
            })
        })
        .map_err(error_string)?;
    rows.collect::<Result<Vec<_>, _>>().map_err(error_string)
}

fn step_runs(conn: &Connection, workflow_id: i64) -> SidecarResult<Vec<StepRun>> {
    let mut stmt = conn
        .prepare(
            r#"
            select sr.id, sr.run_id, sr.step_id, sr.status, sr.input_json, sr.output_json,
                   sr.evidence_json, sr.error_json, sr.started_at, sr.finished_at, sr.duration_ms
            from step_runs sr
            join workflow_runs wr on wr.id = sr.run_id
            where wr.skill_id = ?
            order by sr.id desc
            limit 300
            "#,
        )
        .map_err(error_string)?;
    let rows = stmt
        .query_map(params![workflow_id], |row| {
            Ok(StepRun {
                id: row.get("id")?,
                run_id: row.get("run_id")?,
                step_id: row.get("step_id")?,
                status: row.get("status")?,
                input: parse_json_text(row.get::<_, String>("input_json")?),
                output: parse_optional_json_text(row.get("output_json")?),
                evidence: parse_optional_json_text(row.get("evidence_json")?),
                error: parse_optional_json_text(row.get("error_json")?),
                started_at: row.get("started_at")?,
                finished_at: row.get("finished_at")?,
                duration_ms: row.get("duration_ms")?,
            })
        })
        .map_err(error_string)?;
    rows.collect::<Result<Vec<_>, _>>().map_err(error_string)
}

fn update_events(conn: &Connection, workflow_id: i64) -> SidecarResult<Vec<UpdateEvent>> {
    let mut stmt = conn
        .prepare(
            r#"
            select id, from_version_id, to_version_id, run_id, update_type, reason,
                   diff_json, approved_by, created_at
            from skill_update_events
            where skill_id = ?
            order by id desc
            "#,
        )
        .map_err(error_string)?;
    let rows = stmt
        .query_map(params![workflow_id], |row| {
            Ok(UpdateEvent {
                id: row.get("id")?,
                from_version_id: row.get("from_version_id")?,
                to_version_id: row.get("to_version_id")?,
                run_id: row.get("run_id")?,
                update_type: row.get("update_type")?,
                reason: row.get("reason")?,
                diff: parse_json_text(row.get::<_, String>("diff_json")?),
                approved_by: row.get("approved_by")?,
                created_at: row.get("created_at")?,
            })
        })
        .map_err(error_string)?;
    rows.collect::<Result<Vec<_>, _>>().map_err(error_string)
}

fn proposals(conn: &Connection, workflow_id: i64) -> SidecarResult<Vec<WorkflowUpdateProposal>> {
    if !table_exists(conn, "workflow_update_proposals")? {
        return Ok(Vec::new());
    }
    let mut stmt = conn
        .prepare(
            r#"
            select id, skill_id, base_version_id, proposed_version, instruction,
                   discovery_provider, synthesizer_provider, synthesizer_model, status,
                   proposed_workflow_json, diff_json, evidence_json, synthesis_duration_ms,
                   error_json, applied_version_id, approved_by, created_at, updated_at
            from workflow_update_proposals
            where skill_id = ?
            order by id desc
            limit 50
            "#,
        )
        .map_err(error_string)?;
    let rows = stmt
        .query_map(params![workflow_id], |row| {
            Ok(WorkflowUpdateProposal {
                id: row.get("id")?,
                skill_id: row.get("skill_id")?,
                base_version_id: row.get("base_version_id")?,
                proposed_version: row.get("proposed_version")?,
                instruction: row.get("instruction")?,
                discovery_provider: row.get("discovery_provider")?,
                synthesizer_provider: row.get("synthesizer_provider")?,
                synthesizer_model: row.get("synthesizer_model")?,
                status: row.get("status")?,
                proposed_workflow: parse_json_text(row.get::<_, String>("proposed_workflow_json")?),
                diff: parse_json_text(row.get::<_, String>("diff_json")?),
                evidence: parse_json_text(row.get::<_, String>("evidence_json")?),
                synthesis_duration_ms: row.get("synthesis_duration_ms")?,
                error: parse_optional_json_text(row.get("error_json")?),
                applied_version_id: row.get("applied_version_id")?,
                approved_by: row.get("approved_by")?,
                created_at: row.get("created_at")?,
                updated_at: row.get("updated_at")?,
            })
        })
        .map_err(error_string)?;
    rows.collect::<Result<Vec<_>, _>>().map_err(error_string)
}

fn table_exists(conn: &Connection, table_name: &str) -> SidecarResult<bool> {
    conn.query_row(
        "select exists(select 1 from sqlite_master where type = 'table' and name = ?)",
        params![table_name],
        |row| row.get::<_, i64>(0),
    )
    .map(|value| value != 0)
    .map_err(error_string)
}

fn parse_json_text(raw: String) -> Value {
    serde_json::from_str(&raw).unwrap_or_else(|_| Value::String(raw))
}

fn parse_optional_json_text(raw: Option<String>) -> Value {
    raw.map(parse_json_text).unwrap_or(Value::Null)
}

fn error_string(error: impl ToString) -> String {
    error.to_string()
}

#[cfg(test)]
mod tests {
    use rusqlite::Connection;
    use tempfile::tempdir;

    fn create_fixture_db(conn: &Connection) {
        conn.execute_batch(
            r#"
            create table workflow_skills (
                id integer primary key,
                name text not null,
                slug text not null,
                description text not null,
                domain text not null,
                task_type text not null,
                status text not null,
                latest_version_id integer,
                created_at text not null,
                updated_at text not null
            );
            create table workflow_skill_versions (
                id integer primary key,
                skill_id integer not null,
                version integer not null,
                summary text not null,
                input_schema_json text not null,
                output_schema_json text not null,
                body_md text not null,
                load_policy_json text not null,
                status text not null,
                created_from_run_id integer,
                created_at text not null
            );
            create table workflow_skill_arguments (
                id integer primary key,
                version_id integer not null,
                name text not null,
                description text not null,
                type text not null,
                required integer not null,
                default_value_json text,
                validation_json text not null,
                examples_json text not null,
                is_dynamic integer not null,
                order_index integer not null
            );
            create table workflow_skill_steps (
                id integer primary key,
                version_id integer not null,
                order_index integer not null,
                name text not null,
                description text not null,
                step_type text not null,
                handler_ref text,
                action_json text not null,
                argument_bindings_json text not null,
                assertions_json text not null,
                fallback_policy_json text not null,
                update_policy_json text not null
            );
            create table workflow_skill_resources (
                id integer primary key,
                version_id integer not null,
                resource_type text not null,
                name text not null,
                description text not null,
                content_json text,
                content_text text,
                load_when_json text not null
            );
            create table handler_registry (
                id integer primary key,
                name text not null unique,
                description text not null,
                module text not null,
                function text not null,
                input_schema_json text not null,
                output_schema_json text not null,
                allowed_domains_json text not null
            );
            create table workflow_runs (
                id integer primary key,
                skill_id integer not null,
                version_id integer not null,
                user_request text not null,
                input_json text not null,
                status text not null,
                llm_used integer not null,
                llm_reason text,
                started_at text not null,
                finished_at text,
                duration_ms integer,
                output_json text,
                report_path text
            );
            create table step_runs (
                id integer primary key,
                run_id integer not null,
                step_id integer not null,
                status text not null,
                input_json text not null,
                output_json text,
                evidence_json text,
                error_json text,
                started_at text not null,
                finished_at text,
                duration_ms integer
            );
            create table skill_update_events (
                id integer primary key,
                skill_id integer not null,
                from_version_id integer,
                to_version_id integer,
                run_id integer,
                update_type text not null,
                reason text not null,
                diff_json text not null,
                approved_by text,
                created_at text not null
            );
            create table workflow_update_proposals (
                id integer primary key,
                skill_id integer not null,
                base_version_id integer not null,
                proposed_version integer not null,
                instruction text not null,
                discovery_provider text not null,
                synthesizer_provider text not null,
                synthesizer_model text not null,
                status text not null,
                proposed_workflow_json text not null,
                diff_json text not null,
                evidence_json text not null,
                synthesis_duration_ms integer,
                error_json text,
                applied_version_id integer,
                approved_by text,
                created_at text not null,
                updated_at text not null
            );

            insert into workflow_skills values
              (1, 'naver_stock_report', 'naver-stock-report', 'Naver stock report', 'naver.com', 'stock_report', 'stable', 2, '2026-06-09 00:00:00', '2026-06-09 00:02:00');
            insert into workflow_skill_versions values
              (1, 1, 1, 'Initial version', '{"company_name":{"type":"string"}}', '{"report_text":"string"}', 'Load this workflow.', '{"metadata_first":true}', 'stable', null, '2026-06-09 00:00:00'),
              (2, 1, 2, 'Updated version', '{"company_name":{"type":"string"}}', '{"report_text":"string"}', 'Load this workflow. Update v2.', '{"metadata_first":true}', 'stable', 10, '2026-06-09 00:02:00');
            insert into workflow_skill_arguments values
              (1, 2, 'company_name', '검색할 기업명', 'string', 1, null, '{}', '["삼성전자"]', 1, 0);
            insert into workflow_skill_steps values
              (1, 2, 0, 'open_search', 'Open search page', 'goto', null, '{"url_template":"https://search.naver.com/search.naver?query={{company_name}} 주가"}', '{}', '{"url_contains":"search.naver.com"}', '{"retry":0}', '{"record_update_event":true}'),
              (2, 2, 1, 'extract_stock_card', 'Extract quote fields', 'run_handler', 'naver_stock.extract_stock_card', '{"handler":"naver_stock.extract_stock_card"}', '{}', '{"required_output":["company_name","current_price"]}', '{"retry":0}', '{"record_update_event":true}');
            insert into workflow_skill_resources values
              (1, 2, 'report_template', 'stock_report_markdown', 'Report template', null, '# {{company_name}} 주가 리포트', '{"step":"render"}');
            insert into handler_registry values
              (1, 'naver_stock.extract_stock_card', 'Extract stock quote fields from Naver stock search text.', 'webworkflows.handlers.naver_stock', 'extract_stock_card', '{"page_text":"string"}', '{"current_price":"integer"}', '["naver.com"]');
            insert into workflow_runs values
              (10, 1, 2, '삼성전자 주가 리포트', '{"company_name":"삼성전자"}', 'succeeded', 0, null, '2026-06-09 00:03:00', '2026-06-09 00:03:01', 12, '{"report_text":"ok"}', '/tmp/report.md');
            insert into step_runs values
              (20, 10, 1, 'succeeded', '{}', '{}', '{"url":"https://search.naver.com"}', null, '2026-06-09 00:03:00', '2026-06-09 00:03:01', 4);
            insert into skill_update_events values
              (30, 1, 1, 2, 10, 'new_example', 'Observed request.', '{"example":"삼성전자"}', 'system', '2026-06-09 00:04:00');
            insert into workflow_update_proposals values
              (40, 1, 2, 3, 'Add valuation section.', 'none', 'agent_json', 'test-model',
               'draft', '{"skill_name":"naver_stock_report"}', '{"resources_changed":["stock_report_markdown"]}',
               '{"instruction":"Add valuation section."}', 9, null, null, null,
               '2026-06-09 00:05:00', '2026-06-09 00:05:00');
            "#,
        )
        .expect("fixture schema");
    }

    #[test]
    fn lists_workflow_cards_from_webmcp_db() {
        let temp = tempdir().expect("tempdir");
        let db_path = temp.path().join("workflows.sqlite");
        let conn = Connection::open(&db_path).expect("open db");
        create_fixture_db(&conn);
        drop(conn);

        let workflows = super::list_workflows(&db_path).expect("workflows");

        assert_eq!(1, workflows.len());
        assert_eq!("naver_stock_report", workflows[0].name);
        assert_eq!(2, workflows[0].latest_version);
        assert_eq!(1, workflows[0].run_count);
        assert_eq!(12, workflows[0].last_run_duration_ms.unwrap());
    }

    #[test]
    fn loads_workflow_detail_with_versions_steps_resources_runs_and_updates() {
        let temp = tempdir().expect("tempdir");
        let db_path = temp.path().join("workflows.sqlite");
        let conn = Connection::open(&db_path).expect("open db");
        create_fixture_db(&conn);
        drop(conn);

        let detail = super::workflow_detail(&db_path, 1).expect("detail");

        assert_eq!("naver_stock_report", detail.workflow.name);
        assert_eq!(2, detail.versions.len());
        assert_eq!("company_name", detail.arguments[0].name);
        assert_eq!("open_search", detail.steps[0].name);
        assert_eq!("naver_stock.extract_stock_card", detail.handlers[0].name);
        assert_eq!(
            "webworkflows.handlers.naver_stock",
            detail.handlers[0].module
        );
        assert_eq!("stock_report_markdown", detail.resources[0].name);
        assert_eq!("succeeded", detail.runs[0].status);
        assert_eq!("new_example", detail.update_events[0].update_type);
        assert_eq!("draft", detail.proposals[0].status);
        assert_eq!(3, detail.proposals[0].proposed_version);
    }
}
