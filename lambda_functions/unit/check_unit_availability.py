import json
import boto3
import os
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')

TABLE_USERUNITS = os.environ.get('TABLE_USERUNITS', 'UserUnits-dev')
MEMBERS_TABLE = os.environ.get('MEMBERS_TABLE', 'Members-dev')
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
    """Convert Decimal objects to float/int for JSON serialization"""
    if isinstance(obj, list):
        return [convert_decimal(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: convert_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj

def enrich_wing_details(wing_details):
    """Add total_units calculation to wing_details"""
    enriched = {}
    for wing_name, details in wing_details.items():
        if isinstance(details, dict):
            total_floors = details.get('total_floors', 0)
            units_per_floor = details.get('units_per_floor', 0)
            
            try:
                total_floors = int(total_floors)
                units_per_floor = int(units_per_floor)
                total_units = total_floors * units_per_floor
            except:
                total_units = 0
            
            enriched[wing_name] = {
                **details,
                'total_units': total_units
            }
    return enriched

def lambda_handler(event, context):
    """
    Check if a unit is available for assignment/connection request
    """
    try:
        print("=== CHECK UNIT AVAILABILITY FUNCTION ===")
        
        query_params = event.get('queryStringParameters', {}) or {}
        print(f"Query params: {query_params}")
        
        building_id = query_params.get('building_id')
        wing = query_params.get('wing')
        floor = query_params.get('floor')
        unit_number = query_params.get('unit_number')
        user_id = query_params.get('user_id')  
        
        if not building_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': False,
                    'message': 'building_id is required'
                })
            }
        
        if not user_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': False,
                    'message': 'user_id is required for access check'
                })
            }
        
        user_units_table = dynamodb.Table(TABLE_USERUNITS)
        members_table = dynamodb.Table(MEMBERS_TABLE) if MEMBERS_TABLE else None
        buildings_table = dynamodb.Table(TABLE_BUILDINGS)
        
        if not check_user_has_any_role(user_id, building_id):
            return {
                'statusCode': 403,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': False,
                    'message': 'You do not have access to check availability for this building',
                    'user_id': user_id,
                    'building_id': building_id
                })
            }
        
        try:
            building_response = buildings_table.get_item(
                Key={'building_id': building_id}
            )
            
            if 'Item' not in building_response:
                return {
                    'statusCode': 404,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'success': False,
                        'message': 'Building not found'
                    })
                }
            
            building = building_response['Item']
            building_wings = building.get('wings', [])
            
            wing_details = building.get('wing_details', {})
            enriched_wing_details = enrich_wing_details(wing_details)
            
            if wing and wing not in building_wings:
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'success': False,
                        'message': f'Invalid wing. Available wings: {", ".join(building_wings)}'
                    })
                }
                
        except Exception as e:
            print(f"Error fetching building: {e}")
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': False,
                    'message': 'Error validating building',
                    'error': str(e)
                })
            }
        
        print("RETURNING SUCCESS RESPONSE")

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': True,
                'message': 'Unit availability check successful',
                'building_id': building_id,
                'wing': wing,
                'floor': floor,
                'unit_number': unit_number
            })
        }        

    except Exception as e:
        print(f"Unexpected error in check_unit_availability: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': False,
                'message': 'Internal server error while checking unit availability',
                'error': str(e)
            })
        }