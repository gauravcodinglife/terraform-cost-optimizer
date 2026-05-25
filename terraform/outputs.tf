output "vpc_id" {
  description = "VPC ID"
  value       = module.network.vpc_id
}

output "subnet_ids" {
  description = "Public subnet IDs"
  value       = module.network.subnet_ids
}

output "bucket_name" {
  description = "S3 app logs bucket name"
  value       = aws_s3_bucket.app_logs.bucket
}

output "web_instance_ids" {
  description = "IDs of the two web EC2 instances"
  value       = aws_instance.web[*].id
}

output "orphan_ebs_volume_id" {
  description = "ID of the intentionally unattached EBS volume"
  value       = aws_ebs_volume.orphan.id
}
