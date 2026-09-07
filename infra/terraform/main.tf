terraform {
  required_version = ">= 1.8.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "5.84.0"
    }
  }
}

# Control plane and publisher live outside the hostile execution account.
module "control_plane" {
  source = "./modules/control_plane"
}

module "executor" {
  source = "./modules/executor"
}
