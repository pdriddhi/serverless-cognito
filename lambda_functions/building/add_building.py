import json
import boto3
import uuid
import os
import traceback
from datetime import datetime
from decimal import Decimal

TABLE_BUILDINGS = os.environ['TABLE_BUILDINGS']
USERS_TABLE = os.environ.get('USERS_TABLE')
USER_BUILDING_ROLES_TABLE = os.environ.get('TABLE_USER_BUILDING_ROLES') 

dynamodb = boto3.resource('dynamodb')
buildings_table = dynamodb.Table(TABLE_BUILDINGS)
users_table = dynamodb.Table(USERS_TABLE) if USERS_TABLE else None
user_building_roles_table = dynamodb.Table(USER_BUILDING_ROLES_TABLE) if USER_BUILDING_ROLES_TABLE else None  

def validate_user(user_id):
    """
    Check if user exists in Users table
    Returns True if user exists, False otherwise
    """
    if not USERS_TABLE or not users_table:
        print("Warning: USERS_TABLE not configured, skipping user validation")
        return True  
    
    try:
        response = users_table.get_item(Key={'user_id': user_id})
        user_exists = 'Item' in response
        if not user_exists:
            print(f"User {user_id} not found in Users table")
        return user_exists
    except Exception as e:
        print(f"Error validating user {user_id}: {str(e)}")
        traceback.print_exc()
        return False

def assign_admin_role_to_user(user_id, building_id):
    """
    Assign admin role to user for the building in UserBuildingRoles table
    """
    if not USER_BUILDING_ROLES_TABLE or not user_building_roles_table:
        print("Warning: TABLE_USER_BUILDING_ROLES not configured, skipping role assignment")
        return False
    
    try:
        composite_key = f"{user_id}#{building_id}"
        current_time = datetime.now().isoformat()
        
        # Check if role already exists
        try:
            existing_role = user_building_roles_table.get_item(
                Key={'user_building_composite': composite_key}
            )
            
            if 'Item' in existing_role:
                # Update existing role to admin
                user_building_roles_table.update_item(
                    Key={'user_building_composite': composite_key},
                    UpdateExpression='SET #role = :role, updated_at = :updated',
                    ExpressionAttributeNames={'#role': 'role'},
                    ExpressionAttributeValues={
                        ':role': 'admin',
                        ':updated': current_time
                    }
                )
                print(f"Updated existing role to 'admin' for user {user_id} in building {building_id}")
            else:
                # Create new admin role
                user_building_roles_table.put_item(
                    Item={
                        'user_building_composite': composite_key,
                        'user_id': user_id,
                        'building_id': building_id,
                        'role': 'admin',
                        'created_at': current_time,
                        'updated_at': current_time
                    }
                )
                print(f"Assigned 'admin' role to user {user_id} for building {building_id}")
                
        except Exception as role_check_error:
            print(f"Error checking existing role: {str(role_check_error)}")
            # Create new role anyway
            user_building_roles_table.put_item(
                Item={
                    'user_building_composite': composite_key,
                    'user_id': user_id,
                    'building_id': building_id,
                    'role': 'admin',
                    'created_at': current_time,
                    'updated_at': current_time
                }
            )
            print(f"Assigned 'admin' role to user {user_id} for building {building_id}")
        
        return True
        
    except Exception as role_error:
        print(f"Error assigning admin role: {str(role_error)}")
        traceback.print_exc()
        return False

def generate_building_code(building_name, building_id):
    """
    Generate unique building code from building name and ID
    Format: First 3 letters of building name + Last 4 chars of building ID
    Example: SUNRISE APARTMENTS + BLD-ABC123DEF -> SUN-DEF
    """
    words = [word for word in building_name.split() if word]
    
    if words:
        prefix = ''.join([word[0].upper() for word in words[:3]])
        if len(prefix) < 2:
            prefix = 'BLD'[:3]
    else:
        prefix = 'BLD'
    
    if len(prefix) > 3:
        prefix = prefix[:3]
    elif len(prefix) < 3:
        prefix = prefix.ljust(3, 'X')
    
    if building_id and '-' in building_id:
        suffix_part = building_id.split('-')[-1]
        suffix = suffix_part[-3:].upper() if len(suffix_part) >= 3 else '001'
    else:
        suffix = uuid.uuid4().hex[:3].upper()
    
    building_code = f"{prefix}{suffix}"
    
    print(f"Generated building code: {building_code} from name: {building_name}, id: {building_id}")
    return building_code

def check_building_code_unique(building_code):
    """
    Check if building_code already exists in the database
    Returns True if unique, False if duplicate
    """
    try:
        response = buildings_table.scan(
            FilterExpression='building_code = :code',
            ExpressionAttributeValues={':code': building_code}
        )
        
        if response.get('Items') and len(response['Items']) > 0:
            print(f"Building code {building_code} already exists")
            return False
        
        return True
    except Exception as e:
        print(f"Error checking building code uniqueness: {e}")
        return True

def lambda_handler(event, context):
    try:
        print("=== ADD BUILDING ===")
        print(f"Event: {json.dumps(event, default=str)}")

        body = {}
        if event.get('body'):
            try:
                body = json.loads(event['body'])
            except json.JSONDecodeError:
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'message': 'Invalid JSON in request body',
                        'success': False
                    })
                }

        print(f"Request body: {body}")

        building_name = body.get('name')
        wings = body.get('wings', [])
        wing_details = body.get('wing_details', {})
        user_id = body.get('user_id')

        if not building_name or not wings or not wing_details or not user_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'message': 'Missing required fields: name, wings, wing_details, or user_id',
                    'success': False
                })
            }

        building_name = building_name.strip()
        if len(building_name) < 2:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'message': 'Building name must be at least 2 characters long',
                    'success': False
                })
            }

        if not isinstance(user_id, str) or len(user_id) < 10:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'message': 'Invalid user_id format',
                    'success': False
                })
            }

        if not validate_user(user_id):
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'message': 'User not found. Please register first before creating a building.',
                    'success': False,
                    'error': 'User does not exist in the system'
                })
            }

        if not isinstance(wings, list) or len(wings) == 0:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'message': 'Wings must be a non-empty array',
                    'success': False
                })
            }

        for wing in wings:
            if not isinstance(wing, str) or not wing.strip():
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'message': f'Invalid wing name: {wing}',
                        'success': False
                    })
                }

        building_id = f"BLD-{uuid.uuid4().hex[:8].upper()}"
        current_time = datetime.utcnow().isoformat()

        building_code = generate_building_code(building_name, building_id)
        
        attempts = 0
        max_attempts = 3
        while not check_building_code_unique(building_code) and attempts < max_attempts:
            attempts += 1
            print(f"Building code {building_code} exists, generating new one (attempt {attempts})")
            
            if building_id and '-' in building_id:
                suffix_part = building_id.split('-')[-1]
                new_suffix = (suffix_part[-3:].upper() + str(attempts))[:3]
            else:
                new_suffix = uuid.uuid4().hex[:3].upper()
            
            prefix = building_code[:3]
            building_code = f"{prefix}{new_suffix}"
        
        if attempts >= max_attempts:
            timestamp = str(int(datetime.utcnow().timestamp()))[-3:]
            building_code = f"BLD{timestamp}"
            print(f"Using fallback building code: {building_code}")

        total_units_of_building = 0
        processed_wings = {}

        for wing in wings:
            details = wing_details.get(wing)

            if not details:
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'message': f'Missing details for wing {wing}',
                        'success': False
                    })
                }

            total_floors = details.get('total_floors')
            units_per_floor = details.get('units_per_floor')

            if not total_floors or not units_per_floor:
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'message': f'Invalid data for wing {wing}. Need total_floors and units_per_floor',
                        'success': False
                    })
                }

            try:
                total_floors = int(total_floors)
                units_per_floor = int(units_per_floor)

                if total_floors <= 0 or total_floors > 100:
                    return {
                        'statusCode': 400,
                        'headers': {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*'
                        },
                        'body': json.dumps({
                            'message': f'Total floors for wing {wing} must be between 1 and 100',
                            'success': False
                        })
                    }

                if units_per_floor <= 0 or units_per_floor > 20:
                    return {
                        'statusCode': 400,
                        'headers': {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*'
                        },
                        'body': json.dumps({
                            'message': f'Units per floor for wing {wing} must be between 1 and 20',
                            'success': False
                        })
                    }

            except (ValueError, TypeError):
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'message': f'Invalid numeric values for wing {wing}',
                        'success': False
                    })
                }

            wing_total_units = total_floors * units_per_floor
            total_units_of_building += wing_total_units

            processed_wings[wing] = {
                'total_floors': total_floors,
                'units_per_floor': units_per_floor,
                'total_units': wing_total_units
            }

        building_item = {
            'building_id': building_id,
            'building_name': building_name,
            'building_code': building_code,  
            'user_id': user_id,
            'wings': wings,
            'wing_details': processed_wings,
            'total_wings': len(wings),
            'total_units_of_building': total_units_of_building,
            'status': 'active',
            'created_at': current_time,
            'updated_at': current_time
        }

        try:
            buildings_table.put_item(Item=building_item)
            print(f"Building created: {building_id} with code: {building_code} by user: {user_id}")
            
            role_assigned = assign_admin_role_to_user(user_id, building_id)
            if role_assigned:
                print(f"Successfully assigned 'admin' role to user {user_id} for building {building_id}")
            else:
                print(f"Warning: Could not assign admin role to user {user_id} for building {building_id}")
            
        except Exception as e:
            print(f"Error saving building: {str(e)}")
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'message': 'Failed to save building to database',
                    'success': False,
                    'error': str(e)
                })
            }

        response_data = {
            'user_id': user_id,
            'name': building_name,
            'wings': wings,
            'wing_details': wing_details,
            'building_code': building_code  
        }

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Building created successfully',
                'success': True,
                'data': response_data,
                'building_info': {
                    'building_id': building_id,
                    'building_code': building_code,  
                    'total_wings': len(wings),
                    'total_units_of_building': total_units_of_building,
                    'status': 'active',
                    'created_at': current_time,
                    'user_role': 'admin'
                }
            })
        }

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        traceback.print_exc()
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Internal server error',
                'success': False,
                'error': str(e)
            })
        }