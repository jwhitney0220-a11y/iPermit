# Terraform and provider version constraints (T01-09).
#
# ADR-0001 permitted "Terraform, Pulumi, or equivalent". We chose Terraform
# (see infrastructure/README.md for the rationale). Pinning versions here keeps
# every environment on the same toolchain and prevents silent provider drift.
#
# SKELETON ONLY: the provider block below is a placeholder. The concrete cloud
# provider is selected with the hosting decision in T01-16 / T05-01. Do not run
# `terraform apply` against this skeleton.

terraform {
  # Pin the Terraform CLI to a known-good major line. Tighten the upper bound
  # once the team standardizes on a release in T01-09 implementation.
  required_version = ">= 1.7.0, < 2.0.0"

  required_providers {
    # Placeholder provider. Replace `local` with the chosen cloud provider
    # (e.g. aws / google / azurerm) when the hosting decision lands. The
    # `local` provider is referenced here only so the skeleton is well-formed
    # and parseable without committing to a cloud yet.
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }

    # random is commonly needed for naming suffixes / generated values; kept as
    # a placeholder so module skeletons can reference it.
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Remote state backend is configured PER ENVIRONMENT, not here. See
  # environments/{staging,production}/backend.tf. A partial/empty backend block
  # is intentionally omitted from the root so each environment owns its state.
}
