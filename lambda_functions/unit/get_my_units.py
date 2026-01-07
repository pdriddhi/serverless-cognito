import json
import boto3
import os
from decimal import Decimal
from boto3.dynamodb.conditions import Attr

dynamodb = boto3.resource('dynamodb')

TABLE_USERUNITS = os.environ.get('TABLE_USERUNITS', 'UserUnits-dev')
TABLE_BUILDINGS = os.environ.get('TABLE_BUILDINGS', 'Buildings-dev')
USER_BUILDING_ROLES_TABLE = os.environ.get('TABLE_USER_BUILDING_ROLES', 'UserBuildingRoles-dev')

def check_user_has_any_role(user_id, building_id):
    """Check if user has any role (admin/member) in the building"""
    try:
        if not USER_BUILDING_ROLES_TABLE:
            print("WARNING: USER_BUILDING_ROLES_TABLE not configured, skipping role check")
            return True
            
        table = dynamodb.Table(USER_BUILDING_ROLES_TABLE)
        composite_key = f"{user_id}#{building_id}"
        
        response = table.get_item(Key={'user_building_composite': composite_key})
        
        if 'Item' in response:
            user_role = response['Item'].get('role')
            print(f"User has role '{user_role}' for building {building_id}")
            return True
        
        print(f"No role found for user {user_id} in building {building_id}")
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
        print("=== GET MY UNITS FUNCTION STARTED ===")
        print(f"Using tables: {TABLE_USERUNITS}, {TABLE_BUILDINGS}")
        
        # ✅ FIX: Initialize tables here
        user_units_table = dynamodb.Table(TABLE_USERUNITS)
        buildings_table = dynamodb.Table(TABLE_BUILDINGS)
        
        query_params = event.get('queryStringParameters', {}) or {}
        user_id = query_params.get('user_id')
        
        if not user_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'success': False,  
                    'message': 'user_id parameter is required'
                })
            }
        
        units = []
        response = user_units_table.scan(
            FilterExpression=Attr('user_id').eq(user_id)
        )
        units.extend(response.get('Items', []))
        
        while 'LastEvaluatedKey' in response:
            response = user_units_table.scan(
                FilterExpression=Attr('user_id').eq(user_id),
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            units.extend(response.get('Items', []))
        
        filtered_units = []
        for unit in units:
            building_id = unit.get('building_id')
            if building_id and check_user_has_any_role(user_id, building_id):
                try:
                    building_response = buildings_table.get_item(Key={'building_id': building_id})
                    if 'Item' in building_response:
                        unit['building_details'] = building_response['Item']
                        filtered_units.append(unit)
                except Exception as e:
                    print(f"Error fetching building {building_id}: {e}")
        
        filtered_units = convert_decimal(filtered_units)
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'success': True,  
                'user_id': user_id,
                'units': filtered_units,
                'count': len(filtered_units)
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
                'success': False,
                'message': 'Failed to get units',
                'error': str(e)
            })
        }