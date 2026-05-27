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
