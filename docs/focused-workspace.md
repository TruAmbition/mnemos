# Focused workspace (0.8.1)

Mnemos is the durable documentation companion to your AI workspace. Use ChatGPT, Claude, or a local coding agent for reasoning and engineering work. Use Mnemos to find prior knowledge, review the resulting documentation, and build reusable skills. It does not embed those products' chat interfaces or replace their accounts. You can read, search, and write notes in Mnemos without an AI platform.

A typical loop is **find relevant context → work with your assistant → capture and review the result**. Local skills/MCP connections can make capture and recall available inside a compatible assistant. File handoff lets you review a context pack, attach it to your existing chat, and import its returned draft without a tunnel. These remain explicit integrations; hiding navigation does not change permissions or automatically share notes.

Keeping Mnemos independent gives the documentation one stable home when you change assistants. The direction is a smoother context handoff, rather than another place to manage chat accounts. An optional in-app model integration could be a separate future feature; this version has no built-in model or inference API configuration.

## Library and navigation

The library opens as a compact list with search, document-type and project filters, and visible draft/verified labels. Grid view remains available. The promotional banner and repeated statistics have been removed. Daily navigation is Library, Capture work, Find context, and Skills (authoring controls remain role-gated).

**Tools** contains Use with AI (the existing Cloud handoff page) and Workflows. **Manage** contains the available Projects, Connections, Backups & settings, and Workspace setup controls. A group expands automatically when you navigate into it. Getting started remains directly accessible. Existing hash links still work, and first-visit onboarding is unchanged.

Choose **Focus** in the top bar to hide navigation and the footer. **Exit focus** or Escape restores them. Focus mode lasts for the current page session and works across routes. It does not hide document status or change access permissions.

## Read and capture

Opening a document gives it a full-width reading surface with a comfortable line length. Title, summary, status, and example notices stay visible. **Document details** reveals author, dates, project, and tags. Source references and related notes remain available after the body. An identical leading Markdown title is omitted from the rendered body to avoid a duplicate; the stored file is unchanged.

Back or Escape returns to the previous page with its search and filters intact. Copy and Edit remain in the reader toolbar. The underlying page is inert while a dialog is open, and the keyboard focus loop includes the details disclosure. Escape closes a dialog before exiting page Focus mode.

Capture puts title, type, project, and the writing area first. **Summary, tags & references** holds optional metadata without removing those fields from imports or submissions. Status and Save remain visible below the editor. File import, pasted JSON, Markdown preview, draft safeguards, revision checks, and workspace-change recovery keep their existing behavior.

## Native manager

The SwiftUI dashboard emphasizes the active library and **Open Library**. File paths and Finder are under **Location & files**; service information and Stop are under **Service & installation**. A short handoff/skills section explains the relationship to the AI assistant.

Workspace keeps its setup actions visible and collapses the backup destination when updating an existing configuration. A new setup still shows backup choices. Assistants keeps status and different-workspace warnings visible; explanation and connection details expand on demand. The native manager and HTML workspace continue to share the same service and vault.
