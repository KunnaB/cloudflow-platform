import json
import boto3
import os
from datetime import datetime, timedelta

ce_client = boto3.client('ce')
dynamodb = boto3.resource('dynamodb')

def lambda_handler(event, context):
    """
    Check if team is within budget before provisioning
    """
    
    # Extract team name from event
    team_name = event.get('teamName')
    environment_type = event.get('environmentType')
    
    if not team_name:
        return {
            'statusCode': 400,
            'approved': False,
            'reason': 'Missing teamName in request'
        }
    
    # Get team's budget from tags
    budget_limits = {
        'dev': 150,      # $150/month per dev account
        'staging': 400,  # $400/month per staging account
        'prod': 1200     # $1200/month per prod account
    }
    
    budget_limit = budget_limits.get(environment_type, 500)
    
    # Get current month's spend for team
    try:
        # Query Cost Explorer for team's current spend
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now().replace(day=1)).strftime('%Y-%m-%d')
        
        response = ce_client.get_cost_and_usage(
            TimePeriod={
                'Start': start_date,
                'End': end_date
            },
            Granularity='MONTHLY',
            Metrics=['UnblendedCost'],
            Filter={
                'Tags': {
                    'Key': 'Team',
                    'Values': [team_name]
                }
            }
        )
        
        # Extract current spend
        current_spend = 0
        if response['ResultsByTime']:
            current_spend = float(response['ResultsByTime'][0]['Total']['UnblendedCost']['Amount'])
        
        # Estimate new environment cost
        estimated_costs = {
            'dev': 40,
            'staging': 150,
            'prod': 350
        }
        
        new_env_cost = estimated_costs.get(environment_type, 100)
        projected_spend = current_spend + new_env_cost
        
        # Check if within budget
        if projected_spend > budget_limit:
            return {
                'statusCode': 200,
                'approved': False,
                'reason': f'Budget exceeded: Current ${current_spend:.2f} + New ${new_env_cost} = ${projected_spend:.2f} exceeds limit ${budget_limit}',
                'currentSpend': current_spend,
                'projectedSpend': projected_spend,
                'budgetLimit': budget_limit
            }
        
        # Approved
        return {
            'statusCode': 200,
            'approved': True,
            'reason': f'Within budget: ${projected_spend:.2f} of ${budget_limit}',
            'currentSpend': current_spend,
            'projectedSpend': projected_spend,
            'budgetLimit': budget_limit
        }
        
    except Exception as e:
        print(f"Error checking budget: {str(e)}")
        # Fail open - approve if we can't check (prevents blocking)
        return {
            'statusCode': 200,
            'approved': True,
            'reason': f'Budget check failed, approving anyway: {str(e)}',
            'warning': 'Budget validation unavailable'
        }
