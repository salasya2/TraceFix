variable "name" { default = "tracefix" }
variable "region" { default = "us-east-1" }

resource "aws_s3_bucket" "artifacts" {
  bucket = "${var.name}-artifacts"
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_db_instance" "control_plane" {
  identifier                 = "${var.name}-pg"
  engine                     = "postgres"
  engine_version             = "17.4"
  instance_class             = "db.t3.medium"
  allocated_storage          = 50
  username                   = "tracefix"
  password                   = "change-me-in-tfvars"
  db_name                    = "tracefix"
  skip_final_snapshot        = true
  publicly_accessible        = false
  auto_minor_version_upgrade = true
}

resource "aws_iam_role" "api" {
  name = "${var.name}-api"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role" "publisher" {
  name = "${var.name}-publisher"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "api_artifacts" {
  name = "${var.name}-api-artifacts"
  role = aws_iam_role.api.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
      Resource = [aws_s3_bucket.artifacts.arn, "${aws_s3_bucket.artifacts.arn}/*"]
    }]
  })
}

output "artifact_bucket" {
  value = aws_s3_bucket.artifacts.bucket
}

output "database_endpoint" {
  value = aws_db_instance.control_plane.address
}

output "notes" {
  value = "Control-plane RDS PostgreSQL 17 and S3 artifacts. GitHub App private key stays in the credential broker, never the executor."
}
