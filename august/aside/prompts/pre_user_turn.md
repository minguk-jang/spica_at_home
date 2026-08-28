# Observed pre-user-turn input

## Finding

The inspected database schema has no `pre_user_turn` column, and no dedicated file or literal `pre_user_turn` identifier was found in the inspected `.aside` data or installed Aside binaries.

Therefore, this repository documents the observed pre-user-turn input rather than claiming a named internal prompt implementation.

## Observed record

In session run `113`, the `user_message` array contained a `system-message` item before the first user message:

```json
{
  "role": "system-message",
  "content": "Relevant skill docs are available. Read with read_file if needed:\n- aside: /Users/mingukjang/.aside/u/0/skills/builtin/aside/SKILL.md",
  "kind": "site_skill",
  "metadata": {},
  "timestamp": 1787920381234
}
```

The same prelude is also present in the first entry of the session transcript. Later runs in this session contain user messages without another persisted `pre_user_turn` field.

## Interpretation boundary

- Evidence: a per-run `system-message` skill prelude was recorded before the first user turn.
- Not established: whether Aside has a separate runtime template named `pre_user_turn`, how it is assembled internally, or whether an equivalent prelude is added for every task but omitted from persisted run data.

## Evidence locations

- `/Users/mingukjang/.aside/u/0/state.db`, table `session_runs`, column `user_message`, run `113`
- `/Users/mingukjang/.aside/u/0/sessions/2026-08-28_VqF3D5MdtDRATrHH/messages.jsonl`
