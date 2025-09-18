data "aws_caller_identity" "current" {}

resource "aws_route53_zone" "main" {
  name = var.host_name
}

data "aws_iam_policy_document" "kms_key_policy" {
  statement {
    sid    = "Enable IAM User Permissions"
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
    actions   = ["kms:*"]
    resources = ["*"]
  }

  statement {
    sid    = "Allow ECS execution role to decrypt"
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/ecs-execution-${var.infra_id}"]
    }
    actions = [
      "kms:Decrypt",
      "kms:DescribeKey"
    ]
    resources = ["*"]
  }
}

resource "aws_kms_key" "key" {
  description = "Encryption key for the Sema4 Team Edition infrastructure ${var.infra_id}"
  policy      = data.aws_iam_policy_document.kms_key_policy.json
}

/**
 * Note: There can only be one of these per AWS account.
 */
resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

module "vpc" {
  source = "../modules/vpc"

  vpc_name             = var.infra_id
  private_subnet_count = 3
  public_subnet_count  = 3
  natgw_count          = 1
}

module "alb" {
  source = "../modules/alb"

  infra_id          = var.infra_id
  vpc_id            = module.vpc.vpc_id
  public_subnet_ids = module.vpc.public_subnet_ids
  route53_zone_id   = aws_route53_zone.main.zone_id
  target_port       = 8001
  health_check_path = "/"
}

module "postgres" {
  source = "../modules/rds-aurora-pg"

  cluster_name                  = var.infra_id
  subnet_ids                    = module.vpc.private_subnet_ids
  postgres_engine_version       = "17.5"
  cluster_instance_count        = 1
  encryption_key_arn            = aws_kms_key.key.arn
  admin_credentials_secret_name = "${var.infra_id}/rds-admin-credentials"
}

module "ecs-cluster" {
  source = "../modules/ecs-cluster"

  cluster_name                  = var.infra_id
  logs_region                   = var.aws_region
  execution_role_name           = "ecs-execution-${var.infra_id}"
  auth_configuration_secret_arn = module.app-auth.auth_configuration_secret_arn
  rds_credentials_secret_arn    = module.postgres.cluster_credentials_secret_arn
  secrets_encryption_key_arn    = aws_kms_key.key.arn
}

module "codebuild" {
  source = "../modules/codebuild"

  cluster_name = module.ecs-cluster.ecs_cluster_name
  infra_id     = var.infra_id

  allowed_github_subjects_write = ["repo:Sema4AI/agent-platform:*"]
  github_oidc_provider_arn      = aws_iam_openid_connect_provider.github.arn

  ecs_task_execution_role_arn   = module.ecs-cluster.ecs_task_execution_role_arn
  auth_configuration_secret_arn = module.app-auth.auth_configuration_secret_arn
  rds_credentials_secret_arn    = module.postgres.cluster_credentials_secret_arn
  alb_target_group_arn          = module.alb.alb_target_group_arn
  alb_targets_security_group_id = module.alb.alb_targets_security_group_id
  vpc_subnet_ids                = module.vpc.private_subnet_ids
}

module "app-auth" {
  source = "../modules/app-auth"

  infra_id           = var.infra_id
  encryption_key_arn = aws_kms_key.key.arn
}
