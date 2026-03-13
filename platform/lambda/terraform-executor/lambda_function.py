import json
import boto3
import uuid
import time
from datetime import datetime

ec2 = boto3.client('ec2')
rds = boto3.client('rds')
s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
environments_table = dynamodb.Table('cloudflow-environments')

def lambda_handler(event, context):
    team_name = event.get('teamName')
    environment_type = event.get('environmentType')
    app_name = event.get('appName')
    requested_by = event.get('requestedBy')
    
    environment_id = f"env-{uuid.uuid4().hex[:8]}"
    
    try:
        # Create environment record
        environments_table.put_item(Item={
            'environmentId': environment_id,
            'teamName': team_name,
            'environmentType': environment_type,
            'appName': app_name,
            'requestedBy': requested_by or 'unknown',
            'status': 'provisioning',
            'createdAt': int(datetime.now().timestamp())
        })
        
        # 1. CREATE VPC
        vpc_response = ec2.create_vpc(
            CidrBlock='10.0.0.0/16',
            TagSpecifications=[{
                'ResourceType': 'vpc',
                'Tags': [
                    {'Key': 'Name', 'Value': f'{team_name}-{environment_type}-{app_name}-vpc'},
                    {'Key': 'Team', 'Value': team_name},
                    {'Key': 'Environment', 'Value': environment_type},
                    {'Key': 'Project', 'Value': 'CloudFlow'},
                    {'Key': 'EnvironmentId', 'Value': environment_id}
                ]
            }]
        )
        vpc_id = vpc_response['Vpc']['VpcId']
        ec2.modify_vpc_attribute(VpcId=vpc_id, EnableDnsHostnames={'Value': True})
        ec2.modify_vpc_attribute(VpcId=vpc_id, EnableDnsSupport={'Value': True})
        
        # 2. CREATE INTERNET GATEWAY
        igw_response = ec2.create_internet_gateway(
            TagSpecifications=[{
                'ResourceType': 'internet-gateway',
                'Tags': [{'Key': 'Name', 'Value': f'{team_name}-{environment_type}-igw'}]
            }]
        )
        igw_id = igw_response['InternetGateway']['InternetGatewayId']
        ec2.attach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
        
        # 3. CREATE SUBNETS
        # Public subnet
        public_subnet = ec2.create_subnet(
            VpcId=vpc_id,
            CidrBlock='10.0.1.0/24',
            AvailabilityZone='us-east-1a',
            TagSpecifications=[{
                'ResourceType': 'subnet',
                'Tags': [{'Key': 'Name', 'Value': f'{team_name}-{environment_type}-public-1a'}]
            }]
        )
        public_subnet_id = public_subnet['Subnet']['SubnetId']
        
        # Private app subnet
        private_app_subnet = ec2.create_subnet(
            VpcId=vpc_id,
            CidrBlock='10.0.11.0/24',
            AvailabilityZone='us-east-1a',
            TagSpecifications=[{
                'ResourceType': 'subnet',
                'Tags': [{'Key': 'Name', 'Value': f'{team_name}-{environment_type}-private-app-1a'}]
            }]
        )
        private_app_subnet_id = private_app_subnet['Subnet']['SubnetId']
        
        # Private DB subnet 1
        private_db_subnet_1 = ec2.create_subnet(
            VpcId=vpc_id,
            CidrBlock='10.0.21.0/24',
            AvailabilityZone='us-east-1a',
            TagSpecifications=[{
                'ResourceType': 'subnet',
                'Tags': [{'Key': 'Name', 'Value': f'{team_name}-{environment_type}-private-db-1a'}]
            }]
        )
        private_db_subnet_1_id = private_db_subnet_1['Subnet']['SubnetId']
        
        # Private DB subnet 2 (RDS requires 2 AZs)
        private_db_subnet_2 = ec2.create_subnet(
            VpcId=vpc_id,
            CidrBlock='10.0.22.0/24',
            AvailabilityZone='us-east-1b',
            TagSpecifications=[{
                'ResourceType': 'subnet',
                'Tags': [{'Key': 'Name', 'Value': f'{team_name}-{environment_type}-private-db-1b'}]
            }]
        )
        private_db_subnet_2_id = private_db_subnet_2['Subnet']['SubnetId']
        
        # 4. CREATE NAT GATEWAY
        # Allocate Elastic IP
        eip_response = ec2.allocate_address(Domain='vpc')
        eip_id = eip_response['AllocationId']
        
        nat_response = ec2.create_nat_gateway(
            SubnetId=public_subnet_id,
            AllocationId=eip_id,
            TagSpecifications=[{
                'ResourceType': 'natgateway',
                'Tags': [{'Key': 'Name', 'Value': f'{team_name}-{environment_type}-nat'}]
            }]
        )
        nat_id = nat_response['NatGateway']['NatGatewayId']
        
        # Wait for NAT Gateway to be available
        time.sleep(30)
        
        # 5. CREATE ROUTE TABLES
        # Public route table
        public_rt = ec2.create_route_table(
            VpcId=vpc_id,
            TagSpecifications=[{
                'ResourceType': 'route-table',
                'Tags': [{'Key': 'Name', 'Value': f'{team_name}-{environment_type}-public-rt'}]
            }]
        )
        public_rt_id = public_rt['RouteTable']['RouteTableId']
        
        ec2.create_route(
            RouteTableId=public_rt_id,
            DestinationCidrBlock='0.0.0.0/0',
            GatewayId=igw_id
        )
        
        ec2.associate_route_table(RouteTableId=public_rt_id, SubnetId=public_subnet_id)
        
        # Private route table
        private_rt = ec2.create_route_table(
            VpcId=vpc_id,
            TagSpecifications=[{
                'ResourceType': 'route-table',
                'Tags': [{'Key': 'Name', 'Value': f'{team_name}-{environment_type}-private-rt'}]
            }]
        )
        private_rt_id = private_rt['RouteTable']['RouteTableId']
        
        ec2.create_route(
            RouteTableId=private_rt_id,
            DestinationCidrBlock='0.0.0.0/0',
            NatGatewayId=nat_id
        )
        
        ec2.associate_route_table(RouteTableId=private_rt_id, SubnetId=private_app_subnet_id)
        
        # 6. CREATE SECURITY GROUPS
        # EC2 security group
        ec2_sg = ec2.create_security_group(
            GroupName=f'{team_name}-{environment_type}-ec2-sg',
            Description='Security group for EC2 instances',
            VpcId=vpc_id,
            TagSpecifications=[{
                'ResourceType': 'security-group',
                'Tags': [{'Key': 'Name', 'Value': f'{team_name}-{environment_type}-ec2-sg'}]
            }]
        )
        ec2_sg_id = ec2_sg['GroupId']
        
        ec2.authorize_security_group_ingress(
            GroupId=ec2_sg_id,
            IpPermissions=[
                {'IpProtocol': 'tcp', 'FromPort': 80, 'ToPort': 80, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                {'IpProtocol': 'tcp', 'FromPort': 443, 'ToPort': 443, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
            ]
        )
        
        # RDS security group
        rds_sg = ec2.create_security_group(
            GroupName=f'{team_name}-{environment_type}-rds-sg',
            Description='Security group for RDS',
            VpcId=vpc_id,
            TagSpecifications=[{
                'ResourceType': 'security-group',
                'Tags': [{'Key': 'Name', 'Value': f'{team_name}-{environment_type}-rds-sg'}]
            }]
        )
        rds_sg_id = rds_sg['GroupId']
        
        ec2.authorize_security_group_ingress(
            GroupId=rds_sg_id,
            IpPermissions=[
                {'IpProtocol': 'tcp', 'FromPort': 3306, 'ToPort': 3306, 
                 'UserIdGroupPairs': [{'GroupId': ec2_sg_id}]}
            ]
        )
        
        # 7. CREATE RDS SUBNET GROUP
        rds.create_db_subnet_group(
            DBSubnetGroupName=f'{team_name}-{environment_type}-db-subnet-group',
            DBSubnetGroupDescription='Subnet group for RDS',
            SubnetIds=[private_db_subnet_1_id, private_db_subnet_2_id],
            Tags=[
                {'Key': 'Name', 'Value': f'{team_name}-{environment_type}-db-subnet-group'},
                {'Key': 'EnvironmentId', 'Value': environment_id}
            ]
        )
        
        # 8. CREATE S3 BUCKET
        bucket_name = f'{team_name.lower()}-{environment_type}-{app_name.lower()}-{environment_id}'
        s3.create_bucket(Bucket=bucket_name)
        s3.put_bucket_tagging(
            Bucket=bucket_name,
            Tagging={'TagSet': [
                {'Key': 'Team', 'Value': team_name},
                {'Key': 'Environment', 'Value': environment_type},
                {'Key': 'EnvironmentId', 'Value': environment_id}
            ]}
        )
        
        # Update DynamoDB with all resource IDs
        environments_table.update_item(
            Key={'environmentId': environment_id},
            UpdateExpression='SET #status = :status, vpcId = :vpc, publicSubnet = :pub_sub, privateAppSubnet = :priv_app, privateDbSubnet1 = :priv_db1, privateDbSubnet2 = :priv_db2, natGatewayId = :nat, ec2SecurityGroup = :ec2_sg, rdsSecurityGroup = :rds_sg, s3Bucket = :s3',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': 'ready',
                ':vpc': vpc_id,
                ':pub_sub': public_subnet_id,
                ':priv_app': private_app_subnet_id,
                ':priv_db1': private_db_subnet_1_id,
                ':priv_db2': private_db_subnet_2_id,
                ':nat': nat_id,
                ':ec2_sg': ec2_sg_id,
                ':rds_sg': rds_sg_id,
                ':s3': bucket_name
            }
        )
        
        return {
            'statusCode': 200,
            'success': True,
            'environmentId': environment_id,
            'vpcId': vpc_id,
            's3Bucket': bucket_name,
            'message': 'Full dev environment provisioned successfully'
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        
        try:
            environments_table.update_item(
                Key={'environmentId': environment_id},
                UpdateExpression='SET #status = :status, errorMessage = :error',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':status': 'failed',
                    ':error': str(e)
                }
            )
        except:
            pass
        
        return {
            'statusCode': 500,
            'success': False,
            'reason': str(e)
        }
