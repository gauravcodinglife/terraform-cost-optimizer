# Submission — DevOps Engineer Assignment

**Candidate name:** Gaurav
**Email:** gauravcodinglife@gmail.com
**Date submitted:** 2026-05-25
**Hours spent (approximate):** 8

---

## Deliverables checklist

- [x] Part A: Terraform code under /terraform applies cleanly on LocalStack
- [x] Part A: `terraform validate` and `terraform fmt -check` both pass
- [x] Part B: Janitor script runs in --dry-run mode and produces report.json
- [x] Part B: GitHub Actions workflow runs green on a fresh PR
- [x] Part B: --delete mode respects Protected=true tag
- [x] Part C: DESIGN.md is present and within 2 pages

---

## Sample report

Path to a sample report.json produced by your script:
`samples/report.example.json`

---

## Known limitations

- **LocalStack version pinned to 3.8.1** — `localstack:latest` now
  requires a paid license (exits with code 55). Pinned to last free
  community version. Documented in Decisions & Deviations in README.md.
- **Stopped instance age uses LaunchTime as proxy** — AWS does not
  expose a "stopped since" timestamp. LaunchTime is used as a
  conservative lower bound. CloudTrail would give precision in production.
- **No remote Terraform state** — local state is fine for LocalStack.
  In production this would be S3 backend with DynamoDB locking.
- **EIP age always reported as 0** — AWS does not expose EIP allocation
  timestamps in the standard API.
- **No RDS or snapshot scanning** — scoped out to stay within time
  budget. The provider abstraction in DESIGN.md makes them easy to add.

---

## AI usage disclosure

### Tools used
- **Claude (Anthropic)** — primary assistant used throughout. Helped
  with Python janitor.py code, GitHub Actions workflow structure,
  DESIGN.md architecture sections, and debugging the LocalStack license
  error in CI.
- **Terraform** — I already had working knowledge of Terraform before
  this assignment. The module structure, variable conventions, and
  provider configuration were written with confidence. Claude helped
  with syntax and LocalStack-specific provider settings.
- **Official docs consulted** — Terraform AWS provider docs, LocalStack
  docs, GitHub Actions docs, boto3 API reference.

### What I actually did myself
- Wrote and structured the Terraform modules based on prior knowledge
- Debugged every CI error by reading raw logs myself:
  - GitHub token missing `workflow` scope
  - 674MB `.terraform/` folder exceeding GitHub file size limit
  - LocalStack license error (code 55) from Docker container logs
  - `terraform fmt` formatting failures
  - Container name conflict from Docker daemon
- Made every design decision in the Decisions & Deviations section
- Understood and can explain every line of code in this repo

### One thing AI got wrong
Claude suggested `localstack/localstack:latest` in the GitHub Actions
workflow. This failed because LocalStack's latest image now requires a
paid license. I caught it by reading the raw Docker logs in the Actions
tab. Fixed by pinning to `localstack:3.8.1`.

### One section written with prior knowledge
The entire Terraform stack — I already knew how VPCs, subnets, security
groups, and EC2 instances are structured in Terraform. Claude helped
with the LocalStack provider block and tagging conventions, but the
module structure and resource definitions came from prior experience.
