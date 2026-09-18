---
name: remotion-best-practices
description: Implement or debug Remotion components and rendering, or change Remotion dependencies.
metadata:
  version: "4.0.521"
---

## Scope in this repository

Use this skill for engine code, rendering issues, and Remotion dependencies. Ordinary Shorts production and edits to script, footage, sound, or `project.json` use the existing [editing workflow](../../../docs/EDITING.md) and [CLI](../../../README.md).

The canonical project is `projects/<case>/project.json`; the shared renderer is `remotion/`. A new video uses that renderer. Preserve user edits and keep generated timing in `work/` derived from the project.

The user's requested endpoint and repository approval rules govern completion. Bundled references also describe standalone videos; their Studio preview endpoint and render-only-on-request advice do not add an approval gate to already authorized production or fixture validation.

## Read the relevant reference

Choose the reference for the implementation being changed; follow further links only when needed. Check the official API documentation for the API in use.

| Task | Reference |
| --- | --- |
| React composition, timing, media, effects | [Markup](./remotion-markup/REFERENCE.md) |
| Caption rendering or measured timestamps | [Captions](./remotion-captions/REFERENCE.md) |
| Renderer options and render failures | [Rendering](./remotion-render/REFERENCE.md) |
| Launch or configure Studio when needed | [Studio](./remotion-studio/REFERENCE.md) |
| Add Studio editing controls | [Interactivity](./remotion-interactivity/REFERENCE.md) |
| Browser-side media processing | [Multimedia](./remotion-multimedia/REFERENCE.md) |
| Look up current Remotion APIs | [Docs](./remotion-docs/REFERENCE.md) |
| Requested dependency or skill upgrade | [Upgrade](./remotion-upgrade/REFERENCE.md) |
| Explicitly requested map or geographic visualization | [Maps](./remotion-maps/REFERENCE.md) |
| Requested Player, hosted renderer, or SaaS | [SaaS](./remotion-saas/REFERENCE.md) |
| Explicitly requested standalone Remotion project or new composition outside this engine | [Create](./remotion-create/REFERENCE.md) |
