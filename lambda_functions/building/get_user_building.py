import json
import boto3
import os
import traceback

dynamodb = boto3.resource('dynamodb')
TABLE_BUILDINGS = os.environ['TABLE_BUILDINGS']
table = dynamodb.Table(TABLE_BUILDINGS)

def lambda_handler(event, context):
    print("=== GET USER BUILDING ===")
    print(f"Event: {json.dumps(event, default=str)}")

    try:
       
        query_params = event.get('queryStringParameters') or {}
        user_id = query_params.get('user_id')
        
        print(f"Query params: {query_params}")
        print(f"Looking for buildings for user_id: {user_id}")

        if not user_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'message': 'user_id is required in query parameters',
                    'success': False
                })
            }

        
        try:
            print("Trying to query using UserIDIndex GSI...")
            response = table.query(
                IndexName='UserIDIndex',
                KeyConditionExpression='user_id = :uid',
                ExpressionAttributeValues={
                    ':uid': user_id
                }
            )
            print(f"GSI query response: {response}")
            
        except Exception as gsi_error:
            print(f"GSI query failed: {str(gsi_error)}")
            print("Falling back to scan operation...")
            
            
            response = table.scan(
                FilterExpression='user_id = :uid',
                ExpressionAttributeValues={
                    ':uid': user_id
                }
            )
            print(f"Scan response count: {response.get('Count', 0)}")

        items = response.get('Items', [])
        print(f"Found {len(items)} building(s) for user {user_id}")

        if not items:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'message': 'No building found for this user',
                    'success': False,
                    'user_id': user_id
                })
            }

        
        buildings_list = []
        for building in items:
            
            building_data = {
                'building_id': building.get('building_id'),
                'building_name': building.get('building_name'),  
                'name': building.get('building_name'),  
                'user_id': building.get('user_id'),
                'wings': building.get('wings', []),
                'wing_details': building.get('wing_details', {}),
                'total_wings': building.get('total_wings'),
                'total_units_of_building': building.get('total_units_of_building'),
                'created_at': building.get('created_at'),
                'updated_at': building.get('updated_at'),
                'status': building.get('status', 'active')
            }
            buildings_list.append(building_data)

        
        first_building = items[0]
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Building(s) found successfully',
                'success': True,
                'user_id': user_id,
                'total_buildings': len(items),
                'building': {  
                    'building_id': first_building.get('building_id'),
                    'building_name': first_building.get('building_name'),
                    'name': first_building.get('building_name'),
                    'user_id': first_building.get('user_id'),
                    'wings': first_building.get('wings', []),
                    'wing_details': first_building.get('wing_details', {}),
                    'total_wings': first_building.get('total_wings'),
                    'total_units_of_building': first_building.get('total_units_of_building'),
                    'created_at': first_building.get('created_at'),
                    'updated_at': first_building.get('updated_at'),
                    'status': first_building.get('status', 'active')
                },
                'all_buildings': buildings_list  
            }, default=str)  
        }

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        traceback.print_exc()
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Internal server error',
                'success': False,
                'error': str(e)
            })
        }