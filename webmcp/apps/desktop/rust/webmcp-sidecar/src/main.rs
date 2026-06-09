use std::env;
use std::path::PathBuf;
use webmcp_sidecar::{list_workflows, workflow_detail};

fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), String> {
    let args: Vec<String> = env::args().collect();
    let command = args.get(1).ok_or_else(usage)?;

    match command.as_str() {
        "list-workflows" => {
            let db = required_arg(&args, "--db")?;
            let workflows = list_workflows(&PathBuf::from(db))?;
            print_json(&workflows)
        }
        "workflow-detail" => {
            let db = required_arg(&args, "--db")?;
            let workflow_id = required_arg(&args, "--workflow-id")?
                .parse::<i64>()
                .map_err(|error| format!("invalid --workflow-id: {error}"))?;
            let detail = workflow_detail(&PathBuf::from(db), workflow_id)?;
            print_json(&detail)
        }
        _ => Err(usage()),
    }
}

fn required_arg(args: &[String], name: &str) -> Result<String, String> {
    args.windows(2)
        .find_map(|pair| (pair[0] == name).then(|| pair[1].clone()))
        .ok_or_else(|| format!("missing {name}\n{}", usage()))
}

fn print_json<T: serde::Serialize>(value: &T) -> Result<(), String> {
    let raw = serde_json::to_string_pretty(value).map_err(|error| error.to_string())?;
    println!("{raw}");
    Ok(())
}

fn usage() -> String {
    "usage: webmcp-sidecar <list-workflows|workflow-detail> --db <path> [--workflow-id <id>]"
        .to_string()
}
