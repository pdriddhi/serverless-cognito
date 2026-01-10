import json
import boto3
import os
import traceback
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
TABLE_BUILDINGS = os.environ['TABLE_BUILDINGS']
TABLE_USER_BUILDING_ROLES = os.environ['TABLE_USER_BUILDING_ROLES']

table_buildings = dynamodb.Table(TABLE_BUILDINGS)
table_user_roles = dynamodb.Table(TABLE_USER_BUILDING_ROLES)

def lambda_handler(event, context):
    print("=== GET USER BUILDINGS (INCLUDING CONNECTED) ===")
    print(f"Event: {json.dumps(event, default=str)}")

    try:
        query_params = event.get('queryStringParameters') or {}
        user_id = query_params.get('user_id')
        
        print(f"Query params: {query_params}")
        print(f"Looking for ALL buildings for user_id: {user_id}")

        if not user_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'message': 'user_id is required in query parameters',
                    'success': False
                })
            }

        # STEP 1: Get owned buildings (user is the building owner/creator)
        print("Getting owned buildings...")
        owned_buildings = []
        try:
            buildings_response = table_buildings.query(
                IndexName='UserIDIndex',
                KeyConditionExpression='user_id = :uid',
                ExpressionAttributeValues={
                    ':uid': user_id
                }
            )
            owned_buildings = buildings_response.get('Items', [])
            print(f"Found {len(owned_buildings)} owned buildings")
            
        except Exception as e:
            print(f"Error querying owned buildings: {str(e)}")
            # Fallback to scan
            try:
                buildings_response = table_buildings.scan(
                    FilterExpression='user_id = :uid',
                    ExpressionAttributeValues={
                        ':uid': user_id
                    }
                )
                owned_buildings = buildings_response.get('Items', [])
            except Exception as scan_error:
                print(f"Scan also failed: {str(scan_error)}")

        # STEP 2: Get buildings where user has roles (resident, admin, etc.)
        print("Getting connected buildings via UserBuildingRoles...")
        connected_buildings = []
        try:
            # Query UserBuildingRoles table for user's roles
            roles_response = table_user_roles.query(
                IndexName='UserIdIndex',
                KeyConditionExpression='user_id = :uid',
                ExpressionAttributeValues={
                    ':uid': user_id
                }
            )
            user_roles = roles_response.get('Items', [])
            print(f"Found {len(user_roles)} role entries for user")
            
            # Get building details for each role
            for role_item in user_roles:
                building_id = role_item.get('building_id')
                if not building_id:
                    continue
                    
                # Skip if this building is already in owned_buildings
                if any(b.get('building_id') == building_id for b in owned_buildings):
                    continue
                    
                try:
                    # Get building details
                    building_response = table_buildings.get_item(
                        Key={'building_id': building_id}
                    )
                    
                    if 'Item' in building_response:
                        building = building_response['Item']
                        
                        # Prepare building data with role info
                        building_data = {
                            'building_id': building.get('building_id'),
                            'building_name': building.get('building_name'),
                            'name': building.get('building_name'),
                            'building_code': building.get('building_code', ''),
                            'address': building.get('address', ''),
                            'user_id': building.get('user_id'),  # Building owner
                            'wings': building.get('wings', []),
                            'wing_details': building.get('wing_details', {}),
                            'total_wings': building.get('total_wings', 0),
                            'total_floors': building.get('total_floors', 0),
                            'total_units': building.get('total_units', building.get('total_units_of_building', 0)),
                            'created_at': building.get('created_at'),
                            'updated_at': building.get('updated_at'),
                            'status': building.get('status', 'active'),
                            
                            # Role info
                            'role': role_item.get('role', 'resident'),
                            'role_status': role_item.get('status', 'active'),
                            'approved_at': role_item.get('approved_at', role_item.get('created_at')),
                            'approved_by': role_item.get('approved_by'),
                            'wing': role_item.get('wing'),
                            'floor': role_item.get('floor'),
                            'unit_number': role_item.get('unit_number'),
                            'is_owner': False,
                            'is_connected': True
                        }
                        
                        connected_buildings.append(building_data)
                        
                except Exception as e:
                    print(f"Error getting building {building_id}: {str(e)}")
                    continue
                    
        except Exception as e:
            print(f"Error querying user roles: {str(e)}")

        # STEP 3: Combine all buildings
        all_buildings = []
        
        # Add owned buildings first (mark as owner)
        for building in owned_buildings:
            building_data = {
                'building_id': building.get('building_id'),
                'building_name': building.get('building_name'),
                'name': building.get('building_name'),
                'building_code': building.get('building_code', ''),
                'address': building.get('address', ''),
                'user_id': building.get('user_id'),
                'wings': building.get('wings', []),
                'wing_details': building.get('wing_details', {}),
                'total_wings': building.get('total_wings', 0),
                'total_floors': building.get('total_floors', 0),
                'total_units': building.get('total_units', building.get('total_units_of_building', 0)),
                'created_at': building.get('created_at'),
                'updated_at': building.get('updated_at'),
                'status': building.get('status', 'active'),
                'role': 'owner',
                'role_status': 'active',
                'is_owner': True,
                'is_connected': False
            }
            all_buildings.append(building_data)
        
        # Add connected buildings
        all_buildings.extend(connected_buildings)
        
        print(f"Total buildings found: {len(all_buildings)}")
        print(f"  - Owned: {len(owned_buildings)}")
        print(f"  - Connected: {len(connected_buildings)}")

        if not all_buildings:
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'message': 'No buildings found for this user',
                    'success': True,
                    'user_id': user_id,
                    'all_buildings': [],
                    'total_buildings': 0,
                    'owned_count': 0,
                    'connected_count': 0
                }, default=str)
            }

        # STEP 4: Prepare response (maintain backward compatibility)
        first_building = all_buildings[0] if all_buildings else {}
        
        response_body = {
            'message': 'Building(s) found successfully',
            'success': True,
            'user_id': user_id,
            'total_buildings': len(all_buildings),
            'owned_count': len(owned_buildings),
            'connected_count': len(connected_buildings),
            
            # For backward compatibility - first building details
            'building': {
                'building_id': first_building.get('building_id'),
                'building_name': first_building.get('building_name'),
                'name': first_building.get('building_name'),
                'building_code': first_building.get('building_code', ''),
                'user_id': first_building.get('user_id'),
                'wings': first_building.get('wings', []),
                'wing_details': first_building.get('wing_details', {}),
                'total_wings': first_building.get('total_wings'),
                'total_units_of_building': first_building.get('total_units', first_building.get('total_units_of_building', 0)),
                'created_at': first_building.get('created_at'),
                'updated_at': first_building.get('updated_at'),
                'status': first_building.get('status', 'active'),
                'role': first_building.get('role', 'owner'),
                'is_owner': first_building.get('is_owner', False)
            },
            
            # All buildings with role info
            'all_buildings': all_buildings,
            
            # Additional info for frontend
            'buildings_summary': {
                'total': len(all_buildings),
                'owned': len(owned_buildings),
                'connected': len(connected_buildings),
                'roles': {
                    'owner': len(owned_buildings),
                    'resident': len([b for b in connected_buildings if b.get('role') == 'resident']),
                    'admin': len([b for b in connected_buildings if b.get('role') == 'admin']),
                    'staff': len([b for b in connected_buildings if b.get('role') == 'staff'])
                }
            }
        }

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_body, default=str)
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