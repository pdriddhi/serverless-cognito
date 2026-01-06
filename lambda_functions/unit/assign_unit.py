import json
import boto3
import uuid
import os
from datetime import datetime
import traceback

# Environment variables
USER_BUILDING_ROLES_TABLE = os.environ.get('TABLE_USER_BUILDING_ROLES', 'UserBuildingRoles-dev')
USER_UNITS_TABLE = os.environ.get('TABLE_USERUNITS', 'UserUnits-dev')
USERS_TABLE = os.environ.get('USERS_TABLE', 'Users-dev')
BUILDINGS_TABLE = os.environ.get('TABLE_BUILDINGS', 'Buildings-dev')

dynamodb = boto3.resource('dynamodb')

def get_user_role_for_building(user_id, building_id):
    """Get user's role for a specific building"""
    try:
        if not USER_BUILDING_ROLES_TABLE:
            print("WARNING: USER_BUILDING_ROLES_TABLE not configured")
            return None
            
        table = dynamodb.Table(USER_BUILDING_ROLES_TABLE)
        composite_key = f"{user_id}#{building_id}"
        
        response = table.get_item(Key={'user_building_composite': composite_key})
        
        if 'Item' in response:
            user_role = response['Item'].get('role')
            print(f"User role for building {building_id}: {user_role}")
            return user_role
        
        print(f"No role found for user {user_id} in building {building_id}")
        return None
        
    except Exception as e:
        print(f"Error checking user role: {str(e)}")
        return None

def check_user_is_admin(user_id, building_id):
    """Check if user is admin for the given building"""
    user_role = get_user_role_for_building(user_id, building_id)
    return user_role == 'admin'

def check_user_is_member(user_id, building_id):
    """Check if user is member for the given building"""
    user_role = get_user_role_for_building(user_id, building_id)
    return user_role == 'member'

def lambda_handler(event, context):
    try:
        print("=== ASSIGN UNIT FUNCTION STARTED ===")

        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})

        # Parameters
        user_id = body.get('user_id')  # User who wants to assign unit
        building_id = body.get('building_id')
        unit_number = body.get('unit_number')
        floor = body.get('floor')  
        wings = body.get('wings')   
        
        unit_type = body.get('unit_type', '2BHK')
        area_sqft = body.get('area_sqft', 0)
        rent_amount = body.get('rent_amount', 0)

        # Required fields
        required_fields = ['user_id', 'building_id', 'unit_number', 'floor', 'wings']
        missing_fields = [field for field in required_fields if not body.get(field)]
        
        if missing_fields:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'success': False,
                    'message': f'Missing required fields: {", ".join(missing_fields)}'
                })
            }

        # ===== Check user's role for this building =====
        user_role = get_user_role_for_building(user_id, building_id)
        
        if user_role is None:
            # User has no role in this building
            return {
                'statusCode': 403,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'success': False,
                    'message': 'You do not have any role in this building',
                    'user_id': user_id,
                    'building_id': building_id
                })
            }
        
        if user_role != 'admin':
            # Only admin can assign units
            return {
                'statusCode': 403,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'success': False,
                    'message': 'Only building admin can assign units',
                    'user_id': user_id,
                    'building_id': building_id,
                    'user_role': user_role,
                    'required_role': 'admin'
                })
            }

        # Initialize tables
        user_units_table = dynamodb.Table(USER_UNITS_TABLE)
        users_table = dynamodb.Table(USERS_TABLE)
        buildings_table = dynamodb.Table(BUILDINGS_TABLE)

        # Check if user exists
        user_response = users_table.get_item(Key={'user_id': user_id})
        if 'Item' not in user_response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'success': False,
                    'message': 'User not found'
                })
            }

        # Check if building exists
        building_response = buildings_table.get_item(Key={'building_id': building_id})
        if 'Item' not in building_response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'success': False,
                    'message': 'Building not found'
                })
            }

        # Validate wing
        building_data = building_response['Item']
        building_wings = building_data.get('wings', [])
        
        if isinstance(building_wings, str):
            available_wings = [w.strip() for w in building_wings.split(',')]
        elif isinstance(building_wings, list):
            available_wings = [str(w).strip() for w in building_wings]
        else:
            available_wings = []

        if wings not in available_wings:
           return {
               'statusCode': 400,
               'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
               'body': json.dumps({
                    'success': False,
                    'message': f'Invalid wing. Available wings: {", ".join(available_wings)}'
               })
           }

        # Check if unit is already assigned
        existing_units_response = user_units_table.scan(
            FilterExpression='building_id = :bid AND wings = :wing AND floor = :floor AND unit_number = :unit',
            ExpressionAttributeValues={
                ':bid': building_id,
                ':wing': wings,
                ':floor': int(floor),
                ':unit': unit_number
            }
        )
        
        if existing_units_response.get('Items') and len(existing_units_response['Items']) > 0:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'success': False,
                    'message': 'Unit is already assigned to another user'
                })
            }

        # Create unit record
        unit_id = f"UNIT-{uuid.uuid4().hex[:8].upper()}"

        unit_item = {
            'unit_id': unit_id,
            'user_id': user_id,  # Admin ही unit owner होगा
            'building_id': building_id,
            'unit_number': unit_number,
            'floor': int(floor),  
            'wings': wings,          
            'unit_type': unit_type,
            'area_sqft': area_sqft,
            'rent_amount': rent_amount,
            'assigned_by': user_id,
            'assigned_at': datetime.now().isoformat(),
            'status': 'active',
            'user_role': user_role  # Store role with unit
        }

        user_units_table.put_item(Item=unit_item)

        print(f"Admin {user_id} assigned unit {unit_number} in building {building_id}")

        # Return success response
        return {
            'statusCode': 201,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'success': True,
                'message': 'Unit assigned successfully',
                'unit_id': unit_id,
                'user_id': user_id,
                'user_role': user_role,
                'building_id': building_id,
                'unit_number': unit_number,
                'floor': floor,
                'wings': wings,
                'unit_type': unit_type,
                'area_sqft': area_sqft,
                'rent_amount': rent_amount
            })
        }

    except Exception as e:
        print(f"Error in assign_unit: {str(e)}")
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'success': False,
                'message': f'Failed to assign unit: {str(e)}'
            })
        }