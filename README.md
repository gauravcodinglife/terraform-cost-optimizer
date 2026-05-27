# Cloud Cost Hygiene Platform — Infrastructure Automation Project

A complete DevOps project that automatically detects and prevents cloud waste before it reaches production.

---

## 🎯 Project Overview

Built as a practical DevOps engineering assignment, this project demonstrates:
- **Infrastructure as Code** with Terraform on AWS (via LocalStack)
- **Cost optimization automation** using Python + boto3
- **CI/CD pipeline integration** with GitHub Actions
- **Real-world problem solving** — detecting orphaned resources that cost money

**Real-world context:** NimbusKart (e-commerce startup) saw their AWS bill jump from $400/month to $2,100/month due to forgotten resources. This project automates detection and prevention.

---

## 🏗️ What's Built

### Part 1 — Infrastructure as Code (Terraform)
Modular Terraform stack provisioning:
- VPC with 2 public subnets across 2 AZs
- Security groups (hardened SSH access)
- 2 EC2 instances (web tier)
- S3 bucket with versioning + lifecycle rules
- 1 intentional orphan EBS volume (for testing)

**Key decision:** Uses LocalStack (free AWS emulator) — zero real AWS costs.

### Part 2 — Cost Janitor (Python Automation)
Python script detecting 4 types of waste:
1. Unattached EBS volumes
2. Stopped EC2 instances (> 14 days)
3. Idle Elastic IPs
4. Untagged resources

**Outputs:**
- `report.json` — machine-readable findings
- `report.md` — human-readable cost summary

### Part 3 — CI/CD Enforcement (GitHub Actions)
Automated workflow that:
- Spins up LocalStack
- Applies Terraform infrastructure
- Runs cost scanner
- **Blocks PR merge** if orphans found
- Posts cost report as PR comment

---

## 🚀 How to Run

### Prerequisites
```bash
docker --version      # Docker
python3 --version    # Python 3.10+
terraform version    # Terraform
```

### Quick Start
```bash
# 1. Clone
git clone https://github.com/gauravcodinglife/terraform-cost-optimizer.git
cd terraform-cost-optimizer

# 2. Setup Python env
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r janitor/requirements.txt
pip install terraform-local

# 4. Start LocalStack (fake AWS)
docker run -d \
  --name localstack \
  -p 4566:4566 \
  -e SERVICES=ec2,s3,sts \
  -e DEFAULT_REGION=us-east-1 \
  localstack/localstack:3.8.1

sleep 20  # Wait for startup

# 5. Apply infrastructure
cd terraform
tflocal init
tflocal apply -auto-approve
cd ..

# 6. Run cost scanner
cd janitor
python3 janitor.py --dry-run --endpoint-url http://localhost:4566
cat report.md
```

**Expected output:**

Found: 1 unattached EBS volume
Estimated monthly waste: $1.60
Orphans found — exiting with code 1

---

## 📊 Key Features

### Modular Terraform
- Reusable `network/` module for VPC infrastructure
- Variables for easy customization
- Proper tagging (Project, Environment, Owner, ManagedBy)

### Smart Cost Detection
- Calculates estimated monthly waste per resource
- Respects `Protected=true` tag (never auto-deletes protected resources)
- Distinguishes safe vs unsafe deletions

### CI/CD Integration
- GitHub Actions workflow runs on every PR
- Blocks merge if waste found (safety net)
- Posts detailed cost report to PR

---

## 🔧 Technical Decisions

| Decision | Rationale |
|----------|-----------|
| LocalStack 3.8.1 (not latest) | Latest requires paid license; 3.8.1 is last free version |
| SSH restricted to 10.0.0.0/8 | Security: not 0.0.0.0/0 (internet-open) |
| EC2 never auto-deletes | Too risky without human approval |
| LaunchTime as age proxy | AWS doesn't expose stopped since timestamp |

---

## 🎓 Challenges & Solutions

### Challenge: LocalStack License Error
**Problem:** GitHub Actions pipeline failed with "License activation failed! exit code 55"

**Root Cause:** `localstack:latest` now requires paid license

**Solution:** Pinned to `localstack:3.8.1` (last free community version)

**Learning:** AI suggested `:latest`, but breaking changes happen. Reading logs is critical.

---

## 📈 Results

**What this demonstrates:**
- Can write modular, reusable infrastructure code
- Can build practical automation for real problems
- Can integrate security/cost controls into CI/CD
- Can debug production issues (reading logs, understanding errors)
- Can think beyond code (trade-offs, scaling, multi-cloud)

---

## 📁 Project Structure

├── terraform/              # Infrastructure as Code
│   ├── main.tf            # Root config
│   ├── variables.tf       # Inputs
│   ├── outputs.tf         # Outputs
│   └── modules/network/   # Reusable VPC module
├── janitor/               # Cost detection script
│   ├── janitor.py         # Main scanner
│   ├── constants.py       # AWS pricing
│   └── requirements.txt
├── .github/workflows/
│   └── cost-janitor.yml   # CI/CD pipeline
├── DESIGN.md              # Architecture doc
├── SUBMISSION.md          # Assignment checklist
└── README.md              # This file

---

## 🤖 AI Usage & Learning

### What Claude Helped With
- Terraform module structure and GitHub Actions workflow setup
- Python script scaffold with boto3 integration
- DESIGN.md architecture documentation

### What I Did Myself
- Debugged the LocalStack license error (code 55) by reading Docker logs
- Fixed terraform fmt errors and GitHub token scope issues
- Wrote scan_stopped_instances() function after discovering AWS API limitations
- Resolved git merge conflicts and tested entire workflow locally
- Made all security decisions (SSH restriction, no auto-delete EC2)

### Key Lesson
AI gave me 80% boilerplate code. The remaining 20% — debugging errors, making architecture decisions, fixing production issues — that's 100% human work.

---

## 🔗 Links

- **GitHub:** https://github.com/gauravcodinglife/terraform-cost-optimizer
- **LinkedIn:** https://linkedin.com/in/gaurav-chavan-codinglife
- **Blog:** https://medium.com/@codinggaurav85

---

## 📝 License

MIT — use this for learning and inspiration!

---

## 🙋 Contact

Email: codinggaurav85@gmail.com
Phone: +91-8530254513

---

**Built during #90DaysOfCloudDevOps challenge** 🚀
