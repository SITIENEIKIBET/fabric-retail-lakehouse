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