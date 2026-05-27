# DESIGN.md — Cloud Cost Hygiene Platform

## 1. Overview

The Cloud Cost Hygiene Platform is a DevOps automation project built to detect and prevent cloud resource waste before it reaches production. It was motivated by a real-world scenario: NimbusKart, a fictitious e-commerce startup, saw its AWS bill spike from $400/month to $2,100/month due to forgotten, idle, and untagged resources.

This platform addresses that problem with three integrated components: modular Infrastructure as Code (Terraform), a Python-based cost scanner (the "janitor"), and a CI/CD enforcement pipeline (GitHub Actions).

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────┐
│                  GitHub Actions CI/CD               │
│  ┌──────────┐   ┌────────────┐   ┌───────────────┐  │
│  │LocalStack│──▶│  Terraform │──▶│ Cost Janitor  │  │
│  │ (AWS emu)│   │  Apply     │   │  (Python)     │  │
│  └──────────┘   └────────────┘   └───────────────┘  │
│                                        │             │
│                              ┌─────────▼──────────┐  │
│                              │  PR Comment +       │  │
│                              │  Block/Allow Merge  │  │
│                              └────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

**Execution Flow:**
1. Developer opens a Pull Request
2. GitHub Actions spins up LocalStack (emulated AWS)
3. Terraform provisions the full infrastructure stack
4. Cost Janitor scans for orphaned/wasteful resources
5. If orphans are found → PR is blocked + report is posted as a comment
6. If clean → PR is allowed to merge

---

## 3. Component Design

### 3.1 Infrastructure as Code (Terraform)

**Structure:**
```
terraform/
├── main.tf           # Root config — wires modules together
├── variables.tf      # Configurable inputs (region, CIDR, tags)
├── outputs.tf        # Exported values (VPC ID, instance IPs)
└── modules/
    └── network/      # Reusable VPC module
        ├── main.tf
        ├── variables.tf
        └── outputs.tf
```

**What gets provisioned:**

| Resource | Count | Purpose |
|---|---|---|
| VPC | 1 | Isolated network boundary |
| Public Subnets | 2 | Spread across 2 AZs for resilience |
| Security Groups | 1 | Hardened SSH (10.0.0.0/8 only) |
| EC2 Instances | 2 | Web tier |
| S3 Bucket | 1 | Storage with versioning + lifecycle rules |
| EBS Volume (orphan) | 1 | Intentional — for testing the janitor |

**Key decisions:**

- SSH restricted to `10.0.0.0/8` (internal CIDR only) — never `0.0.0.0/0`
- All resources tagged with `Project`, `Environment`, `Owner`, `ManagedBy`
- `Protected=true` tag respected by the janitor (prevents auto-deletion)
- Uses `tflocal` CLI to point Terraform at LocalStack instead of real AWS

---

### 3.2 Cost Janitor (Python)

**File:** `janitor/janitor.py`

The janitor connects to AWS (or LocalStack) via `boto3` and scans for four categories of waste:

| Waste Type | Detection Logic | Estimated Cost |
|---|---|---|
| Unattached EBS volumes | State = `available` | ~$0.10/GB/month |
| Stopped EC2 instances | LaunchTime used as proxy for age (> 14 days) | Instance-type dependent |
| Idle Elastic IPs | Not associated with any running instance | $3.60/month each |
| Untagged resources | Missing required tags (`Project`, `Owner`) | Governance risk |

**Outputs:**
- `report.json` — machine-readable findings for programmatic use
- `report.md` — human-readable summary for PR comments

**Safety rules:**
- `--dry-run` flag: scans only, never deletes
- Resources tagged `Protected=true` are never touched
- EC2 instances are **never** auto-deleted (requires human approval)

**Design note on LaunchTime:** AWS does not expose a "stopped since" timestamp for EC2 instances. `LaunchTime` is used as a conservative proxy — a limitation acknowledged in the codebase.

---

### 3.3 CI/CD Pipeline (GitHub Actions)

**File:** `.github/workflows/cost-janitor.yml`

```
Trigger: Pull Request (opened, synchronize)
         ↓
Step 1: Start LocalStack 3.8.1
         ↓
Step 2: tflocal init + apply
         ↓
Step 3: Run janitor.py --dry-run
         ↓
Step 4a (orphans found): exit code 1 → block PR merge
         + post cost report as PR comment
Step 4b (clean):         exit code 0 → allow merge
```

**Why LocalStack 3.8.1 (not latest):**
The `localstack:latest` image now requires a paid license. Version `3.8.1` is the last freely available community release. This was discovered when the pipeline failed with exit code 55 ("License activation failed"). Pinning to `3.8.1` resolves the issue at zero cost.

---

## 4. Security Decisions

| Decision | Rationale |
|---|---|
| SSH to `10.0.0.0/8` only | Blocks internet-facing SSH; only internal VPN/bastion access |
| No auto-delete for EC2 | Destroying compute without human review is too risky |
| `Protected=true` tag respected | Allows teams to explicitly mark resources that must not be cleaned |
| Dry-run default | Janitor never destroys anything unless explicitly invoked without `--dry-run` |

---

## 5. Cost Model

The janitor estimates monthly waste using hardcoded pricing constants in `janitor/constants.py`:

```
Unattached EBS (gp2):     $0.10 / GB / month
Elastic IP (unattached):  $3.60 / month
Stopped EC2 (t3.micro):  ~$8.50 / month
```

These are us-east-1 on-demand approximations and serve as conservative floor estimates.

---

## 6. Project Structure

```
terraform-cost-optimizer/
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── modules/network/
├── janitor/
│   ├── janitor.py
│   ├── constants.py
│   └── requirements.txt
├── .github/workflows/
│   └── cost-janitor.yml
├── DESIGN.md          ← this file
├── SUBMISSION.md
└── README.md
```

---

## 7. Trade-offs & Limitations

| Trade-off | Notes |
|---|---|
| LocalStack vs real AWS | Zero cost, but some API behaviour differs from production AWS |
| LaunchTime as age proxy | Inaccurate for long-running instances that were later stopped |
| No auto-remediation | By design — automation identifies waste; humans act on it |
| Single-region scope | Scanner targets `us-east-1` only; multi-region support is a future enhancement |

---

## 8. Future Enhancements

- Multi-region scanning support
- Slack/email alerting on orphan detection
- Auto-remediation mode (with approval gate) for low-risk resources (EBS, EIPs)
- Cost trending over time (store reports in S3, visualise in Grafana)
- Support for RDS, NAT Gateways, and Load Balancers

---

## 9. References

- Terraform Registry — AWS Provider docs
- LocalStack documentation — https://docs.localstack.cloud
- boto3 EC2 API reference
- AWS EBS pricing — https://aws.amazon.com/ebs/pricing/
- GitHub Actions — https://docs.github.com/en/actions
