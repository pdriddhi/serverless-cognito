import json
import boto3
from boto3.dynamodb.conditions import Key
import os
from decimal import Decimal

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            if obj % 1 == 0:
                return int(obj)
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['MEMBERS_TABLE'])

def lambda_handler(event, context):
    try:
        if 'pathParameters' in event and event['pathParameters'] and 'user_id' in event['pathParameters']:
            user_id = event['pathParameters']['user_id']
            
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
                'body': json.dumps(response['Item'], cls=DecimalEncoder)
            }
        
        query_params = event.get('queryStringParameters', {}) or {}
        
        if 'building_id' in query_params:
            response = table.query(
                IndexName='building-index',
                KeyConditionExpression=Key('building_id').eq(query_params['building_id'])
            )
            members = response.get('Items', [])
        else:
            response = table.scan()
            members = response.get('Items', [])
            
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
            }, cls=DecimalEncoder)
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