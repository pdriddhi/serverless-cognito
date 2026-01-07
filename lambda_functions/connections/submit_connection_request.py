import json
import boto3
import uuid
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
        print("=== SUBMIT CONNECTION REQUEST ===")
        
        body = json.loads(event.get('body', '{}'))
        
        required_fields = ['user_id', 'user_name', 'user_mobile', 'building_id', 
                          'wing', 'floor', 'unit_number']
        
        missing_fields = [field for field in required_fields if not body.get(field)]
        if missing_fields:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'message': f'Missing required fields: {", ".join(missing_fields)}',
                    'success': False
                })
            }
        
        connection_requests_table = dynamodb.Table(TABLE_CONNECTION_REQUESTS)
        buildings_table = dynamodb.Table(TABLE_BUILDINGS)
        user_units_table = dynamodb.Table(TABLE_USERUNITS)
        members_table = dynamodb.Table(MEMBERS_TABLE) if MEMBERS_TABLE else None
        
        building_response = buildings_table.get_item(
            Key={'building_id': body['building_id']}
        )
        
        if 'Item' not in building_response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'message': 'Building not found',
                    'success': False
                })
            }
        
        building = building_response['Item']
        
        if body['wing'] not in building.get('wings', []):
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'message': f'Invalid wing. Available wings: {", ".join(building.get("wings", []))}',
                    'success': False
                })
            }
        
        # ✅ FIX: Use ExpressionAttributeNames for reserved keyword 'status'
        existing_request = connection_requests_table.scan(
            FilterExpression=(
                'user_id = :uid AND building_id = :bid AND wing = :wing AND '
                'floor = :floor AND unit_number = :unit AND #status = :status_val'
            ),
            ExpressionAttributeValues={
                ':uid': body['user_id'],
                ':bid': body['building_id'],
                ':wing': body['wing'],
                ':floor': body['floor'],
                ':unit': body['unit_number'],
                ':status_val': 'pending'
            },
            ExpressionAttributeNames={
                '#status': 'status'
            }
        )
        
        if existing_request.get('Count', 0) > 0:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'message': 'You already have a pending request for this unit',
                    'success': False
                })
            }
        
        request_id = f"REQ-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.utcnow().isoformat()
        
        request_item = {
            'request_id': request_id,
            'user_id': body['user_id'],
            'user_name': body['user_name'],
            'user_mobile': body['user_mobile'],
            'building_id': body['building_id'],
            'building_code': building.get('building_code', ''),
            'building_name': building.get('building_name', 'Unknown Building'),
            'wing': body['wing'],
            'floor': body['floor'],
            'unit_number': body['unit_number'],
            'status': 'pending',
            'requested_at': now,
            'updated_at': now
        }
        
        connection_requests_table.put_item(Item=request_item)
        
        print(f"Connection request created: {request_id}")
        
        return {
            'statusCode': 201,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'success': True,
                'message': 'Connection request submitted successfully',
                'request_id': request_id,
                'status': 'pending',
                'requested_at': now
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