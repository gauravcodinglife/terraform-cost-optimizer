# Cost Janitor Report

**Scan time:** 2026-05-25T04:01:31Z
**Account:** 000000000000
**Region:** us-east-1

## Summary

| Metric | Value |
|--------|-------|
| Total orphans found | 3 |
| Estimated monthly waste | $1.60 |

## Findings

| Resource ID | Type | Reason | Age (days) | Est. Cost/mo | Safe to Delete |
|-------------|------|--------|------------|--------------|----------------|
| vol-c3839194 | ebs_volume | unattached | 0 | $1.60 | ⚠️ No |
| vol-87a5743a | ebs_volume | missing tags: Project, Environment, Owner | 0 | $0.00 | ⚠️ No |
| vol-098c372c | ebs_volume | missing tags: Project, Environment, Owner | 0 | $0.00 | ⚠️ No |
