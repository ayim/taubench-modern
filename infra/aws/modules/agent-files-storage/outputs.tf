output "bucket_name" {
  value = aws_s3_bucket.agent_files.bucket
}

output "storage_role_arn" {
  value = aws_iam_role.agent_files.arn
}

output "mcp_runtime_efs_filesystem_id" {
  value = aws_efs_file_system.mcp_runtime_data.id
}

output "mcp_runtime_efs_access_point_id" {
  value = aws_efs_access_point.mcp_runtime_data.id
}
