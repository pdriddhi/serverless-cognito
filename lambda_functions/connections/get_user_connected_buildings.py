import json
import boto3
import os

dynamodb = boto3.resource('dynamodb')

TABLE_CONNECTION_REQUESTS = os.environ['TABLE_CONNECTION_REQUESTS']
TABLE_BUILDINGS = os.environ['TABLE_BUILDINGS']
TABLE_USERUNITS = os.environ['TABLE_USERUNITS']
MEMBERS_TABLE = os.environ['MEMBERS_TABLE']
TABLE_USERS = os.environ['TABLE_USERS']

def lambda_handler(event, context):
    try:
        print("=== GET USER CONNECTED BUILDINGS ===")
        
        query_params = event.get('queryStringParameters') or {}
        user_id = query_params.get('user_id')
        
        if not user_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'message': 'user_id is required',
                    'success': False
                })
            }
        
        connection_requests_table = dynamodb.Table(TABLE_CONNECTION_REQUESTS)
        buildings_table = dynamodb.Table(TABLE_BUILDINGS)
        user_units_table = dynamodb.Table(TABLE_USERUNITS)
        members_table = dynamodb.Table(MEMBERS_TABLE) if MEMBERS_TABLE else None
        
        result = {
            'connected_buildings': [],
            'pending_requests': [],
            'rejected_requests': []
        }
        
        user_units_response = user_units_table.scan(
            FilterExpression='user_id = :uid AND status = :status',
            ExpressionAttributeValues={
                ':uid': user_id,
                ':status': 'active'
            }
        )
        
        for unit in user_units_response.get('Items', []):
            building_response = buildings_table.get_item(
                Key={'building_id': unit['building_id']}
            )
            
            if 'Item' in building_response:
                building = building_response['Item']
                result['connected_buildings'].append({
                    'building_id': unit['building_id'],
                    'building_name': building.get('building_name'),
                    'building_code': building.get('building_code'),
                    'wing': unit.get('wings'),
                    'floor': unit.get('floor'),
                    'unit_number': unit.get('unit_number'),
                    'connection_type': 'unit_assignment',
                    'connected_at': unit.get('assigned_at'),
                    'status': 'active'
                })
        
        pending_response = connection_requests_table.query(
            IndexName='UserIdStatusIndex',
            KeyConditionExpression='user_id = :uid AND #status = :status',
            ExpressionAttributeValues={
                ':uid': user_id,
                ':status': 'pending'
            },
            ExpressionAttributeNames={'#status': 'status'}
        )
        
        for request in pending_response.get('Items', []):
            building_response = buildings_table.get_item(
                Key={'building_id': request['building_id']}
            )
            
            if 'Item' in building_response:
                building = building_response['Item']
                result['pending_requests'].append({
                    'request_id': request['request_id'],
                    'building_id': request['building_id'],
                    'building_name': building.get('building_name'),
                    'building_code': building.get('building_code'),
                    'wing': request['wing'],
                    'floor': request['floor'],
                    'unit_number': request['unit_number'],
                    'status': 'pending',
                    'requested_at': request['requested_at']
                })
        
        rejected_response = connection_requests_table.query(
            IndexName='UserIdStatusIndex',
            KeyConditionExpression='user_id = :uid AND #status = :status',
            ExpressionAttributeValues={
                ':uid': user_id,
                ':status': 'rejected'
            },
            ExpressionAttributeNames={'#status': 'status'}
        )
        
        for request in rejected_response.get('Items', []):
            building_response = buildings_table.get_item(
                Key={'building_id': request['building_id']}
            )
            
            if 'Item' in building_response:
                building = building_response['Item']
                result['rejected_requests'].append({
                    'request_id': request['request_id'],
                    'building_id': request['building_id'],
                    'building_name': building.get('building_name'),
                    'building_code': building.get('building_code'),
                    'wing': request['wing'],
                    'floor': request['floor'],
                    'unit_number': request['unit_number'],
                    'status': 'rejected',
                    'rejected_at': request.get('rejected_at'),
                    'rejected_by': request.get('rejected_by')
                })
        
        if members_table:
            member_response = members_table.scan(
                FilterExpression='user_id = :uid',
                ExpressionAttributeValues={':uid': user_id}
            )
            
            for member in member_response.get('Items', []):
                building_response = buildings_table.get_item(
                    Key={'building_id': member['building_id']}
                )
                
                if 'Item' in building_response:
                    building = building_response['Item']
                    result['connected_buildings'].append({
                        'building_id': member['building_id'],
                        'building_name': building.get('building_name'),
                        'building_code': building.get('building_code'),
                        'wing': member.get('wings'),
                        'floor': member.get('floor'),
                        'unit_number': member.get('unit_number'),
                        'connection_type': 'member',
                        'member_since': member.get('approved_at'),
                        'member_type': member.get('member_type', 'resident'),
                        'status': 'active'
                    })
        
        seen = set()
        unique_buildings = []
        for building in result['connected_buildings']:
            key = (building['building_id'], building.get('wing'), building.get('floor'), building.get('unit_number'))
            if key not in seen:
                seen.add(key)
                unique_buildings.append(building)
        
        result['connected_buildings'] = unique_buildings
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'success': True,
                'user_id': user_id,
                **result
            }, default=str)
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