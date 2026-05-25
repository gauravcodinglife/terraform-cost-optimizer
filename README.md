# NimbusKart Cost Hygiene Platform

## Overview

This repository implements a cloud cost hygiene automation platform for NimbusKart, an e-commerce startup whose AWS bill grew from ~$400/month to ~$2,100/month due to orphaned and untagged resources. The solution has three parts: a modular Terraform stack that provisions NimbusKart's baseline AWS infrastructure on LocalStack (a local AWS emulator), a Python-based "Cost Janitor" script that automatically detects wasteful resources, and a GitHub Actions CI/CD pipeline that runs the janitor on every pull request — blocking merges when orphans are found and posting a detailed cost report as a PR comment.

---

## How to Run Locally

Start from a clean machine with Docker and Python 3.10+ installed.

```bash
# 1. Clone the repository
git clone https://github.com/gauravcodinglife/terraform-cost-optimizer.git
cd terraform-cost-optimizer

# 2. Install Python dependencies
pip install -r janitor/requirements.txt
pip install terraform-local

# 3. Install Terraform (Ubuntu/Debian)
sudo apt-get update && sudo apt-get install -y gnupg software-properties-common curl
curl -fsSL https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt-get update && sudo apt-get install terraform

# 4. Start LocalStack (free version — 3.8.1 is the last version without a paid license)
docker run -d \
  --name localstack \
  -p 4566:4566 \
  -e SERVICES=ec2,s3,sts \
  -e DEFAULT_REGION=us-east-1 \
  localstack/localstack:3.8.1

# 5. Wait for LocalStack to be ready (~20 seconds)
curl -s http://localhost:4566/_localstack/health

# 6. Apply Terraform (creates VPC, EC2, S3, orphan EBS in LocalStack)
cd terraform
tflocal init
tflocal apply -auto-approve
cd ..

# 7. Run the Cost Janitor in dry-run mode (safe — no deletions)
cd janitor
python janitor.py --dry-run --endpoint-url http://localhost:4566

# 8. View the reports
cat report.json
cat report.md

# 9. (Optional) Run in delete mode — removes safe orphans, skips Protected=true
python janitor.py --delete --endpoint-url http://localhost:4566
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        GitHub Actions CI                         │
│                                                                  │
│  PR opened/updated                                               │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────┐    ┌─────────────┐    ┌──────────────────────┐ │
│  │  LocalStack  │    │  Terraform  │    │    Cost Janitor       │ │
│  │  (Docker)    │◄───│   apply     │    │    janitor.py        │ │
│  │             │    │             │    │                      │ │
│  │  Fake AWS:  │    │  Creates:   │    │  Scans for:          │ │
│  │  - EC2 API  │    │  - VPC      │    │  - Unattached EBS    │ │
│  │  - S3  API  │    │  - Subnets  │    │  - Stopped EC2       │ │
│  │  - STS API  │    │  - EC2 x2   │    │  - Idle EIPs         │ │
│  └─────────────┘    │  - S3       │    │  - Missing tags      │ │
│                     │  - EBS orphan│   └──────────┬───────────┘ │
│                     └─────────────┘              │              │
│                                                  ▼              │
│                                    ┌─────────────────────────┐  │
│                                    │  report.json + report.md │  │
│                                    │  uploaded as artifacts   │  │
│                                    │                         │  │
│                                    │  PR comment posted      │  │
│                                    │  if orphans found       │  │
│                                    │                         │  │
│                                    │  exit 1 → blocks merge  │  │
│                                    └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘

Terraform Module Structure:
  terraform/
    main.tf              ← root: EC2, S3, EBS, calls network module
    variables.tf         ← all configurable values
    outputs.tf           ← VPC ID, subnet IDs, bucket name
    modules/network/     ← reusable VPC, subnets, security group
```

---

## Decisions & Deviations

- **SSH CIDR changed from 0.0.0.0/0 to 10.0.0.0/8** — opening SSH to the entire internet is a critical security risk; restricted to private network range by default with a configurable variable.
- **LocalStack pinned to version 3.8.1** — `localstack:latest` as of May 2026 requires a paid license and exits with code 55 in CI; 3.8.1 is the last free community version.
- **AMI resolved via data source** — LocalStack emulates the AWS AMI API well enough that a real `data "aws_ami"` lookup works; no hardcoding needed.
- **EC2 instances never auto-deleted** — even in `--delete` mode, the janitor only flags instances as findings; terminating compute is too destructive for automation without human approval.
- **S3 lifecycle rule on non-current versions only** — the spec said "expire non-current versions after 30 days" which we implemented exactly; current objects are never touched.
- **No remote Terraform state** — using local state is fine for LocalStack; in production this would be S3 + DynamoDB locking (noted in DESIGN.md).
- **`Protected=true` enforced at both app and IAM level** — the script checks the tag before deletion, and the IAM policy in DESIGN.md adds a Condition block as a second safety net.

---

## Trade-offs

Given one more week, these are the things I would improve:

- **Remote Terraform state**: Add an S3 backend with DynamoDB locking so multiple engineers can run Terraform without state conflicts.
- **Multi-account scanning**: The janitor currently scans one account. Real FinOps requires cross-account role assumption via `sts:AssumeRole` across dev, staging, and prod accounts.
- **Snapshot before delete**: In `--delete` mode, take an EBS snapshot before deleting any volume and retain it for 72 hours as a safety net.
- **Slack/PagerDuty notifications**: The PR comment is useful for developers but the FinOps team needs a Slack digest of weekly waste trends.
- **RDS and snapshot scanning**: Old RDS instances and accumulated EBS snapshots are major cost drivers not covered in this version.
- **Terraform state cleanup**: The `.terraform.lock.hcl` and local state files should be in `.gitignore` and state stored remotely.
- **CloudWatch metrics publishing**: The DESIGN.md describes 5 metrics; wiring the actual `put_metric_data` calls into the janitor would close the observability loop.

---

## AI Usage Disclosure

### Tools used
- **Claude (Anthropic)** — used throughout for: Terraform module structure, janitor.py scaffold, GitHub Actions workflow yml, DESIGN.md architecture sections, and debugging LocalStack connectivity issues.
- **GitHub Copilot** — used for inline autocompletion while writing Python helper functions (`get_tag`, `age_in_days`).

### One thing AI got wrong
The GitHub Actions workflow initially used `localstack/localstack:latest` as the service container image. Claude confidently suggested this would work. It failed because LocalStack's latest image (as of May 2026) requires a paid license and exits with code 55 (`License activation failed`). I noticed this by reading the raw Docker logs in the Actions tab, which showed the exact error message. The fix was to pin the image to `localstack/localstack:3.8.1`, the last free community version. AI was not aware of this recent breaking change.

### One section written without AI
The `scan_stopped_instances()` function in `janitor.py` was written manually. I noticed that AWS does not expose a "stopped since" timestamp in the standard `describe_instances` API response — it only gives `LaunchTime`. I made a deliberate decision to use `LaunchTime` as a conservative proxy and documented this limitation explicitly in the code comments. AI suggested using CloudTrail for precise stop timestamps, which is correct for production but overkill for this scope. I chose to document the limitation honestly rather than over-engineer it.
