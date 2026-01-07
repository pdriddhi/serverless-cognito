import json
import boto3
import os

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['MEMBERS_TABLE'])

def lambda_handler(event, context):
    try:
        # Get user_id from path parameters
        if 'pathParameters' not in event or 'user_id' not in event['pathParameters']:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'user_id is required in path parameters'})
            }
            
        user_id = event['pathParameters']['user_id']
        
        # Check if member exists
        existing_member = table.get_item(Key={'user_id': user_id})
        if 'Item' not in existing_member:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Member not found'})
            }
        
        # Delete the member
        table.delete_item(Key={'user_id': user_id})
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Member deleted successfully',
                'user_id': user_id
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }