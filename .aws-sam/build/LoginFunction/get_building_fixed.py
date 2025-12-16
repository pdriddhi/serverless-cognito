import json
import boto3
from decimal import Decimal

def lambda_handler(event, context):
    try:
        print("Get Building function started")
        
        # Get building_id from query parameters
        building_id = event.get('queryStringParameters', {}).get('building_id')
        
        if not building_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'building_id parameter is required'})
            }
        
        # Connect to DynamoDB
        dynamodb = boto3.resource('dynamodb')
        buildings_table = dynamodb.Table('Buildings-dev')
        
        # Get building from DynamoDB
        response = buildings_table.get_item(Key={'building_id': building_id})
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Building not found'})
            }
        
        # Convert Decimal to int/float for JSON serialization
        building_item = response['Item']
        
        # Function to convert Decimal to int/float
        def convert_decimal(obj):
            if isinstance(obj, Decimal):
                # Convert to int if it's a whole number, else float
                if obj % 1 == 0:
                    return int(obj)
                else:
                    return float(obj)
            elif isinstance(obj, list):
                return [convert_decimal(item) for item in obj]
            elif isinstance(obj, dict):
                return {key: convert_decimal(value) for key, value in obj.items()}
            return obj
        
        # Convert all Decimal fields
        converted_building = convert_decimal(building_item)
        
        print(f"Successfully fetched building: {converted_building.get('building_name')}")
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps(converted_building)
        }
        
    except Exception as e:
        print(f"Error in get_building: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Failed to get building details'})
        }
