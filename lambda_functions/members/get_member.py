import json
import boto3
from boto3.dynamodb.conditions import Key
import os

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['MEMBERS_TABLE'])

def lambda_handler(event, context):
    try:
        # Check if specific user_id is provided in path parameters
        if 'pathParameters' in event and event['pathParameters'] and 'user_id' in event['pathParameters']:
            user_id = event['pathParameters']['user_id']
            
            # Get single member
            response = table.get_item(
                Key={'user_id': user_id}
            )
            
            if 'Item' not in response:
                return {
                    'statusCode': 404,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({'error': 'Member not found'})
                }
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps(response['Item'])
            }
        
        # Get all members or filter by query parameters
        query_params = event.get('queryStringParameters', {}) or {}
        
        if 'building_id' in query_params:
            # Query by building_id using GSI
            response = table.query(
                IndexName='building-index',
                KeyConditionExpression=Key('building_id').eq(query_params['building_id'])
            )
            members = response.get('Items', [])
        else:
            # Scan for all members
            response = table.scan()
            members = response.get('Items', [])
            
            # Handle pagination
            while 'LastEvaluatedKey' in response:
                response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
                members.extend(response.get('Items', []))
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'members': members,
                'count': len(members)
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