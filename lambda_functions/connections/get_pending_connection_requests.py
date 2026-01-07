import json
import boto3
import os

dynamodb = boto3.resource('dynamodb')

TABLE_CONNECTION_REQUESTS = os.environ['TABLE_CONNECTION_REQUESTS']
TABLE_BUILDINGS = os.environ['TABLE_BUILDINGS']
TABLE_USERS = os.environ['TABLE_USERS']

def lambda_handler(event, context):
    try:
        print("=== GET PENDING CONNECTION REQUESTS ===")
        
        query_params = event.get('queryStringParameters') or {}
        admin_id = query_params.get('admin_id')
        building_id = query_params.get('building_id')
        
        if not admin_id and not building_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'message': 'admin_id or building_id is required',
                    'success': False
                })
            }
        
        connection_requests_table = dynamodb.Table(TABLE_CONNECTION_REQUESTS)
        buildings_table = dynamodb.Table(TABLE_BUILDINGS)
        
        pending_requests = []
        
        if building_id:
            response = connection_requests_table.query(
                IndexName='BuildingIdStatusIndex',
                KeyConditionExpression='building_id = :bid AND #status = :status',
                ExpressionAttributeValues={
                    ':bid': building_id,
                    ':status': 'pending'
                },
                ExpressionAttributeNames={'#status': 'status'}
            )
            pending_requests = response.get('Items', [])
            
        elif admin_id:
            buildings_response = buildings_table.scan(
                FilterExpression='user_id = :uid',
                ExpressionAttributeValues={':uid': admin_id}
            )
            
            admin_buildings = buildings_response.get('Items', [])
            building_ids = [building['building_id'] for building in admin_buildings]
            
            for bld_id in building_ids:
                response = connection_requests_table.query(
                    IndexName='BuildingIdStatusIndex',
                    KeyConditionExpression='building_id = :bid AND #status = :status',
                    ExpressionAttributeValues={
                        ':bid': bld_id,
                        ':status': 'pending'
                    },
                    ExpressionAttributeNames={'#status': 'status'}
                )
                pending_requests.extend(response.get('Items', []))
        
        pending_requests.sort(key=lambda x: x.get('requested_at', ''), reverse=True)
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'success': True,
                'count': len(pending_requests),
                'requests': pending_requests
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
                'success': False
            })
        }