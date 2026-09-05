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

## ADR-008: Delta Lake Time Travel as a Deliberate Auditing Tool

**Context:**
Throughout Phases 7B, we used Delta time travel reactively to recover
from an accidental full-table overwrite. This ADR formalizes it as an
intentional project capability rather than treating that as a one-off fix.

**Decision:**
Use `VERSION AS OF` / `TIMESTAMP AS OF` queries against Delta tables for
auditing historical state and diffing changes over time, in addition to
the SCD2 dimension logic already handling business-facing history.

**Alternatives considered:**
- Relying solely on SCD2 for history: SCD2 captures *business* history
  (what a dimension looked like at a point in time) but not *pipeline*
  history (every write operation, including mistakes, corrections, and
  intermediate states) — time travel captures the latter, which SCD2
  cannot.

**Trade-offs:**
- Delta's transaction log grows over time; without periodic `VACUUM`,
  old file versions accumulate storage cost indefinitely. Production
  systems set a retention window (e.g. 30 days) and vacuum beyond it —
  we deliberately do NOT vacuum in this project, since we want full
  history available for demonstration purposes.

**Consequences:**
Time travel and SCD2 serve complementary, not redundant, purposes:
SCD2 answers "what did this customer look like when they placed this
order" (business-time); time travel answers "what did this entire table
look like last Tuesday, including any pipeline mistakes" (system-time).


## ADR-009: Explicit Schema Evolution via mergeSchema

**Context:**
Bronze sources can change shape over time (e.g., a new column added
upstream). Delta enforces schema matching by default, causing writes to
fail when incoming data doesn't match the target table's schema.

**Decision:**
Treat schema mismatches as a deliberate decision point, not an automatic
pass-through. Default behavior (no `mergeSchema` flag) correctly fails
loudly; evolution only happens when explicitly requested via
`option("mergeSchema", "true")`.

**Alternatives considered:**
- Always enabling `mergeSchema` by default on every write: rejected —
  this would silently accept a renamed or retyped column as if it were
  a new one, risking silent data corruption rather than a caught error.

**Trade-offs:**
- Requires a human (or an alerting mechanism) to notice the failure and
  make an explicit decision to evolve — this is a deliberate friction
  point, not an oversight.

**Consequences:**
`bronze_loyalty` now has a `referral_code` column; pre-change rows would
show null for it if this had been a partial/incremental load, correctly
representing that the field genuinely didn't exist for those records
rather than inventing a fabricated default value.


## ADR-009: Explicit Schema Evolution via mergeSchema

**Context:**
Bronze sources can change shape over time (e.g., a new column added
upstream). Delta enforces schema matching by default, causing writes to
fail when incoming data doesn't match the target table's schema.

**Decision:**
Treat schema mismatches as a deliberate decision point, not an automatic
pass-through. Default behavior (no `mergeSchema` flag) correctly fails
loudly; evolution only happens when explicitly requested via
`option("mergeSchema", "true")`.

**Alternatives considered:**
- Always enabling `mergeSchema` by default on every write: rejected —
  this would silently accept a renamed or retyped column as if it were
  a new one, risking silent data corruption rather than a caught error.

**Trade-offs:**
- Requires a human (or an alerting mechanism) to notice the failure and
  make an explicit decision to evolve — this is a deliberate friction
  point, not an oversight.

**Consequences:**
`bronze_loyalty` now has a `referral_code` column; pre-change rows would
show null for it if this had been a partial/incremental load, correctly
representing that the field genuinely didn't exist for those records
rather than inventing a fabricated default value.


## ADR-011: Wait Activities Between Pipeline Notebook Steps (Trial Capacity Mitigation)

**Context:**
Chaining 4 notebook activities in a Data Factory pipeline on Fabric trial
capacity (FT1) reliably triggers HTTP 430 TooManyRequestsForCapacity,
since each activity spins up a fresh Spark session with minimal gap
between the previous session's teardown and the next one's creation.

**Decision:**
Insert explicit Wait activities (60-90s) between each Notebook activity
in the orchestration pipeline, giving Spark sessions time to fully
release capacity before the next one is requested.

**Alternatives considered:**
- Upgrading to a paid Fabric capacity: would eliminate the constraint
  entirely, but violates this project's explicit cost-control requirement
  (Fabric 60-day trial, no unnecessary cloud spend).
- Combining all 4 notebooks into a single notebook (one Spark session
  for everything): would resolve the capacity issue but destroys the
  clean separation of concerns (Bronze/Silver/Gold/CDC as independently
  testable, independently re-runnable units) that the rest of this
  project deliberately maintains.

**Trade-offs:**
- Adds ~3-5 minutes of pure wait time to every pipeline run — acceptable
  for a daily batch schedule, would NOT be acceptable for a
  low-latency/near-real-time requirement.
- This is a trial-capacity-specific mitigation; a production Fabric
  capacity (F64+) would not need these waits, since it has enough
  concurrent Spark VCores to run chained sessions back-to-back.

**Consequences:**
The orchestration pipeline is now: Bronze → Wait → Silver → Wait → Gold
→ Wait → CDC. This is explicitly documented as a trial-environment
adaptation, not a production pattern — worth stating clearly in an
interview if asked why waits are hardcoded into the pipeline.


## ADR-012: overwriteSchema Instead of DROP TABLE for Silver Schema Changes

**Context:**
After bronze_loyalty gained a referral_code column via mergeSchema
(Phase 7F), silver_loyalty's mode("overwrite") write began failing with
a schema mismatch, since Delta enforces schema matching on overwrite by
default, same as it does on append.

**Decision:**
Use .option("overwriteSchema", "true") on the write instead of dropping
and recreating the table.

**Alternatives considered:**
- DROP TABLE IF EXISTS before each write: works, but destroys the
  table's entire Delta version history (time travel) on every run,
  directly undermining the auditing capability established in ADR-008.

**Consequences:**
silver_loyalty now retains full version history across schema changes,
consistent with how the rest of the project treats Delta's transaction
log as a deliberate asset, not disposable state.


## ADR-013: Fabric Data Factory Pipeline Orchestration with Wait-Based Capacity Mitigation

**Context:**
The four-notebook medallion pipeline (Bronze→Silver→Gold→CDC) needed
end-to-end orchestration with dynamic date parameters and a daily
schedule, replacing manual notebook-by-notebook execution.

**Decision:**
Built a single Fabric Data Factory pipeline chaining all 4 notebook
activities via "On Success" dependencies, each receiving processing_date
dynamically via @formatDateTime(pipeline().TriggerTime, 'yyyy-MM-dd'),
with Wait activities (90s) inserted between each notebook activity to
mitigate trial-capacity Spark session contention (see ADR-011).

**What we validated in practice:**
- First full run failed at Run_Silver with HTTP 430 (capacity) — resolved
  by adding Wait activities.
- Second full run succeeded through Bronze/Silver but failed at Run_Gold
  with a generic transient platform error (1.3s duration, "Something
  went wrong on our end") — resolved simply by retrying, confirming it
  was a genuine transient backend issue rather than a design flaw.
- Third full run succeeded end-to-end: Bronze → Silver → Gold → CDC,
  all green.

**Consequences:**
The pipeline is schedulable and does not require any hardcoded dates —
tomorrow's scheduled run will automatically process tomorrow's date via
the dynamic expression, with no manual notebook edits required. This is
the direct payoff of the Phase 8A parameterization work.


## ADR-014: dbt-fabric via SQL Analytics Endpoint (CLI Authentication, Tenant-Level)

**Context:**
Needed to connect dbt-core locally to the Fabric Lakehouse for a
SQL-based analytics engineering marts layer on top of Gold. The Lakehouse
SQL analytics endpoint is read-only (views only, not tables) — a real
architectural constraint, not a dbt limitation.

**Decision:**
Use the dbt-fabric adapter against the SQL analytics endpoint, with
CLI-based authentication via Azure CLI, connected at the tenant level
(no Azure subscription required — consistent with this project's
trial-capacity, no-billing-account constraints established in ADR-002/003).

**Trade-offs:**
- Getting `az login` to establish a valid CLI credential without an Azure
  subscription required the device-code flow and explicit tenant
  selection — more setup friction than a typical subscription-backed
  account, but confirms the whole project can run on a genuinely
  cost-free setup end to end.
- All dbt models here materialize as views, not tables, since the SQL
  endpoint cannot create tables (only Spark/OneLake writes can).

**Consequences:**
dbt is scoped specifically to a BI-facing marts layer on top of
Gold — not a Bronze/Silver/Gold replacement — consistent with the
decision in the Phase 8C introduction about where dbt genuinely fits
versus where Spark remains the right tool.