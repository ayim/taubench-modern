#region KMS
resource "aws_kms_key" "agent_files" {
  description  = "Encryption of agent files data on ${var.infra_id}"
  multi_region = true
  key_usage    = "ENCRYPT_DECRYPT"
}

resource "aws_kms_alias" "agent_files" {
  name          = "alias/agent-files-${var.infra_id}"
  target_key_id = aws_kms_key.agent_files.arn
}
#endregion

#region S3
resource "aws_s3_bucket" "agent_files" {
  bucket = "${var.infra_id}-agent-files"
}

resource "aws_s3_bucket_public_access_block" "agent_files" {
  bucket = aws_s3_bucket.agent_files.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "agent_files" {
  bucket = aws_s3_bucket.agent_files.bucket

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_alias.agent_files.target_key_arn
    }

    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_versioning" "agent_files" {
  bucket = aws_s3_bucket.agent_files.bucket

  versioning_configuration {
    status = "Disabled"
  }
}

resource "aws_s3_bucket_ownership_controls" "agent_files" {
  bucket = aws_s3_bucket.agent_files.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}
#endregion

#region IAM
data "aws_iam_policy_document" "agent_files_trust_policy" {
  statement {
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = [var.ecs_runtime_role_arn]
    }

    actions = ["sts:AssumeRole"]
  }
}

data "aws_iam_policy_document" "agent_files_policy" {
  statement {
    effect = "Allow"

    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject"
    ]

    resources = ["arn:aws:s3:::${aws_s3_bucket.agent_files.bucket}/*"]
  }

  statement {
    effect = "Allow"

    actions = [
      "kms:Encrypt",
      "kms:Decrypt",
      "kms:ReEncrypt*",
      "kms:GenerateDataKey*",
      "kms:DescribeKey"
    ]

    resources = [aws_kms_key.agent_files.arn]
  }
}

resource "aws_iam_role" "agent_files" {
  name               = "${var.infra_id}-s3-access"
  assume_role_policy = data.aws_iam_policy_document.agent_files_trust_policy.json
}

resource "aws_iam_policy" "agent_files" {
  name   = "${var.infra_id}-s3-access"
  policy = data.aws_iam_policy_document.agent_files_policy.json
}

resource "aws_iam_role_policy_attachment" "agent_files" {
  role       = aws_iam_role.agent_files.name
  policy_arn = aws_iam_policy.agent_files.arn
}
#endregion

#region EFS
resource "aws_efs_file_system" "mcp_runtime_data" {
  encrypted        = true
  kms_key_id       = aws_kms_key.agent_files.arn
  performance_mode = "generalPurpose"
  throughput_mode  = "bursting"

  tags = {
    Name = "${var.infra_id}-mcp-runtime-data"
  }
}

resource "aws_security_group" "efs" {
  name        = "${var.infra_id}-efs"
  description = "Security group for EFS mcp-runtime data"
  vpc_id      = var.vpc_id

  ingress {
    description     = "NFS from ECS tasks"
    from_port       = 2049
    to_port         = 2049
    protocol        = "tcp"
    security_groups = [var.ecs_tasks_security_group_id]
  }

  tags = {
    Name = "${var.infra_id}-efs"
  }
}

resource "aws_efs_mount_target" "mcp_runtime_data" {
  for_each = var.vpc_subnet_ids

  file_system_id  = aws_efs_file_system.mcp_runtime_data.id
  subnet_id       = each.value
  security_groups = [aws_security_group.efs.id]
}

resource "aws_efs_access_point" "mcp_runtime_data" {
  file_system_id = aws_efs_file_system.mcp_runtime_data.id

  root_directory {
    path = "/mcp-runtime"
    creation_info {
      owner_uid   = 1001
      owner_gid   = 1001
      permissions = "755"
    }
  }

  posix_user {
    uid = 1001
    gid = 1001
  }

  tags = {
    Name = "${var.infra_id}-mcp-runtime-access-point"
  }
}
#endregion
