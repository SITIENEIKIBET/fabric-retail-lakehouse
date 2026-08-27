# Architecture Decision Records

## ADR-001: Why Microsoft Fabric Lakehouse (not Warehouse) for Project 2

**Context:**
We need a storage/compute layer supporting both PySpark-based transformations
and SQL-based BI consumption, ingesting from Postgres, REST API, CSV, and JSON sources.

**Decision:**
Use Fabric Lakehouse with OneLake/Delta as the primary storage format.

**Alternatives considered:**
- Fabric Warehouse (T-SQL only, no native Spark access)
- Azure Databricks + separate Power BI connection (adds a second platform,
  duplicates what Fabric already provides for this project's scope)

**Trade-offs:**
- Lakehouse gives us dual access (Spark notebooks + SQL analytics endpoint)
  at the cost of some SQL feature parity compared to a dedicated Warehouse
  (e.g., stricter T-SQL constructs, better query optimizer for pure SQL workloads).
- Warehouse would be the better choice if the team were SQL-only with no
  Spark/Python skillset, or if strict ACID multi-table transactions across
  a fully relational model were a hard requirement.

**Consequences:**
All Bronze/Silver/Gold tables are Delta tables in OneLake. Gold layer remains
queryable via both PySpark notebooks and the SQL analytics endpoint for Power BI.

## ADR-002: Manual Fabric-to-Git Sync (instead of native Git integration)

**Context:**
Native Fabric Git integration requires either GitHub tenant-level enablement
(not available on trial capacity) or Azure DevOps (requires an Azure
subscription with card verification, unavailable in this environment).

**Decision:**
Use GitHub as the sole source-controlled repo. Sync Fabric artifacts
(notebooks, pipeline JSON) manually via export/commit after each session,
per docs/fabric-git-sync-workflow.md.

**Alternatives considered:**
- Azure DevOps native sync (blocked by card verification requirement)
- GitHub native sync (blocked by trial capacity tenant restrictions)

**Trade-offs:**
- No automatic conflict detection between Fabric and Git state — discipline
  is required to keep them in sync manually.
- Loses Fabric's built-in branching-out/workspace-per-branch capability.
- Gains full portability: this workflow works on any Fabric SKU, trial or paid.

**Consequences:**
CI/CD (GitHub Actions) will validate exported notebook/pipeline files on
push, but cannot trigger deployments *into* Fabric automatically without
the Fabric REST API (evaluated separately in the CI/CD phase).


## ADR-003: Manual Upload to Lakehouse Files (instead of On-Premises Data Gateway)

**Context:**
Fabric notebooks execute in Microsoft's cloud and cannot reach localhost
services (our Dockerized Postgres) or the local filesystem (our generated
CSV/JSON files) directly.

**Decision:**
Export local sources to flat files (CSV/Parquet/JSON) and manually upload
them to the Lakehouse's Files section in OneLake. The Bronze notebook reads
from Files, not from live source connections.

**Alternatives considered:**
- On-premises Data Gateway: the production-correct tool for this exact
  problem, but adds real setup overhead (local Windows service install,
  recovery key management) and has documented connectivity reliability
  issues specifically on trial capacity (error 9518, requiring gateway
  version downgrades to resolve per community reports).
- Exposing local Postgres publicly (e.g. via ngrok): rejected outright —
  unnecessary security exposure for a local dev database with no
  corresponding benefit for this project's goals.

**Trade-offs:**
- Manual upload means ingestion isn't "live" — each Bronze run reflects
  whatever was last exported/uploaded, not real-time source state.
- In a real production environment with a paid Fabric capacity, we would
  use the On-premises Data Gateway or Fabric Mirroring for SQL sources
  instead — this is explicitly a trial-environment adaptation, not the
  production-recommended pattern.

**Consequences:**
The Bronze notebook's ingestion logic (retry, audit columns, schema
handling) is written identically to how it would be against a live
gateway-based source — only the entry point (Files vs. JDBC-over-gateway)
differs. This keeps the pattern honestly transferable to a real Fabric
capacity, and this ADR gives us the "how would this change in production"
answer ready for interviews.

## ADR-004: Quarantine Instead of Drop for Data Quality Violations

**Context:**
Multiple Bronze sources contain deliberate data quality issues (duplicate
customers, broken foreign key references, negative business-impossible
values, stale references). A decision was needed on how Silver handles
each violation type.

**Decision:**
Split violations into two handling strategies:
- **Quarantine** (structural/referential violations, business-rule
  violations): row is excluded from the Silver table but preserved in a
  parallel `silver_quarantine_<table>` table with a `quarantine_reason`.
- **Flag** (soft/non-fatal issues like missing email, missing rating,
  unparseable date): row is kept in Silver with a boolean flag column
  (e.g. `has_missing_email`).

**Alternatives considered:**
- Drop bad rows silently — rejected, since it destroys the ability to
  investigate or report on data quality issues after the fact.
- Reject the entire batch on any violation — rejected as too brittle for
  a source that will always have some noise (e.g. legacy CSV exports).

**Trade-offs:**
- Quarantine tables add storage and pipeline complexity versus a simple
  filter-and-drop approach.
- Requires ongoing judgment calls about which issues are quarantine-worthy
  versus flag-worthy — this project's rule of thumb: quarantine when the
  row would corrupt downstream joins/aggregates (broken FK, impossible
  values); flag when the row is still usable on its own.

**Consequences:**
Every Silver table transformation now logs into `silver_dq_log`, giving
a queryable history of ingestion health per run — the foundation for the
observability dashboards planned in Project 5.

## ADR-006: SCD Type 2 via Delta MERGE-style Update + Append

**Context:**
`dim_customers` needed to track historical changes (e.g. city updates) so
that "what did this customer look like at order time" remains answerable,
per the project's SCD2 requirement.

**Decision:**
Implement SCD2 as a two-step Delta operation: (1) `DeltaTable.update()` to
expire (`is_current=False`, set `effective_end_date`) any existing current
row whose attributes changed, followed by (2) an `append` of new current
rows for both changed and brand-new customers.

**Alternatives considered:**
- True Delta `MERGE INTO` with `WHEN MATCHED`/`WHEN NOT MATCHED` clauses:
  more idiomatic and closer to what Fabric/Databricks documentation
  typically shows; not used here mainly for pedagogical clarity of the
  update/append split, though a production version would likely
  consolidate into a single MERGE statement.

**Trade-offs:**
- Two-step approach requires careful ordering (expire before insert) and
  is more exposed to bugs like premature re-evaluation of lazy DataFrames
  against already-mutated table state (encountered and documented during
  implementation — see troubleshooting notes).
- A single `MERGE INTO` statement would be more atomic and less prone to
  this specific class of bug.

**Consequences:**
`dim_customers` now carries full version history via `customer_key`
(surrogate, unique per version) vs. `customer_id` (stable natural key).
Any fact table join must use `customer_key`, not `customer_id`, to
correctly attribute historical facts to the customer version that was
current at the time.