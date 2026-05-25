# janitor/constants.py
# Pricing constants used for waste cost estimates.
# Sources:
#   EBS: https://aws.amazon.com/ebs/pricing/ (us-east-1, as of 2025)
#   EC2: https://aws.amazon.com/ec2/pricing/on-demand/ (us-east-1, t3.micro)
#   EIP: https://aws.amazon.com/vpc/pricing/ — idle EIP costs $0.005/hr = ~$3.60/mo

# EBS cost per GB per month (gp3)
EBS_GP3_COST_PER_GB_MONTH = 0.08   # USD

# EBS cost per GB per month (gp2)
EBS_GP2_COST_PER_GB_MONTH = 0.10   # USD

# Default EBS size assumption when size is unknown
EBS_DEFAULT_SIZE_GB = 20

# EC2 t3.micro on-demand per hour
EC2_T3_MICRO_PER_HOUR = 0.0104     # USD
EC2_HOURS_PER_MONTH   = 730        # 365 days * 24 / 12

# Elastic IP idle cost per month
EIP_IDLE_COST_PER_MONTH = 3.60     # USD

# Required tags every resource must carry
REQUIRED_TAGS = ["Project", "Environment", "Owner"]

# Resources tagged Protected=true are never auto-deleted
PROTECTED_TAG_KEY   = "Protected"
PROTECTED_TAG_VALUE = "true"
