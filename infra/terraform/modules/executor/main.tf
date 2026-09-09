variable "name" { default = "tracefix-executor" }

resource "aws_iam_role" "executor" {
  name = var.name
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "executor_no_secrets" {
  name = "${var.name}-deny-secrets"
  role = aws_iam_role.executor.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "DenyCredentialAndGithubAccess"
      Effect   = "Deny"
      Action   = ["secretsmanager:*", "ssm:GetParameter", "ssm:GetParameters"]
      Resource = "*"
    }]
  })
}

output "runtime_class" {
  value = "gvisor"
}

output "notes" {
  value = "Dedicated gVisor node group. Job admission must fail closed without RuntimeClass runsc. No hostPath, no service-account token, no GitHub/model credentials."
}
