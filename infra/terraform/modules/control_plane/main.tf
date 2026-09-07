variable "name" { default = "tracefix" }

output "notes" {
  value = "Provision RDS PostgreSQL 17, S3 artifacts, IAM for API/publisher only. No GitHub private key in executor."
}
