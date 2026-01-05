import json
import boto3
import os
from datetime import datetime

dynamodb = boto3.resource('dynamodb')

TABLE_CONNECTION_REQUESTS = os.environ['TABLE_CONNECTION_REQUESTS']
TABLE_BUILDINGS = os.environ['TABLE_BUILDINGS']
TABLE_USERUNITS = os.environ['TABLE_USERUNITS']
MEMBERS_TABLE = os.environ['MEMBERS_TABLE']
TABLE_USERS = os.environ['TABLE_USERS']

def lambda_handler(event, context):
    try:
        print("=== PROCESS CONNECTION REQUEST ===")
        
        path_params = event.get('pathParameters', {}) or {}
        request_id = path_params.get('request_id')
        
        if not request_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'message': 'request_id is required in path',
                    'success': False
                })
            }
        
        body = json.loads(event.get('body', '{}'))
        action = body.get('action')  
        admin_id = body.get('admin_id')
        
        if not action or not admin_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'message': 'action and admin_id are required',
                    'success': False
                })
            }
        
        if action not in ['approve', 'reject']:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'message': 'action must be "approve" or "reject"',
                    'success': False
                })
            }
        
        connection_requests_table = dynamodb.Table(TABLE_CONNECTION_REQUESTS)
        buildings_table = dynamodb.Table(TABLE_BUILDINGS)
        user_units_table = dynamodb.Table(TABLE_USERUNITS)
        members_table = dynamodb.Table(MEMBERS_TABLE) if MEMBERS_TABLE else None
        
        response = connection_requests_table.get_item(
            Key={'request_id': request_id}
        )
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'message': 'Request not found',
                    'success': False
                })
            }
        
        request_data = response['Item']
        
        if request_data.get('status') != 'pending':
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'message': 'Request is already processed',
                    'success': False
                })
            }
        
        now = datetime.utcnow().isoformat()
        
        if action == 'approve':
            if members_table:
                member_item = {
                    'user_id': request_data['user_id'],
                    'building_id': request_data['building_id'],
                    'name': request_data['user_name'],
                    'mobile_no': request_data['user_mobile'],
                    'wings': request_data['wing'],
                    'floor': request_data['floor'],
                    'unit_number': request_data['unit_number'],
                    'member_type': 'resident',
                    'approved_by': admin_id,
                    'approved_at': now,
                    'created_at': now,
                    'updated_at': now
                }
                members_table.put_item(Item=member_item)
            
            unit_id = f"UNIT-{request_id}"
            unit_item = {
                'unit_id': unit_id,
                'user_id': request_data['user_id'],
                'building_id': request_data['building_id'],
                'unit_number': request_data['unit_number'],
                'floor': int(request_data['floor']),
                'wings': request_data['wing'],
                'assigned_at': now,
                'status': 'active'
            }
            user_units_table.put_item(Item=unit_item)
            
            connection_requests_table.update_item(
                Key={'request_id': request_id},
                UpdateExpression='SET #status = :status, approved_at = :approved_at, '
                               'approved_by = :approved_by, updated_at = :updated_at',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':status': 'approved',
                    ':approved_at': now,
                    ':approved_by': admin_id,
                    ':updated_at': now
                }
            )
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'success': True,
                    'message': 'Request approved successfully. User added as member.',
                    'member_id': f"MEM-{request_data['user_id']}",
                    'unit_id': unit_id,
                    'action': 'approved'
                })
            }
        
        else:  
            connection_requests_table.update_item(
                Key={'request_id': request_id},
                UpdateExpression='SET #status = :status, rejected_at = :rejected_at, '
                               'rejected_by = :rejected_by, updated_at = :updated_at',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':status': 'rejected',
                    ':rejected_at': now,
                    ':rejected_by': admin_id,
                    ':updated_at': now
                }
            )
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'success': True,
                    'message': 'Request rejected successfully',
                    'action': 'rejected'
                })
            }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'message': 'Internal server error',
                'success': False,
                'error': str(e)
            })
        }