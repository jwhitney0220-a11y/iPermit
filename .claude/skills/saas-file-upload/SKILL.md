---
name: saas-file-upload
description: Use when implementing validated file uploads to object storage — including the iPermit shapefile/KMZ intake that feeds GIS detection.
---

# saas-file-upload — validated object-storage uploads

**Reference:** open-saas `template/app/src/file-upload` (`s3Utils`, `validation`, `operations`, presigned uploads).

## Conventions
- Validate type and size **server-side**; issue a presigned PUT to S3-compatible storage. Store the object key + content hash + metadata in the DB — never the blob.
- Untrusted input: enforce content-type allowlists and size caps; never execute or trust uploaded content.
- iPermit: shapefile/KMZ uploads become a `footprint_ref` consumed by the GIS `DetectionBackend` (`services/gis-engine/ipermit_gis/detection.py`). Keep the upload layer separate from parsing (T05-02).
- `STORAGE_*` env vars per `.env.example`.

## Guardrails
- **MANDATORY** security-review for any upload path (SSRF on presign, path traversal, content sniffing).
- Tenant-scope stored objects (use **saas-multitenancy**). Functions ≤ 60 lines.
