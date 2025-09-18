data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# CodeBuild Project
resource "aws_codebuild_project" "deployer" {
  name          = "team-edition-deployer-${var.infra_name}"
  description   = "Deploys Sema4.ai Team Edition to dev environment"
  build_timeout = 10 # minutes

  service_role = aws_iam_role.codebuild_service_role.arn

  artifacts {
    type = "NO_ARTIFACTS"
  }

  environment {
    compute_type                = "BUILD_GENERAL1_SMALL"
    image                       = "aws/codebuild/standard:7.0"
    type                        = "LINUX_CONTAINER"
    image_pull_credentials_type = "CODEBUILD"

    environment_variable {
      name  = "RELEASE_NAME"
      value = "PLACEHOLDER"
      type  = "PLAINTEXT"
    }

    environment_variable {
      name  = "SPAR_IMAGE_REF"
      value = "PLACEHOLDER"
      type  = "PLAINTEXT"
    }

    environment_variable {
      name  = "AWS_REGION"
      value = data.aws_region.current.id
      type  = "PLAINTEXT"
    }

    environment_variable {
      name  = "ECS_CLUSTER_NAME"
      value = var.cluster_name
      type  = "PLAINTEXT"
    }

    environment_variable {
      name  = "ECS_TASK_EXECUTION_ROLE_ARN"
      value = var.ecs_task_execution_role_arn
      type  = "PLAINTEXT"
    }

    environment_variable {
      name  = "RDS_CREDENTIALS_SECRET_ARN"
      value = var.rds_credentials_secret_arn
      type  = "PLAINTEXT"
    }

    environment_variable {
      name  = "ALB_TARGET_GROUP_ARN"
      value = var.alb_target_group_arn
      type  = "PLAINTEXT"
    }

    environment_variable {
      name  = "ALB_TARGETS_SECURITY_GROUP_ID"
      value = var.alb_targets_security_group_id
      type  = "PLAINTEXT"
    }

    environment_variable {
      name  = "VPC_SUBNETS"
      value = join(",", var.vpc_subnet_ids)
      type  = "PLAINTEXT"
    }
  }

  source {
    type            = "GITHUB"
    location        = "https://github.com/Sema4AI/agent-platform.git"
    git_clone_depth = 1
    buildspec       = "infra/aws-ecs-fargate/codebuild/buildspec.yml"
  }

  source_version = "master"

  cache {
    type = "NO_CACHE"
  }

  logs_config {
    cloudwatch_logs {
      group_name  = "/aws/codebuild/team-edition-deployer"
      stream_name = "deployer"
    }
  }
}

resource "aws_iam_role" "codebuild_service_role" {
  name               = "team-edition-deployer-codebuild-service-role"
  assume_role_policy = data.aws_iam_policy_document.codebuild_assume_role_policy.json
}

data "aws_iam_policy_document" "codebuild_assume_role_policy" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["codebuild.amazonaws.com"]
    }

    effect = "Allow"
  }
}

resource "aws_iam_role_policy" "codebuild_ecs_access" {
  name   = "team-edition-deployer-codebuild-ecs-access"
  role   = aws_iam_role.codebuild_service_role.id
  policy = data.aws_iam_policy_document.deployer_access_policy.json
}

data "aws_iam_policy_document" "deployer_access_policy" {
  statement {
    effect = "Allow"
    actions = [
      "ecs:DescribeServices",
      "ecs:UpdateService",
      "ecs:CreateService",
    ]
    resources = [
      "arn:aws:ecs:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:service/${var.cluster_name}/*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "ecs:RegisterTaskDefinition",
      "ecs:DescribeTaskDefinition",
    ]
    resources = ["*"]
  }

  statement {
    # Required for passing the ECS task execution role
    effect = "Allow"
    actions = [
      "iam:PassRole"
    ]
    resources = ["*"]
  }

  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["*"]
  }
}

# GitHub Role for running the CodeBuild
resource "aws_iam_role" "github_deployer_role" {
  name               = "github-deployer-${var.infra_name}"
  assume_role_policy = data.aws_iam_policy_document.assume_role_from_github_policy.json
}

resource "aws_iam_role_policy" "allow_deploy_from_github" {
  role   = aws_iam_role.github_deployer_role.name
  name   = "AllowStartBuild"
  policy = data.aws_iam_policy_document.run_codebuild_policy.json
}

data "aws_iam_policy_document" "assume_role_from_github_policy" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [var.github_oidc_provider_arn]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = var.allowed_github_subjects_write
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # Note: External ID does not appear to work with AssumeRoleWithWebIdentity /
    # GH actions so we can't use it to tighten the permissions
  }
}

data "aws_iam_policy_document" "run_codebuild_policy" {
  statement {
    effect = "Allow"
    actions = [
      "codebuild:StartBuild",
      "codebuild:BatchGetBuilds",
    ]
    resources = [
      aws_codebuild_project.deployer.arn
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "logs:GetLogEvents",
    ]
    resources = [
      "arn:aws:logs:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:log-group:/aws/codebuild/team-edition-deployer:*"
    ]
  }
}
