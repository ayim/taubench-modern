resource "aws_kms_key" "cluster_master_key" {
  description  = "Encryption of resources on Team Edition ECS cluster: ${var.cluster_name}"
  multi_region = true
  key_usage    = "ENCRYPT_DECRYPT"
}

resource "aws_kms_alias" "cluster_master_key" {
  name          = "alias/ecs/${var.infra_id}"
  target_key_id = aws_kms_key.cluster_master_key.arn
}
