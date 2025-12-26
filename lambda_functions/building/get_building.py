import json
import boto3
import os
from decimal import Decimal
import traceback

TABLE_BUILDINGS = os.environ['TABLE_BUILDINGS']

def lambda_handler(event, context):
    print("=== GET BUILDING FUNCTION STARTED ===")

    try:
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

        dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
        table = dynamodb.Table(TABLE_BUILDINGS)

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
        print(f"Raw item from DynamoDB: {json.dumps(item, default=str)}")

        wing_details = {}
        total_units_of_building = 0
        wings_list = []

        if 'wing_details' in item:
            wing_details = item['wing_details']

            for wing_name, wing_info in wing_details.items():
                wings_list.append(wing_name)

                units_per_floor = wing_info.get('units_per_floor', 0)
                total_floors = wing_info.get('total_floors', 0)
                total_units_for_wing = units_per_floor * total_floors

                total_units_of_building += total_units_for_wing

                wing_info['total_units'] = total_units_for_wing

        building_data = {
            'building_id': item.get('building_id'),
            'building_name': item.get('building_name'),
            'user_id': item.get('user_id'),
            'status': item.get('status', 'active'),
            'created_at': item.get('created_at'),
            'updated_at': item.get('updated_at'),
            'total_units_of_building': total_units_of_building,
            'wing_details': wing_details,
            'wings': wings_list
        }

        for key, value in item.items():
            if key not in building_data:
                building_data[key] = value

        def convert_decimals(obj):
            if isinstance(obj, Decimal):
                return int(obj) if obj % 1 == 0 else float(obj)
            elif isinstance(obj, dict):
                return {k: convert_decimals(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_decimals(i) for i in obj]
            else:
                return obj

        building_data = convert_decimals(building_data)

        print(f"Building fetched successfully: {building_data.get('building_name')}")
        print(f"Total units calculated: {total_units_of_building}")

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Building details retrieved successfully',
                'building': building_data
            }, default=str)
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
