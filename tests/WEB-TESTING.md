# Web verification

Run the dependency-free browser-helper tests with:

```sh
node --test tests/web.test.cjs
```

The suite exercises the actual application's pure helpers using Node's built-in test runner and VM. Minimal DOM stubs allow event registration only; these are not simulated rendering tests.

Coverage includes safe Markdown rendering and link protocols, calendar dates, JSON and Markdown import parsing, draft status and identity restrictions on imported data, source preservation, keyword ranking, and context character budgets.

Manual browser checks during initial implementation covered document creation and saving, recall, workflow-plan display, and a real local backup. **The native file chooser and complete browser file-import interaction remain unverified end to end:** browser automation did not produce a file-chooser event. Parser tests cover the import formats and normalization independently. To check the full interaction manually, open Capture knowledge, choose Import file, select a Markdown or JSON export, verify the populated fields and draft status, and save. Importing alone must not save a document.
