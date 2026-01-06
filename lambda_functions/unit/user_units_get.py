import json
import boto3
import os
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')

TABLE_USERUNITS = os.environ.get('TABLE_USERUNITS', 'UserUnits-dev')
USERS_TABLE = os.environ.get('USERS_TABLE', 'Users-dev')
USER_BUILDING_ROLES_TABLE = os.environ.get('TABLE_USER_BUILDING_ROLES', 'UserBuildingRoles-dev')

def check_user_is_admin(user_id, building_id):
    """Check if user is admin for the given building"""
    try:
        if not USER_BUILDING_ROLES_TABLE:
            print("WARNING: USER_BUILDING_ROLES_TABLE not configured, skipping admin check")
            return True
            
        table = dynamodb.Table(USER_BUILDING_ROLES_TABLE)
        composite_key = f"{user_id}#{building_id}"
        
        response = table.get_item(Key={'user_building_composite': composite_key})
        
        if 'Item' in response:
            user_role = response['Item'].get('role')
            return user_role == 'admin'
        
        return False
        
    except Exception as e:
        print(f"Error checking user role: {str(e)}")
        return False

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
        print("=== USER UNITS GET FUNCTION STARTED ===")
        print(f"Using tables: {TABLE_USERUNITS}, {USERS_TABLE}")
        
        query_params = event.get('queryStringParameters', {}) or {}
        user_id = query_params.get('user_id')  # CHANGED: admin_user_id -> user_id
        building_id = query_params.get('building_id')
        
        if not user_id or not building_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'success': False,
                    'message': 'user_id and building_id are required'
                })
            }
        
        # ===== Check if user is admin for this building =====
        if not check_user_is_admin(user_id, building_id):
            return {
                'statusCode': 403,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'success': False,
                    'message': 'Only building admin can view all units',
                    'user_id': user_id,
                    'building_id': building_id
                })
            }
        
        user_units_table = dynamodb.Table(TABLE_USERUNITS)
        users_table = dynamodb.Table(USERS_TABLE)
        
        # Fetch units filtered by building_id
        units = []
        response = user_units_table.scan(
            FilterExpression='building_id = :bid',
            ExpressionAttributeValues={':bid': building_id}
        )
        units.extend(response.get('Items', []))
        
        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = user_units_table.scan(
                FilterExpression='building_id = :bid',
                ExpressionAttributeValues={':bid': building_id},
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            units.extend(response.get('Items', []))
        
        final_units = []
        
        for unit in units:
            unit_user_id = unit.get("user_id")
            name = None
            mobile = None

            if unit_user_id:
                user_response = users_table.get_item(Key={"user_id": unit_user_id})
                user_data = user_response.get("Item", {})
                name = user_data.get("name")
                mobile = user_data.get("mobile")

            # Optional: Remove sensitive/optional fields
            unit.pop("rent_amount", None)
            unit.pop("area_sqft", None)
            unit.pop("unit_type", None)

            # Add user info
            unit["occupant_name"] = name
            unit["occupant_mobile"] = mobile

            final_units.append(unit)

        final_units = convert_decimal(final_units)

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'success': True,
                'building_id': building_id,
                'requested_by': user_id,
                'is_admin': True,  # Since we passed admin check
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
                'success': False,
                'message': 'Failed to get user units',
                'error': str(e)
            })
        }