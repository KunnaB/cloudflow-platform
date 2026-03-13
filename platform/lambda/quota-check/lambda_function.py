import json
import boto3

dynamodb = boto3.resource('dynamodb')
environments_table = dynamodb.Table('cloudflow-environments')
quotas_table = dynamodb.Table('cloudflow-team-quotas')

def lambda_handler(event, context):
    """
    Check if team has reached their quota limit
    """
    
    team_name = event.get('teamName')
    environment_type = event.get('environmentType')
    
    if not team_name or not environment_type:
        return {
            'statusCode': 400,
            'approved': False,
            'reason': 'Missing teamName or environmentType'
        }
    
    # Define quota limits
    quota_limits = {
        'dev': 3,
        'staging': 2,
        'prod': 1
    }
    
    limit = quota_limits.get(environment_type, 1)
    
    try:
        # Query how many environments this team already has
        response = environments_table.query(
            IndexName='team-index',
            KeyConditionExpression='teamName = :team',
            FilterExpression='environmentType = :env_type AND #status IN (:ready, :provisioning)',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':team': team_name,
                ':env_type': environment_type,
                ':ready': 'ready',
                ':provisioning': 'provisioning'
            }
        )
        
        current_count = response['Count']
        
        # Check if at limit
        if current_count >= limit:
            return {
                'statusCode': 200,
                'approved': False,
                'reason': f'Quota exceeded: {team_name} has {current_count}/{limit} {environment_type} environments',
                'currentCount': current_count,
                'limit': limit
            }
        
        # Approved
        return {
            'statusCode': 200,
            'approved': True,
            'reason': f'Within quota: {current_count}/{limit} {environment_type} environments',
            'currentCount': current_count,
            'limit': limit
        }
        
    except Exception as e:
        print(f"Error checking quota: {str(e)}")
        # Fail open
        return {
            'statusCode': 200,
            'approved': True,
            'reason': f'Quota check failed, approving anyway: {str(e)}',
            'warning': 'Quota validation unavailable'
        }
