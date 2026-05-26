# NimbusKart Cloud Cost Hygiene Platform

A complete DevOps solution that automatically detects and prevents cloud waste before it reaches production.

---

## 🎯 Problem Statement

NimbusKart, an e-commerce startup, saw their AWS bill jump from **$400/month to $2,100/month** in one quarter due to:
- Unattached EBS volumes (forgotten storage)
- EC2 instances stopped for weeks but still billing for disks
- Idle Elastic IPs nobody was using
- Untagged dev resources that couldn't be attributed to any team

**This project solves that problem with automated detection + CI/CD enforcement.**

---

## 🏗️ What This Does

### Part A — Infrastructure as Code
Modular Terraform stack that provisions:
- VPC with 2 public subnets across 2 availability zones
- Security groups with restricted SSH access
- 2 EC2 instances (web tier)
- S3 bucket with versioning + lifecycle rules
- **1 intentional orphan EBS volume** (for testing detection)

All running on **LocalStack** — a free local AWS emulator. Zero real AWS costs.

### Part B — Cost Janitor (Python Automation)
Python script that scans for 4 types of waste:
1. **Unattached EBS volumes** — storage sitting idle
2. **Stopped EC2 instances** — stopped > 14 days (still paying for disks)
3. **Idle Elastic IPs** — reserved but not in use
4. **Missing required tags** — can't attribute cost without tags

Outputs:
- `report.json` — machine-readable findings
- `report.md` — human-readable summary with cost estimates

### Part C — CI/CD Pipeline (GitHub Actions)
Every Pull Request automatically:
1. Spins up LocalStack in Docker
2. Applies Terraform
3. Runs the Cost Janitor
4. **Blocks the merge** if orphans are found
5. Posts a cost report as a PR comment
6. Uploads `report.json` and `report.md` as downloadable artifacts

---

## 🚀 Quick Start (5 minutes)

### Prerequisites
- Docker installed and running
- Python 3.10+
- Terraform installed

### Run It Locally

```bash
# 1. Clone
git clone https://github.com/gauravcodinglife/terraform-cost-optimizer.git
cd terraform-cost-optimizer

# 2. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install Python dependencies
pip install -r janitor/requirements.txt
pip install terraform-local

# 4. Start LocalStack (local AWS emulator)
docker run -d \
  --name localstack \
  -p 4566:4566 \
  -e SERVICES=ec2,s3,sts \
  -e DEFAULT_REGION=us-east-1 \
  localstack/localstack:3.8.1

# Wait 20 seconds for it to start
sleep 20

# 5. Apply Terraform
cd terraform
tflocal init
tflocal apply -auto-approve

# You'll see outputs:
# - VPC ID
# - 2 subnet IDs
# - 2 EC2 instance IDs
# - S3 bucket name
# - Orphan EBS volume ID ← this is what janitor will find

# 6. Run Cost Janitor
cd ../janitor
python3 janitor.py --dry-run --endpoint-url http://localhost:4566

# 7. View the reports
cat report.md   # Human-readable
cat report.json # Machine-readable
```

**Expected output:**
```
🔍 Scanning for unattached EBS volumes...
   Found: 1   ← the intentional orphan

Total orphans: 1
Estimated monthly waste: $1.60

⚠️  Orphans found — exiting with code 1 (CI will flag this PR)
```

---

## 📊 How the CI Pipeline Works

```
Developer opens PR
       ↓
GitHub Actions workflow triggers
       ↓
┌─────────────────────────────────────┐
│ Step 1: Start LocalStack container  │
│ Step 2: terraform init + apply      │ ← Creates the orphan EBS
│ Step 3: Run janitor in dry-run      │ ← Finds the orphan
│ Step 4: Upload report artifacts     │
│ Step 5: Post PR comment if orphans  │
│ Step 6: exit 1 → BLOCK THE MERGE   │ ← The safety net
└─────────────────────────────────────┘
```

### Why Does the Pipeline Show Red? ❌

**This is intentional.**

The workflow exits with code 1 when orphans are found. This **blocks the PR from merging** until the waste is cleaned up.

Think of it like a smoke alarm:
- ✅ Green pipeline = no waste found = safe to merge
- ❌ Red pipeline = orphans detected = fix before merging

The red "failure" IS the feature — it prevents $1,700/month of waste from reaching production.

---

## 🏛️ Architecture

### File Structure
```
terraform-cost-optimizer/
├── terraform/
│   ├── main.tf                 # Root config: EC2, S3, EBS
│   ├── variables.tf            # All configurable values
│   ├── outputs.tf              # VPC ID, subnet IDs, bucket name
│   └── modules/
│       └── network/            # Reusable VPC module
│           ├── main.tf         # VPC, subnets, security group
│           ├── variables.tf
│           └── outputs.tf
├── janitor/
│   ├── janitor.py              # Main scanner script
│   ├── constants.py            # AWS pricing data
│   └── requirements.txt
├── .github/workflows/
│   └── cost-janitor.yml        # CI/CD pipeline
├── DESIGN.md                   # Production architecture doc
├── SUBMISSION.md               # Assignment submission checklist
└── README.md                   # You are here
```

### Flow Diagram
```
┌─────────────────────────────────────────────────────────┐
│             GitHub Actions (on every PR)                 │
│                                                          │
│  LocalStack    →    Terraform    →    Cost Janitor      │
│  (fake AWS)         (creates infra)   (finds waste)     │
│                                                          │
│  Outputs:                                                │
│  - report.json                                           │
│  - report.md                                             │
│  - PR comment (if orphans found)                         │
│  - exit 1 to block merge ✋                              │
└─────────────────────────────────────────────────────────┘
```

---

## 🔧 Key Technical Decisions

### Why LocalStack 3.8.1 (not latest)?
`localstack:latest` now requires a paid license. Version 3.8.1 is the last free community release.

### Why is SSH restricted to 10.0.0.0/8 (not 0.0.0.0/0)?
The assignment spec said default to `0.0.0.0/0` (open to the internet). This is a **critical security flaw**. I changed it to a private network range and made it configurable via `variables.tf`.

### Why do EC2 instances never auto-delete?
Even in `--delete` mode, the janitor only **reports** stopped instances — never terminates them. Deleting compute automatically is too risky without human approval.

### Why use LaunchTime as a proxy for "stopped since"?
AWS doesn't expose a "stopped since" timestamp in the standard API. We use `LaunchTime` as a conservative estimate. In production, you'd use CloudTrail for precision.

---

## 🎓 What I Learned

### Real Problem I Hit
The GitHub Actions pipeline kept failing with:
```
License activation failed! 🔑❌
LocalStack returning with exit code 55
```

**Root cause:** LocalStack's latest Docker image now requires a paid license (changed in May 2026).

**How I fixed it:** Read the raw container logs in the Actions tab, identified the exact error, pinned the image to `localstack:3.8.1` (last free version).

**Lesson:** AI tools suggested `latest` — but breaking changes happen. Reading logs and debugging is still 100% human work.

### Trade-offs I Made
Given more time, I would add:
- Remote Terraform state (S3 + DynamoDB locking)
- Multi-account scanning with `sts:AssumeRole`
- Snapshot-before-delete safety net
- Slack/PagerDuty notifications for FinOps team
- RDS and EBS snapshot scanning
- CloudWatch metrics publishing

---

## 🤖 AI Usage (Full Transparency)

### What AI Helped With
- **Claude (Anthropic):** Terraform module structure, Python script scaffold, GitHub Actions workflow, DESIGN.md architecture sections
- **GitHub Copilot:** Inline autocompletion for helper functions

### What AI Got Wrong
Claude suggested `localstack/localstack:latest` in the workflow. This broke because the latest image requires a paid license. I caught it by reading Docker logs.

### What I Did Without AI
- Debugged every CI error by reading raw logs
- Made all architectural decisions (SSH restriction, no auto-terminate EC2, LaunchTime proxy)
- The `scan_stopped_instances()` function — wrote it manually after realizing AWS doesn't expose "stopped since" timestamps

---

## 📈 Results

**Before this solution:**
- Orphaned resources pile up silently
- Bills grow month after month
- Nobody knows what resources belong to which team

**After this solution:**
- Every PR is scanned automatically
- Waste is blocked before merge
- Cost reports show exactly what's orphaned and how much it costs
- Developers fix waste proactively

---

## 🔗 Links

- **GitHub Repo:** https://github.com/gauravcodinglife/terraform-cost-optimizer
- **DESIGN.md:** Full production architecture (multi-cloud, IAM policies, failure modes, metrics)
- **SUBMISSION.md:** Assignment checklist and deliverables

---

## 📜 License

MIT License — feel free to use this for your own cost optimization projects!

---

## 🙋 Questions?

Open an issue or reach out:
- Email: gauravcodinglife@gmail.com
- LinkedIn: [https://www.linkedin.com/in/gaurav-chavan-codinglife/]

---

**Built as part of #90DaysOfCloudDevOps challenge**
