resource "aws_iam_policy" "cluster_master_key_usage" {
  name        = "${var.infra_id}-cluster-encryption"
  description = "Policy to allow usage of the cluster master key"
  policy      = data.aws_iam_policy_document.cluster_master_key_usage.json
}

resource "aws_iam_role_policy_attachment" "cluster_master_key_usage" {
  role       = aws_iam_role.ecs_task_role.name
  policy_arn = aws_iam_policy.cluster_master_key_usage.arn
}

data "aws_iam_policy_document" "cluster_master_key_usage" {
  statement {
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:DescribeKey",
      "kms:Encrypt",
      "kms:GenerateDataKey"
    ]
    resources = [
      var.cluster_master_key_arn
    ]
  }
}
