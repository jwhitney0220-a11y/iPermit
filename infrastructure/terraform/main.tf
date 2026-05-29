# Root composition (T01-09).
#
# This file wires the environment-level inputs into the reusable modules. It is
# a SKELETON: module blocks reference local module skeletons that declare
# variables/outputs but provision nothing yet. The concrete cloud provider and
# resources are filled in once the hosting decision (T01-16 / T05-01) lands.
#
# Provisions (when implemented):
#   - PostgreSQL 16 + PostGIS  (modules/database)
#   - Object storage           (modules/storage)
#   - Backend service hosting  (future module — not yet scaffolded)
#   - CI/CD infrastructure     (future module — not yet scaffolded)

# Placeholder provider configuration. Replace with the chosen cloud provider
# (aws / google / azurerm) when selected. Kept minimal so the skeleton parses.
provider "local" {}

provider "random" {}

locals {
  # Common name prefix, e.g. "ipermit-staging".
  name_prefix = "${var.project_name}-${var.environment}"

  # Merge per-environment tags onto the common set.
  tags = merge(var.common_tags, {
    environment = var.environment
  })
}

# --- Database: PostgreSQL 16 + PostGIS ---------------------------------------
module "database" {
  source = "./modules/database"

  name_prefix      = local.name_prefix
  region           = var.region
  postgres_version = var.postgres_version
  postgis_required = var.postgis_required
  instance_size    = var.db_instance_size
  tags             = local.tags
}

# --- Object storage: uploads + exported deliverables -------------------------
module "storage" {
  source = "./modules/storage"

  name_prefix        = local.name_prefix
  region             = var.region
  versioning_enabled = var.storage_versioning_enabled
  tags               = local.tags
}

# --- Backend service hosting (API container) — S07-05 ------------------------
module "service_hosting" {
  source = "./modules/service-hosting"

  name_prefix    = local.name_prefix
  region         = var.region
  image          = var.api_image
  desired_count  = var.api_desired_count
  readiness_path = "/readyz"
  tags           = local.tags
}

# --- Future modules (placeholders, intentionally not yet scaffolded) ---------
# module "cicd"            { source = "./modules/cicd" ... }
