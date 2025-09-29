output "bucket_name" {
  value = aws_s3_bucket.agent_files.bucket
}

output "storage_role_arn" {
  value = aws_iam_role.agent_files.arn
}
