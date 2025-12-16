import json
import boto3
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')

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

        user_units_table = dynamodb.Table('UserUnits-prod')
        users_table = dynamodb.Table('Users-prod')   # ← New Users table

        # Step 1: Fetch all units
        response = user_units_table.scan()
        units = response.get('Items', [])

        final_units = []

        # Step 2: Fetch name, mobile, wings from Users table
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

            # Step 3: Remove unwanted fields
            unit.pop("rent_amount", None)
            unit.pop("area_sqft", None)
            unit.pop("unit_type", None)

            # Step 4: Add new 3 fields
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
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Failed to get user units'})
        }
