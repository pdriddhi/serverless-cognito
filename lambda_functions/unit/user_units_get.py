import json
import boto3
import os
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')

TABLE_USERUNITS = os.environ.get('TABLE_USERUNITS', 'UserUnits-dev')
USERS_TABLE = os.environ.get('USERS_TABLE', 'Users-dev')

user_units_table = dynamodb.Table(TABLE_USERUNITS)
users_table = dynamodb.Table(USERS_TABLE)

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
        print("User Units Get function started")
        print(f"Using tables: {TABLE_USERUNITS}, {USERS_TABLE}")   

        # Step 1: Fetch all units with pagination support
        units = []
        response = user_units_table.scan()
        units.extend(response.get('Items', []))
        
        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = user_units_table.scan(
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            units.extend(response.get('Items', []))

        final_units = []

       
        for unit in units:
            user_id = unit.get("user_id")

            # Default values
            name = None
            mobile = None
            wings = None

            if user_id:
                user_response = users_table.get_item(Key={"user_id": user_id})

                user_data = user_response.get("Item", {})

                name = user_data.get("name")
                mobile = user_data.get("mobile")
                wings = user_data.get("wings")

            
            unit.pop("rent_amount", None)
            unit.pop("area_sqft", None)
            unit.pop("unit_type", None)

            
            unit["name"] = name
            unit["mobile"] = mobile
            unit["wings"] = wings

            final_units.append(unit)

        final_units = convert_decimal(final_units)

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'units': final_units,
                'count': len(final_units)
            })
        }

    except Exception as e:
        print(f"Error in user_units_get: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'message': 'Failed to get user units',
                'error': str(e)
            })
        }
