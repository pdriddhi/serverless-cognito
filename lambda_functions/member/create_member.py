import json
import boto3
from datetime import datetime
import os

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['MEMBERS_TABLE'])
users_table = dynamodb.Table(os.environ['USERS_TABLE'])

def validate_user(user_id):
    """
    Check if user exists in Users table
    """
    try:
        response = users_table.get_item(Key={'user_id': user_id})
        return 'Item' in response
    except Exception as e:
        print(f"Error validating user {user_id}: {str(e)}")
        return False

def lambda_handler(event, context):
    try:
        body = json.loads(event['body'])
        
        required_fields = ['user_id', 'building_id', 'name', 'mobile_no']
        for field in required_fields:
            if field not in body:
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({'error': f'Missing required field: {field}'})
                }
        if not validate_user(body['user_id']):
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'User not found',
                    'message': 'User must exist in the system before creating a member profile'
                })
            }

        member_item = {
            'user_id': body['user_id'],
            'building_id': body['building_id'],
            'name': body['name'],
            'mobile_no': body['mobile_no'],
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        if 'wings' in body:
            member_item['wings'] = body['wings']
        if 'floor' in body:
            member_item['floor'] = body['floor']
        if 'unit_number' in body:
            member_item['unit_number'] = body['unit_number']
        
        existing_item = table.get_item(Key={'user_id': body['user_id']})
        if 'Item' in existing_item:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Member with this user_id already exists'})
            }
        
        table.put_item(Item=member_item)
        
        return {
            'statusCode': 201,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Member created successfully',
                'member_id': member_item['user_id']
            })
        }
        
    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Invalid JSON format'})
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