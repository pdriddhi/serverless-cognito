import json
import boto3
import os
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

        user_units_table = dynamodb.Table(os.environ['USER_UNITS_TABLE'])
        users_table = dynamodb.Table(os.environ['USERS_TABLE'])

        response = user_units_table.scan()
        units = response.get('Items', [])

        final_units = []

        for unit in units:
            user_id = unit.get("user_id")

            name = None
            mobile = None
            wings = None

            if user_id:
                user_response = users_table.get_item(
                    Key={"user_id": user_id}
                )
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
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'units': final_units,
                'count': len(final_units)
            })
        }

    except Exception as e:
        print("ERROR:", str(e))
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'message': 'Failed to get user units'})
        }

