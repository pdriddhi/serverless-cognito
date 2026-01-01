import json
import boto3
import os

dynamodb = boto3.resource('dynamodb')
unit_maintenance_table = dynamodb.Table(os.environ['TABLE_UNIT_MAINTENANCE'])
users_table = dynamodb.Table(os.environ['USERS_TABLE'])

def lambda_handler(event, context):
    try:
        unit_maintenance_id = event['pathParameters']['unit_maintenance_id']
        
        # Get query params for user validation
        query_params = event.get('queryStringParameters', {}) or {}
        user_id = query_params.get('user_id')
        
        if user_id:
            # Validate user
            user_response = users_table.get_item(Key={'user_id': user_id})
            if 'Item' not in user_response:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'User not found'})
                }
        
        # Check if exists
        existing = unit_maintenance_table.get_item(Key={'unit_maintenance_id': unit_maintenance_id})
        if 'Item' not in existing:
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'Not found'})
            }
        
        # Delete
        unit_maintenance_table.delete_item(Key={'unit_maintenance_id': unit_maintenance_id})
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'message': 'Deleted successfully',
                'unit_maintenance_id': unit_maintenance_id
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
