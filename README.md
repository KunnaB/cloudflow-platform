# CloudFlow Platform

**Self-service AWS infrastructure automation platform**

Reduces environment provisioning from 2-3 days to 3 minutes with automated approval workflows, cost controls, and governance.

## Architecture

![CloudFlow Platform Architecture](cloudflow-architecture.png)

## Overview

CloudFlow automates AWS environment provisioning with built-in approval workflows, budget enforcement, and quota management. Teams request environments via AWS Service Catalog, and the platform automatically provisions complete 3-tier VPC infrastructure in minutes.

## Components

### Platform Services
- **AWS Service Catalog**: Self-service portal for environment requests
- **AWS Step Functions**: Orchestrates approval workflow
- **AWS Lambda Functions**:
  - `budget-check`: Validates team spending against monthly limits
  - `quota-check`: Enforces environment quotas per team
  - `terraform-executor`: Provisions complete VPC infrastructure
- **Amazon DynamoDB**: Tracks all provisioned environments
- **Amazon SNS**: Sends notifications for approvals and completions
- **Amazon S3**: Stores Terraform modules and state

### Infrastructure Provisioned Per Environment
- VPC with 3-tier architecture (10.0.0.0/16)
- Internet Gateway + NAT Gateway with Elastic IP
- 4 Subnets across 2 Availability Zones
- Route tables with proper routing configuration
- Security groups for EC2 and RDS
- RDS subnet group (Multi-AZ ready)
- S3 bucket for application data

## Key Features

✅ **Self-Service Portal** - Teams request via AWS Service Catalog  
✅ **Automated Approval** - Budget and quota checks via Step Functions  
✅ **Instant Provisioning** - Complete infrastructure in ~3 minutes  
✅ **Cost Controls** - Budget limits and team quotas enforced  
✅ **Resource Tracking** - DynamoDB records all provisioned resources  
✅ **Notifications** - SNS alerts for approvals and completions  

## Quick Start

### Prerequisites
- AWS Account with AWS Organizations
- Terraform >= 1.0
- AWS CLI configured

### Deploy Platform
```bash
cd platform/terraform
terraform init
terraform apply
```

### Request Environment

1. Navigate to AWS Service Catalog
2. Select "Dev Environments" portfolio
3. Launch "Dev Environment" product
4. Provide: TeamName, AppName, RequestedBy
5. Wait ~3 minutes for provisioning

## Technical Details

**Budget Limits:**
- Dev: $150/month per account
- Staging: $400/month per account
- Prod: $1,200/month per account

**Quota Limits:**
- Dev: 3 environments per team
- Staging: 2 environments per team
- Prod: 1 environment per team

**Lambda Runtime:** Python 3.11  
**Region:** us-east-1  
**Provisioning Time:** ~3 minutes  

## Cost Analysis

**Platform Infrastructure:** ~$5/month
- DynamoDB on-demand
- Lambda pay-per-use
- S3 storage
- SNS notifications

**Per Environment:** ~$40/month
- NAT Gateway: $32/month
- Data transfer: ~$5/month
- VPC/Subnets/IGW: Free

## Results

**Efficiency:** Environment provisioning reduced from 2-3 days to 3 minutes (99% reduction)  
**Cost Savings:** Automated cost controls and quota enforcement  
**Consistency:** Standardized infrastructure across all environments  
**Auditability:** Complete tracking in DynamoDB with SNS notifications  

## Author

**Akunna Ndubuisi**  
Solutions Architect | AWS Certified  
Built as demonstration of production-grade infrastructure automation

## License

MIT License
