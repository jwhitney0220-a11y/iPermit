# Backend service hosting (S07-05, SAAS-07).
#
# Provider-neutral skeleton for the container that runs the iPermit API. Once
# the hosting decision lands (ECS / Cloud Run / k8s), this module wires the
# concrete resources behind the same input + output contract, so the root
# composition does not have to change shape.
#
# Outputs are deliberately empty for now — they get populated when the
# concrete resources are added (service ARN/URL, health-check endpoint, etc.).
