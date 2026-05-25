# Root-level input variables (T01-09).
#
# These are the inputs an environment supplies via its terraform.tfvars (see
# environments/{staging,production}/terraform.tfvars.example). Non-secret values
# only — secrets come from the secret manager at runtime, never from tfvars.
# See docs/operations/environments.md for the secrets-handling policy.

variable "environment" {
  description = "Deployment environment name. Drives resource naming and tags. Mirrors IPERMIT_ENV in the app."
  type        = string

  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be one of: staging, production (local development does not use Terraform)."
  }
}

variable "region" {
  description = "Cloud region for all regional resources (DB, storage, compute)."
  type        = string
  default     = "us-east-2"
}

variable "project_name" {
  description = "Short project slug used as a prefix for resource names. Texas-first MVP, but kept generic for multi-state expansion (AGENTS.md Geographic Scope)."
  type        = string
  default     = "ipermit"
}

# --- Database (PostgreSQL 16 + PostGIS) ---------------------------------------
# Wiring for the database module. Spatial hosting trade-offs are decided in
# T01-16 (docs/operations/postgis-planning.md); these inputs anticipate a
# managed-Postgres-with-PostGIS shape but are provider-neutral here.

variable "postgres_version" {
  description = "Major PostgreSQL version. ADR-0001 targets 16."
  type        = string
  default     = "16"
}

variable "postgis_required" {
  description = "Whether the PostGIS extension must be available/enabled in this environment. Staging mirrors production so spatial extensions can be tested (T01-16)."
  type        = bool
  default     = true
}

variable "db_instance_size" {
  description = "Managed DB instance/compute size. Intentionally provider-neutral placeholder; mapped to a concrete SKU in the database module once the provider is chosen."
  type        = string
  default     = "small"
}

# --- Object storage (uploads / exported deliverables) ------------------------

variable "storage_versioning_enabled" {
  description = "Enable object versioning on the uploads/deliverables bucket (recommended for audit/traceability per AGENTS.md)."
  type        = bool
  default     = true
}

# --- Tagging ------------------------------------------------------------------

variable "common_tags" {
  description = "Tags applied to every taggable resource for cost attribution and ownership."
  type        = map(string)
  default = {
    project   = "ipermit"
    managed_by = "terraform"
    ticket    = "T01-09"
  }
}
