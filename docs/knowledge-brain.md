# Knowledge brain

Open **Knowledge brain** in the browser sidebar or the native Mac app. Mnemos displays your engineering knowledge as an open network of colored orbs and documented relationships. “Brain” names the connected knowledge; the view has no anatomical outline, lobes, or hemisphere constraints.

## Color mode

The brain opens with **colors by type**. Turn on **Color by project** in the inspector to give a top-level project and its repositories, notes, workflows, and saved skills the same color. The legend updates to project names. Items assigned to several projects use **Shared across projects** in silver; items without membership use **No project assigned** in gray. Membership comes from recorded metadata, not guessed similarity. Colors are assigned from the full project catalog so filtering does not change them.

Switching colors keeps the current selection, layout, sizes, filters, zoom, and pan. Turning the switch off restores type colors. This view preference is not written to notes or Obsidian settings; opening or refreshing the graph starts in type mode. The browser, embedded Mac view, and new static-reader exports share the control.

## What the orbs mean (default type colors)

| Orb | Color | Meaning |
| --- | --- | --- |
| Project | Violet | A top-level application or system |
| Repository | Cyan | A registered local checkout |
| Built skill / skill note | Amber | A saved Mnemos skill package or a documented skill |
| Runbook | Green | A repeatable procedure |
| Troubleshooting | Coral | Symptoms, diagnosis, and fixes |
| Decision | Lavender | An implementation choice and its reasoning |
| Knowledge item | Blue | A reusable explanation |
| Context | Pale blue | A context handoff or repository snapshot |
| Flow / workflow | Peach / pink | A documented flow or registered workflow |
| Microtask | Mint | A small reusable step |
| Work log | Silver | A record of engineering work |

Projects and repositories have larger base sizes. Every orb also grows with its number of distinct connected neighbors, up to a size cap. The size slider adjusts all orbs. Size is a navigation aid, not AI confidence or an assessment of importance.

## Explore

- Search titles and summaries, or filter by project and node type.
- Select an orb or choose a name in the accessible selector. The inspector shows its actual relationships and an action to open the documentation, project, workflow, or saved skill.
- Enable **Focus on selected neighbors** to show a node and its immediate connections. Selecting another visible node moves that focus.
- Drag the background to pan; scroll or use the buttons to zoom. **Fit view** resets the viewport. Keyboard users can focus the graph and use arrows and plus/minus; each orb supports Enter/Space.
- Main project/repository labels appear by default. Hover or focus an orb for its label, or enable **Show every label**. Select **Refresh graph** after capturing notes or changing projects.
- Up to 500 matching nodes render at once. A notice reports truncation; narrow filters to reach the rest. An empty library has no invented nodes.

## Links and Obsidian

The graph resolves visible notes' Obsidian wiki links, relative Markdown note links, related-note IDs, and Mnemos source references. It also includes declared project/repository memberships and system relationships, workflow steps, and saved skill source documents. Ambiguous or missing references are skipped. Literal examples inside code or comments are not treated as links.

Connections are recorded relationships, not similarity inferred by AI. This is a separate renderer of the same vault knowledge, not an embedded copy of Obsidian's Graph view. Obsidian node positions, filters, colors, and force settings are not synchronized. Obsidian Canvas files remain separate, editable maps. [Obsidian's graph documentation](https://obsidian.md/help/plugins/graph) explains its own group colors and connectivity sizing.

## Privacy and scope

Graph reads do not modify notes, scan repository code, execute skills, or call an AI service. No tunnel is required. Existing session visibility and note privacy rules apply. Only the authenticated local owner receives registered repository and saved-build metadata. Shared readers and static exports include only the documentation and project/workflow metadata already available to them; links cannot create hidden-note placeholders. Checkout paths are omitted from graph nodes.

Saved Mnemos skill packages link back to their source notes. Installed third-party skill folders are not scanned by this graph; use the existing Skills inventory, or document a skill in the vault to include it as a note. Deleting a registry entry or filtering a node may remove it from the graph without deleting its underlying documentation.
