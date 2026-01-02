import json
import boto3
import os
from decimal import Decimal
from boto3.dynamodb.conditions import Attr

dynamodb = boto3.resource('dynamodb')

TABLE_USERUNITS = os.environ.get('TABLE_USERUNITS', 'UserUnits-dev')
TABLE_BUILDINGS = os.environ.get('TABLE_BUILDINGS', 'Buildings-dev')

user_units_table = dynamodb.Table(TABLE_USERUNITS)
buildings_table = dynamodb.Table(TABLE_BUILDINGS)

def convert_decimal(obj):
    if isinstance(obj, list):
        return [convert_decimal(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: convert_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return float(obj)
    return obj

def lambda_handler(event, context):
    try:
        print("Get My Units function started")
        print(f"Using tables: {TABLE_USERUNITS}, {TABLE_BUILDINGS}")
        
        
        query_params = event.get('queryStringParameters', {}) or {}
        user_id = query_params.get('user_id')
        
        if not user_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'user_id parameter is required'})
            }
        
        # Scan with filter expression and handle pagination
        units = []
        response = user_units_table.scan(
            FilterExpression=Attr('user_id').eq(user_id)
        )
        units.extend(response.get('Items', []))
        
        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = user_units_table.scan(
                FilterExpression=Attr('user_id').eq(user_id),
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            units.extend(response.get('Items', []))
        
       
        for unit in units:
            building_id = unit.get('building_id')
            if building_id:
                try:
                    building_response = buildings_table.get_item(Key={'building_id': building_id})
                    if 'Item' in building_response:
                        unit['building_details'] = building_response['Item']
                except Exception as e:
                    print(f"Error fetching building {building_id}: {e}")
        
        # Convert Decimal values after all data is collected
        units = convert_decimal(units)
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'user_id': user_id,
                'units': units,
                'count': len(units)
            })
        }
        
    except Exception as e:
        print(f"Error in get_my_units: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'message': 'Failed to get units',
                'error': str(e)
            })
        }
