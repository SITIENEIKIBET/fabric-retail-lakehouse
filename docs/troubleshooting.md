## Fabric Trial Capacity: HTTP 430 TooManyRequestsForCapacity

**Symptom:** Spark cell fails with `InvalidHttpRequest [TooManyRequestsForCapacity]`,
HTTP status 430.

**Cause:** Fabric trial capacity (FT1) has very limited Spark VCores, shared
across every Spark-using item in the workspace. Idle/lingering notebook
sessions, multiple open notebook tabs, or background Lakehouse table
previews all consume capacity even when nothing looks "active."

### Immediate fix
1. Workspace → **Job management** → cancel any jobs shown as Running or
   Queued, especially ones stuck in "Starting."
2. In every open notebook, use **Stop session** (top toolbar / "..." menu)
   on any notebook not actively in use right now.
3. Close extra Fabric browser tabs (table explorer, Files view, other
   notebooks) — each holds its own session.
4. Retry the cell.
5. If still blocked: wait 5–10 minutes. Trial capacity can stay
   "overextended" for a while even after cancelling everything — there's
   no faster legitimate fix on a trial SKU.

### Prevention habit for this project
- **One notebook open at a time.** Run it fully, explicitly Stop the
  session, then move to the next notebook.
- Don't leave a Lakehouse Files/table view open in another tab while a
  notebook cell is running.
- Prefer "Run all" over manually stepping through cells with long pauses
  in between — idle time between cells still holds the session open.