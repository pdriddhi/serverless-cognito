import json
import boto3
import os
import traceback

def lambda_handler(event, context):
    print("=== DELETE BUILDING FUNCTION STARTED ===")
    print(f"Full event: {json.dumps(event, indent=2)}")
    
    try:
        query_params = event.get('queryStringParameters') or {}
        print(f"Query params: {query_params}")
        
        building_id = query_params.get('building_id')
        print(f"Building ID: {building_id}")
        
        if not building_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'message': 'building_id is required',
                    'example': 'DELETE /delete_building?building_id=BLD123'
                })
            }
        
        table_name = os.environ.get('TABLE_BUILDINGS', 'Buildings-dev')
        print(f"Using table: {table_name}")
        
        dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
        table = dynamodb.Table(table_name)
        
        print(f"Checking if building exists: {building_id}")
        
        response = table.get_item(Key={'building_id': building_id})
        print(f"Get item response: {json.dumps(response, default=str)}")
        
        if 'Item' not in response:
            print(f"Building {building_id} not found")
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'message': 'Building not found'})
            }
        
        print(f"Deleting building: {building_id}")
        table.delete_item(Key={'building_id': building_id})
        print(f"Building {building_id} deleted successfully")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Building deleted successfully',
                'building_id': building_id,
                'building_name': response['Item'].get('building_name', '')
            })
        }
        
    except Exception as e:
        print(f"ERROR in lambda_handler: {str(e)}")
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Internal server error',
                'error': str(e),
                'details': 'Check Lambda logs for more information'
            })
        }
