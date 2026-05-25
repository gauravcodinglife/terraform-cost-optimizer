# Tell Terraform to use LocalStack instead of real AWS
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region                      = var.aws_region
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
  endpoints {
    ec2       = "http://localhost:4566"
    s3        = "http://localhost:4566"
    s3control = "http://localhost:4566"
    iam       = "http://localhost:4566"
  }
}

# ── Call the network module ──────────────────────────────────────────────────
module "network" {
  source           = "./modules/network"
  vpc_cidr         = var.vpc_cidr
  project          = var.project
  environment      = var.environment
  owner            = var.owner
  ssh_ingress_cidr = var.ssh_ingress_cidr
}

# ── EC2 Instances (web tier) ─────────────────────────────────────────────────
data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}

resource "aws_instance" "web" {
  count                  = 2
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = "t3.micro"
  subnet_id              = module.network.subnet_ids[count.index]
  vpc_security_group_ids = [module.network.web_security_group_id]
  tags = {
    Name        = "${var.project}-${var.environment}-web-${count.index + 1}"
    Project     = var.project
    Environment = var.environment
    Owner       = var.owner
    ManagedBy   = "terraform"
    Tier        = "web"
  }
}

# ── S3 Bucket for application logs ──────────────────────────────────────────
resource "aws_s3_bucket" "app_logs" {
  bucket = "${lower(var.project)}-${var.environment}-app-logs"
  tags = {
    Name        = "${var.project}-${var.environment}-app-logs"
    Project     = var.project
    Environment = var.environment
    Owner       = var.owner
    ManagedBy   = "terraform"
  }
}

# Enable versioning on the bucket
resource "aws_s3_bucket_versioning" "app_logs" {
  bucket = aws_s3_bucket.app_logs.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Lifecycle rule — delete old non-current versions after 30 days
#resource "aws_s3_bucket_lifecycle_configuration" "app_logs" {
# count  = var.environment == "localstack" ? 0 : 1
#  bucket = aws_s3_bucket.app_logs.id
#  rule {
#    id     = "expire-noncurrent-versions"
#    status = "Enabled"
#    filter {}
#    noncurrent_version_expiration {
#      noncurrent_days = 30
#    }
#  }
#}

# ── Orphan EBS Volume ────────────────────────────────────────────────────────
resource "aws_ebs_volume" "orphan" {
  availability_zone = "us-east-1a"
  size              = 20
  type              = "gp3"
  tags = {
    Name        = "${var.project}-${var.environment}-orphan-vol"
    Project     = var.project
    Environment = var.environment
    Owner       = var.owner
    ManagedBy   = "terraform"
  }
}
