provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      infra_id = var.infra_id
      source   = "terraform:moonraker/infra/aws/ecs-fargate"
    }
  }
}
