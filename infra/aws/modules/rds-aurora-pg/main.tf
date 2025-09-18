
data "aws_subnet" "subnets" {
  count = length(var.subnet_ids)
  id    = var.subnet_ids[count.index]
}

data "aws_vpc" "vpc" {
  # Determine the VPC ID from one of the subnets
  id = data.aws_subnet.subnets[0].vpc_id
}

locals {
  db_cluster_name  = var.cluster_name
  cluster_username = "clusteradmin"
  cluster_password = random_password.cluster_admin_password.result
}


resource "aws_kms_key" "cluster_data" {
  description  = "Encryption of RDS cluster ${var.cluster_name}"
  multi_region = true
  key_usage    = "ENCRYPT_DECRYPT"
}

resource "random_password" "cluster_admin_password" {
  length  = 32
  special = false
}

resource "aws_db_subnet_group" "postgres" {
  name       = "${var.cluster_name}-subnet-group"
  subnet_ids = var.subnet_ids
}

resource "aws_security_group" "postgres" {
  name        = "${var.cluster_name}-database-security-group"
  description = "Security group for ACE database"
  vpc_id      = data.aws_vpc.vpc.id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.vpc.cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_rds_cluster" "cluster" {
  cluster_identifier      = local.db_cluster_name
  engine                  = "aurora-postgresql"
  engine_mode             = "provisioned"
  engine_version          = var.postgres_engine_version
  master_username         = local.cluster_username
  master_password         = local.cluster_password
  backup_retention_period = 35
  storage_encrypted       = true
  kms_key_id              = var.encryption_key_arn
  db_subnet_group_name    = aws_db_subnet_group.postgres.id
  vpc_security_group_ids  = [aws_security_group.postgres.id]

  availability_zones = [for subnet in data.aws_subnet.subnets : subnet.availability_zone]

  deletion_protection = var.cluster_deletion_protection
  skip_final_snapshot = !var.cluster_deletion_protection

  lifecycle {
    ignore_changes = [engine_version]
  }

  serverlessv2_scaling_configuration {
    max_capacity = 5.0
    min_capacity = 0.5
  }
}

resource "aws_rds_cluster_instance" "serverless" {
  count              = var.cluster_instance_count
  identifier         = "${local.db_cluster_name}-instance-${count.index + 1}"
  cluster_identifier = aws_rds_cluster.cluster.id
  engine             = aws_rds_cluster.cluster.engine
  engine_version     = aws_rds_cluster.cluster.engine_version
  instance_class     = "db.serverless" # Aurora Serverless v2
}

resource "aws_secretsmanager_secret" "ace-db-credentials" {
  count = var.admin_credentials_secret_name != null ? 1 : 0

  name        = var.admin_credentials_secret_name
  description = "RDS Postgres DB admin credentials for ${var.cluster_name}"
  kms_key_id  = var.encryption_key_arn
}

resource "aws_secretsmanager_secret_version" "ace-db-credentials" {
  count = var.admin_credentials_secret_name != null ? 1 : 0

  secret_id = aws_secretsmanager_secret.ace-db-credentials[0].id
  secret_string = jsonencode({
    cluster_name = aws_rds_cluster.cluster.id
    username     = local.cluster_username
    password     = local.cluster_password
    host         = aws_rds_cluster.cluster.endpoint
    port         = aws_rds_cluster.cluster.port
    ro_host      = aws_rds_cluster.cluster.reader_endpoint
  })
}
