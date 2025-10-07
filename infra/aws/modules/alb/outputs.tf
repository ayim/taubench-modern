output "alb_target_group_arn" {
  value = aws_lb_target_group.main.arn
}

output "alb_targets_security_group_id" {
  value = aws_security_group.targets.id
}

output "alb_listener_arn" {
  value = aws_lb_listener.https.arn
}
