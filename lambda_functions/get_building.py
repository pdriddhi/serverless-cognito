import json
import boto3
import os
from decimal import Decimal
import traceback

TABLE_BUILDINGS = os.environ['TABLE_BUILDINGS']

def lambda_handler(event, context):
    print("=== GET BUILDING FUNCTION STARTED ===")

    try:
        # Read query parameters
        query_params = event.get('queryStringParameters') or {}
        print(f"Query params: {query_params}")

        building_id = query_params.get('building_id')

        if not building_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'message': 'building_id is required'})
            }

        # DynamoDB init
        dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
        table = dynamodb.Table(TABLE_BUILDINGS)

        # Fetch building
        response = table.get_item(Key={'building_id': building_id})

        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'message': 'Building not found'})
            }

        item = response['Item']

        # Convert Decimal → int / float
        def convert_decimals(obj):
            if isinstance(obj, Decimal):
                return int(obj) if obj % 1 == 0 else float(obj)
            elif isinstance(obj, dict):
                return {k: convert_decimals(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_decimals(i) for i in obj]
            else:
                return obj

        building_data = convert_decimals(item)

        print(f"Building fetched successfully: {building_data.get('building_name')}")

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Building details retrieved successfully',
                'building': building_data
            })
        }

    except Exception as e:
        print("ERROR:", str(e))
        traceback.print_exc()

        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'message': 'Failed to get building details'})
        }
