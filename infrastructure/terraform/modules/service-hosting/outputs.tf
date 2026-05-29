# Service-hosting module outputs (S07-05).
#
# Populated when the concrete cloud provider lands (ECS service ARN, Cloud Run
# URL, k8s Service name, etc.). Declared here so callers can begin referencing
# the contract even before the resources are created.

output "service_endpoint" {
  description = "Public URL (or DNS name) of the API service once provisioned."
  value       = ""
}

output "readiness_path" {
  description = "Health-check path the load-balancer/probe should hit (mirrors the input)."
  value       = var.readiness_path
}
