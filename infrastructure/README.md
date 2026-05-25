# infrastructure/

Infrastructure-as-Code. Tooling (Terraform / Pulumi / equivalent) is selected and
implemented in T01-09.

Will provision:

- PostgreSQL 16 + PostGIS (relational + spatial data; see [ADR-0001](../docs/architecture/adr-0001-tech-stack.md) and T01-16 spatial planning)
- Object storage (uploaded shapefiles/KMZ, exported deliverables)
- Backend service hosting
- CI/CD infrastructure

## Status

Directory scaffold only. Spatial DB hosting decisions (managed vs. self-hosted
PostGIS) are made in T01-16 before stand-up in T05-01.
