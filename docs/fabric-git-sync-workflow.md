# Fabric ↔ Git Manual Sync Workflow

Live Git integration is not available on this Fabric trial capacity (GitHub
requires tenant-level enablement not present on trial SKUs; Azure DevOps
requires an Azure subscription with card verification, which isn't available
in this environment). This document defines the manual workaround.

## Workflow

1. Do development work directly in the Fabric workspace (notebooks, pipelines).
2. Before ending a work session, export changed artifacts:
   - Notebooks: Fabric notebook → File → Export → select `.ipynb`
   - Pipelines: copy the pipeline JSON via Pipeline → View JSON (or the
     `Export template` option if available)
3. Save exported files into `fabric/notebooks/` or `fabric/pipelines/`
   in this repo, replacing the previous version.
4. Commit with a message describing what changed, e.g.:
   `git commit -m "sync: bronze ingestion notebook - add retry logic"`
5. Push to GitHub as normal.

## Rules

- Treat Fabric as the source of truth for *execution*; treat GitHub as the
  source of truth for *history and review*.
- Sync after every meaningful change, not just at the end of a phase —
  small frequent commits beat one large export at the end.
- Never edit exported files locally and re-upload without also making the
  same edit in Fabric — this workflow has no automatic merge; manual drift
  between the two copies is the main risk and must be avoided deliberately.