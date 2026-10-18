# Workflow contract

Workflow JSON lives in the dedicated vault's `Workflows/` directory. Use an ID and filename that do not collide with an existing workflow. This is a planning artifact, not executable code.

```json
{
  "id": "example-procedure",
  "title": "Repeat a documented procedure",
  "description": "Validate inputs, perform the bounded task, and verify its outcome.",
  "status": "draft",
  "steps": [
    {
      "id": "prepare",
      "title": "Validate required inputs",
      "document_id": "actual-source-document-id",
      "depends_on": [],
      "requires_approval": false
    },
    {
      "id": "perform",
      "title": "Perform the authorized operation",
      "document_id": "another-actual-source-document-id",
      "depends_on": ["prepare"],
      "requires_approval": true
    }
  ]
}
```

Replace illustrative IDs with real source documents. Each dependency names a step in the same workflow. Never rely on the order of the JSON array to express a dependency. `requires_approval` creates an explicit checkpoint; it is not an authorization credential.

Validate and obtain a plan from the source directory:

This command uses the checkout's selected default workspace. Add an explicit `--data` path only to pin a different intended, authorized workspace.

```sh
python3 -m mnemos workflow-plan --id example-procedure
```

The planner resolves source documents and checks graph validity. Retain returned source revisions when recording the plan. Revalidate against current documents before execution. The CLI does not schedule, run, or roll back the tasks.

An execution record should capture the workflow ID, source IDs and revisions, actual inputs without secrets, per-step state, start/end times when available, observed verification, and recovery outcome. Use a work log in the vault or an explicitly selected task tracking system. Planning success and execution success are separate results.
