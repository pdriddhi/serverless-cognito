import json
import boto3
import os
from datetime import datetime

def lambda_handler(event, context):
    body = json.loads(event.get('body', '{}'))
    
    building_id = body.get('building_id')
    target_user_id = body.get('target_user_id')
    new_role = body.get('role')  
    admin_id = body.get('admin_id') 
    
    if not all([building_id, target_user_id, new_role, admin_id]):
        return {'statusCode': 400, 'body': json.dumps({'success': False, 'message': 'Missing fields'})}
    
    if new_role not in ['admin', 'member']:
        return {'statusCode': 400, 'body': json.dumps({'success': False, 'message': 'Invalid role'})}
    
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('BuildingMembers-dev')
    
    admin_check = table.get_item(
        Key={'building_id': building_id, 'user_id': admin_id}
    )
    
    if 'Item' not in admin_check or admin_check['Item'].get('role') != 'admin':
        return {
            'statusCode': 403,
            'body': json.dumps({'success': False, 'message': 'Admin permission required'})
        }
    
    now = datetime.now().isoformat()
    
    table.update_item(
        Key={'building_id': building_id, 'user_id': target_user_id},
        UpdateExpression='SET #role = :role, updated_at = :updated, changed_by = :changed',
        ExpressionAttributeNames={'#role': 'role'},
        ExpressionAttributeValues={
            ':role': new_role,
            ':updated': now,
            ':changed': admin_id
        }
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'success': True,
            'message': f'Role changed to {new_role}',
            'user_id': target_user_id,
            'building_id': building_id,
            'role': new_role
        })
    }