# Service-hosting module inputs (S07-05).

variable "name_prefix" {
  description = "Resource name prefix, e.g. ipermit-staging."
  type        = string
}

variable "region" {
  description = "Cloud region for regional resources."
  type        = string
}

variable "image" {
  description = "Fully-qualified container image (e.g. ECR repo URI + tag) the API task runs."
  type        = string
}

variable "container_port" {
  description = "Port the API listens on inside the container (matches uvicorn bind in services/api/Dockerfile)."
  type        = number
  default     = 8000
}

variable "desired_count" {
  description = "Number of concurrent service instances. The orchestrator scales between min and this value."
  type        = number
  default     = 2
}

variable "cpu" {
  description = "CPU units allocated per task (cloud-provider specific scale)."
  type        = number
  default     = 512
}

variable "memory_mb" {
  description = "Memory allocated per task, in MiB."
  type        = number
  default     = 1024
}

variable "env" {
  description = "Non-secret environment variables injected at container start. Secrets come from the secret manager (see docs/operations/environments.md)."
  type        = map(string)
  default     = {}
}

variable "secret_refs" {
  description = "Map of env var name -> secret-manager reference. Resolved by the orchestrator at startup, never baked into the image."
  type        = map(string)
  default     = {}
}

variable "readiness_path" {
  description = "HTTP path the load-balancer health-checks (S07-03 /readyz)."
  type        = string
  default     = "/readyz"
}

variable "tags" {
  description = "Common tags applied to every resource the module owns."
  type        = map(string)
  default     = {}
}
