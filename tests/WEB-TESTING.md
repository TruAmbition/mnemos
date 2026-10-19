# Web verification

Run the dependency-free browser-helper tests with:

```sh
node --test tests/web.test.cjs
```

The suite exercises the actual application's pure helpers using Node's built-in test runner and VM. Minimal DOM stubs allow event registration only; these are not simulated rendering tests.

Coverage includes safe Markdown rendering and link protocols, calendar dates, JSON and Markdown import parsing, draft status and identity restrictions on imported data, source preservation, keyword ranking, and context character budgets.

Manual browser checks during initial implementation covered document creation and saving, recall, workflow-plan display, and a real local backup. **The native file chooser and complete browser file-import interaction remain unverified end to end:** browser automation did not produce a file-chooser event. Parser tests cover the import formats and normalization independently. To check the full interaction manually, open Capture knowledge, choose Import file, select a Markdown or JSON export, verify the populated fields and draft status, and save. Importing alone must not save a document.

## Guided tutorial

Run `node --test tests/*.test.cjs` to include tutorial progression, duplicate completion, skipped chapters, replay, corrupt state, workspace/role storage keys, and capability-aware feature links. The tutorial module has no API client and receives only public capability flags and a navigation callback. Use the browser to check the full 28-step progression and examples, pause/reload/resume, completed-tour chapter replay, full reset, keyboard activation, and reader restrictions. Sample interactions must not create notes or modify configuration.
