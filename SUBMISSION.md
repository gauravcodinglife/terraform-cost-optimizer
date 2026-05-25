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
- [ ] Walkthrough video link below is accessible (unlisted is fine)

---

## Walkthrough video

Link (Loom / YouTube unlisted / Google Drive): _To be recorded and added_
Length: max 5 minutes

---

## Sample report

Path to a sample report.json produced by your script:
`samples/report.example.json`

---

## Known limitations

- **LocalStack version pinned to 3.8.1** — `localstack:latest` now requires a paid license (exits with code 55: "License activation failed"). Pinned to last free community version. This is documented in Decisions & Deviations in README.md.
- **Stopped instance age uses LaunchTime as proxy** — AWS `describe_instances` does not expose a "stopped since" timestamp. We use `LaunchTime` as a conservative lower bound. In production, CloudTrail or CloudWatch Events would give the precise stop timestamp.
- **No remote Terraform state** — state is stored locally. In production this would be an S3 backend with DynamoDB locking.
- **EIP age always reported as 0** — AWS does not expose EIP allocation timestamps in the standard API. The field is present in the report schema but always 0.
- **No RDS or snapshot scanning** — these are major cost drivers but were scoped out to stay within the time budget. The provider abstraction in DESIGN.md makes them straightforward to add.
- **Walkthrough video** — to be recorded showing: LocalStack startup, terraform apply, janitor dry-run, one finding walkthrough, one design decision, one thing to change.

---

## AI usage disclosure

### Tools used
- **Claude (Anthropic)** — Terraform module structure, janitor.py scaffold, GitHub Actions yml, DESIGN.md, debugging LocalStack license error.
- **GitHub Copilot** — inline autocompletion for Python helper functions.

### One thing AI got wrong
Claude suggested using `localstack/localstack:latest` in the GitHub Actions workflow. This failed because LocalStack's latest image now requires a paid license and exits with code 55. I caught this by reading the raw Docker container logs in the Actions tab which showed `License activation failed`. Fixed by pinning to `localstack:3.8.1`.

### One section written without AI
The `scan_stopped_instances()` function — specifically the decision to use `LaunchTime` as a proxy for "stopped since" and documenting that limitation honestly, rather than over-engineering a CloudTrail solution. AI suggested CloudTrail; I chose the simpler approach with clear documentation.
