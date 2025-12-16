import json
import boto3
import os

# Initialize DynamoDB with correct table names
dynamodb = boto3.resource('dynamodb')

# Use environment-specific table names
def get_table_name(base_name):
    env = os.environ.get('ENVIRONMENT', 'dev')
    return f"{base_name}-{env}"

# Table references with correct names
Buildings = dynamodb.Table(get_table_name('Buildings'))
UserUnits = dynamodb.Table(get_table_name('UserUnits'))
Users = dynamodb.Table(get_table_name('Users'))
SuperAdmins = dynamodb.Table(get_table_name('SuperAdmins'))

# Simplified token validation
def get_user_from_token(event):
    """
    Simple token validation - for now, accept any request
    In production, implement proper JWT validation
    """
    try:
        # For testing, accept all requests
        return {
            'username': 'test-user',
            'user_id': 'test-001',
            'role': 'admin'
        }, None
    except Exception as e:
        print(f"Token validation error: {e}")
        return None, {
            'statusCode': 401,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Authentication failed'})
        }
