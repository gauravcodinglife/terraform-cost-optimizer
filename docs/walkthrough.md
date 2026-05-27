# WALKTHROUGH.md — Cloud Cost Hygiene Platform

A step-by-step guide to running the full project locally, from zero to a passing CI/CD pipeline.

---

## Prerequisites

Make sure the following are installed before you begin:

```bash
docker --version        # Docker Desktop or Docker Engine
python3 --version       # Python 3.10 or higher
terraform version       # Terraform CLI
git --version           # Git
```

If any are missing:
- Docker → https://docs.docker.com/get-docker/
- Terraform → https://developer.hashicorp.com/terraform/install
- Python → https://www.python.org/downloads/

---

## Step 1 — Clone the Repository

```bash
git clone https://github.com/gauravcodinglife/terraform-cost-optimizer.git
cd terraform-cost-optimizer
```

---

## Step 2 — Set Up Python Environment

```bash
# Create a virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate          # macOS / Linux
# venv\Scripts\activate           # Windows

# Install dependencies
pip install -r janitor/requirements.txt
pip install terraform-local
```

`terraform-local` installs the `tflocal` CLI wrapper, which points Terraform commands at LocalStack instead of real AWS.

---

## Step 3 — Start LocalStack

LocalStack emulates AWS services locally — no real AWS account or billing required.

```bash
docker run -d \
  --name localstack \
  -p 4566:4566 \
  -e SERVICES=ec2,s3,sts \
  -e DEFAULT_REGION=us-east-1 \
  localstack/localstack:3.8.1
```

> ⚠️ **Important:** Use version `3.8.1` specifically. The `latest` tag now requires a paid license and will fail with exit code 55 ("License activation failed").

Wait for LocalStack to be ready:

```bash
sleep 20

# Verify it's running
curl http://localhost:4566/_localstack/health
```

You should see `"ec2": "running"` and `"s3": "running"` in the response.

---

## Step 4 — Apply Terraform Infrastructure

```bash
cd terraform

# Initialise providers (downloads AWS provider pointed at LocalStack)
tflocal init

# Preview what will be created
tflocal plan

# Apply — provision all resources
tflocal apply -auto-approve
```

**What gets created:**

```
aws_vpc.main                    — VPC (10.0.0.0/16)
aws_subnet.public[0]            — Public subnet AZ-a
aws_subnet.public[1]            — Public subnet AZ-b
aws_security_group.web          — SSH restricted to 10.0.0.0/8
aws_instance.web[0]             — EC2 web server 1
aws_instance.web[1]             — EC2 web server 2
aws_s3_bucket.main              — S3 bucket with versioning
aws_ebs_volume.orphan           — ⚠️ Intentional orphan (unattached)
```

Expected output (last few lines):

```
Apply complete! Resources: 8 added, 0 changed, 0 destroyed.

Outputs:
vpc_id = "vpc-xxxxxxxx"
instance_ids = ["i-xxxxxxxx", "i-yyyyyyyy"]
```

Go back to the project root:

```bash
cd ..
```

---

## Step 5 — Run the Cost Janitor

```bash
cd janitor

python3 janitor.py --dry-run --endpoint-url http://localhost:4566
```

The `--dry-run` flag means the scanner **will not delete anything** — it only reports.

**Expected terminal output:**

```
[INFO] Scanning for unattached EBS volumes...
[FOUND] vol-xxxxxxxx — 16 GB — unattached — est. $1.60/month

[INFO] Scanning for stopped EC2 instances (> 14 days)...
[OK] No stopped instances found.

[INFO] Scanning for idle Elastic IPs...
[OK] No idle Elastic IPs found.

[INFO] Scanning for untagged resources...
[OK] All resources tagged.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Orphans found: 1
  Estimated monthly waste: $1.60
  Exit code: 1 (orphans detected)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Exit code `1` means orphans were found — this is the correct, expected result because we intentionally provisioned an orphan EBS volume in Step 4.

**View the generated reports:**

```bash
cat report.md      # Human-readable summary
cat report.json    # Machine-readable findings
```

---

## Step 6 — Understanding the Reports

### report.md (example)

```markdown
# Cost Janitor Report
Generated: 2024-11-15 10:32:44

## Summary
| Category              | Count | Est. Monthly Cost |
|-----------------------|-------|-------------------|
| Unattached EBS vols   | 1     | $1.60             |
| Stopped EC2 instances | 0     | $0.00             |
| Idle Elastic IPs      | 0     | $0.00             |
| Untagged resources    | 0     | —                 |
| **TOTAL WASTE**       | **1** | **$1.60**         |

## Details

### Unattached EBS Volumes
- vol-xxxxxxxx | 16 GB | gp2 | us-east-1a | Est. $1.60/month
```

### report.json (example)

```json
{
  "scan_time": "2024-11-15T10:32:44Z",
  "orphans": [
    {
      "type": "ebs_volume",
      "id": "vol-xxxxxxxx",
      "size_gb": 16,
      "monthly_cost_usd": 1.60,
      "region": "us-east-1a"
    }
  ],
  "total_monthly_waste_usd": 1.60,
  "exit_code": 1
}
```

---

## Step 7 — CI/CD Pipeline (GitHub Actions)

The pipeline runs automatically on every Pull Request. Here's what happens end-to-end:

```
PR opened
    │
    ▼
.github/workflows/cost-janitor.yml triggered
    │
    ├── Start LocalStack 3.8.1
    ├── tflocal init + apply
    ├── python3 janitor.py --dry-run
    │
    ├── Orphans found (exit 1)?
    │       ├── ✗ Block PR merge
    │       └── Post report.md as PR comment
    │
    └── Clean (exit 0)?
            └── ✓ Allow merge
```

To test this yourself:

```bash
# Create a feature branch
git checkout -b test/my-feature

# Make any change
echo "# test" >> README.md
git add . && git commit -m "test: trigger CI"

# Push and open a PR on GitHub
git push origin test/my-feature
```

Then open a Pull Request on GitHub — the Actions tab will show the pipeline running. Because of the orphan EBS volume, it will block the merge and post a cost report comment.

---

## Step 8 — Cleanup

When done, stop and remove LocalStack:

```bash
docker stop localstack
docker rm localstack
```

Deactivate the Python virtual environment:

```bash
deactivate
```

---

## Troubleshooting

### LocalStack fails to start

```bash
# Check logs
docker logs localstack

# Common fix: port 4566 already in use
lsof -i :4566
kill -9 <PID>
```

### `tflocal: command not found`

```bash
# Make sure the venv is active and terraform-local is installed
source venv/bin/activate
pip install terraform-local
```

### GitHub Actions — "License activation failed! exit code 55"

This happens if the workflow uses `localstack:latest`. Fix:

```yaml
# .github/workflows/cost-janitor.yml
image: localstack/localstack:3.8.1   # Pin to 3.8.1, not latest
```

### Janitor exits with code 0 (no orphans found)

The orphan EBS volume may not have been created. Re-run:

```bash
cd terraform
tflocal apply -auto-approve
cd ../janitor
python3 janitor.py --dry-run --endpoint-url http://localhost:4566
```

### `boto3.exceptions.NoRegionError`

```bash
export AWS_DEFAULT_REGION=us-east-1
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
```

LocalStack accepts any dummy credentials.

---

## Quick Reference

| Command | What it does |
|---|---|
| `tflocal init` | Initialise Terraform with LocalStack endpoint |
| `tflocal plan` | Preview infrastructure changes |
| `tflocal apply -auto-approve` | Provision all resources |
| `tflocal destroy -auto-approve` | Tear down all resources |
| `python3 janitor.py --dry-run` | Scan for waste, no deletions |
| `docker logs localstack` | Debug LocalStack startup issues |
| `curl localhost:4566/_localstack/health` | Check LocalStack service status |

---

## What to Expect End-to-End

| Step | Expected Result |
|---|---|
| LocalStack health check | `"ec2": "running", "s3": "running"` |
| `tflocal apply` | 8 resources created, 0 errors |
| `janitor.py` scan | 1 orphan EBS found, exit code 1 |
| GitHub Actions PR | Merge blocked, cost report posted as comment |
| After cleanup | LocalStack stopped, no lingering Docker containers |
