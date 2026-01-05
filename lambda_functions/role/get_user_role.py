import json
import boto3
import os

dynamodb = boto3.resource('dynamodb')
BUILDING_MEMBERS_TABLE = os.environ['BUILDING_MEMBERS_TABLE']

def lambda_handler(event, context):
    query_params = event.get('queryStringParameters') or {}
    
    building_id = query_params.get('building_id')
    user_id = query_params.get('user_id')
    
    if not building_id or not user_id:
        return {
            'statusCode': 400,
            'body': json.dumps({
                'success': False,
                'message': 'building_id and user_id are required'
            })
        }
    
    table = dynamodb.Table(BUILDING_MEMBERS_TABLE)
    
    response = table.get_item(
        Key={
            'building_id': building_id,
            'user_id': user_id
        }
    )
    
    if 'Item' in response:
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'role': response['Item'].get('role'),
                'user_id': user_id,
                'building_id': building_id
            })
        }
    else:
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'role': 'none',  # Not a member
                'user_id': user_id,
                'building_id': building_id
            })
        }