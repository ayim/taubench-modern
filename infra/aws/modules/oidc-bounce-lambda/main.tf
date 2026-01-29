data "archive_file" "bounce" {
  type        = "zip"
  source_file = "${path.module}/index.js"
  output_path = "${path.module}/function.zip"
}

resource "aws_iam_role" "bounce" {
  name = "${var.infra_id}-lambda_http_interceptor_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "bounce" {
  role       = aws_iam_role.bounce.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Lambda function
resource "aws_lambda_function" "bounce" {
  filename         = data.archive_file.bounce.output_path
  function_name    = "oidc-bounce"
  role             = aws_iam_role.bounce.arn
  handler          = "index.handler"
  source_code_hash = data.archive_file.bounce.output_base64sha256
  runtime          = "nodejs22.x"
}

resource "aws_lambda_function_url" "bounce" {
  function_name      = aws_lambda_function.bounce.function_name
  authorization_type = "NONE"
}
