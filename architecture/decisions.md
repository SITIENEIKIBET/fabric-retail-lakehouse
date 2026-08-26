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