import json
import boto3
import os
import traceback
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
MAINTENANCE_TABLE = os.environ.get('TABLE_MAINTENANCE', 'MaintenanceRecords-dev')
USER_BUILDING_ROLES_TABLE = os.environ.get('TABLE_USER_BUILDING_ROLES', 'UserBuildingRoles-dev')  

def check_user_access(user_id, building_id):
    """Check if user has access to this building (admin or member)"""
    try:
        if not USER_BUILDING_ROLES_TABLE:
            print("WARNING: USER_BUILDING_ROLES_TABLE not configured, skipping access check")
            return True
            
        table = dynamodb.Table(USER_BUILDING_ROLES_TABLE)
        composite_key = f"{user_id}#{building_id}"
        
        response = table.get_item(Key={'user_building_composite': composite_key})
        
        if 'Item' in response:
            user_role = response['Item'].get('role')
            print(f"User has role '{user_role}' for building {building_id}")
            return True  
        
        print(f"No access found for user {user_id} in building {building_id}")
        return False
        
    except Exception as e:
        print(f"Error checking user access: {str(e)}")
        return False

def get_month_name(month_num):
    """Convert month number to month name"""
    try:
        month_num = int(month_num)
        return datetime(1900, month_num, 1).strftime('%B')
    except Exception:
        return ""

def build_response(status_code, body):
    """Helper to build HTTP response"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token',
            'Access-Control-Allow-Methods': 'GET,OPTIONS'
        },
        'body': json.dumps(body, default=str)
    }

def lambda_handler(event, context):
    """Main Lambda handler for getting a maintenance record by maintenance_id"""
    print("=== MAINTENANCE GET API ===")
    print(f"Event: {json.dumps(event, default=str)}")

    try:
        http_method = event.get('httpMethod', 'GET')
        path = event.get('path', '')

        if http_method == 'GET' and path == '/get_maintenance':
            # Get query parameters
            query_params = event.get('queryStringParameters') or {}
            maintenance_id = query_params.get('maintenance_id')
            user_id = query_params.get('user_id') 

            if not maintenance_id:
                return build_response(400, {
                    "success": False,
                    "message": "Missing required query parameter: maintenance_id"
                })

            if not user_id:
                return build_response(400, {
                    "success": False,
                    "message": "Missing required query parameter: user_id"
                })

            try:
                table = dynamodb.Table(MAINTENANCE_TABLE)
                response = table.get_item(Key={"maintenance_id": maintenance_id})
                item = response.get("Item")

                if not item:
                    return build_response(404, {
                        "success": False,
                        "message": f"Maintenance record with ID {maintenance_id} not found"
                    })

                building_id = item.get('building_id')
                
                if not check_user_access(user_id, building_id):
                    return build_response(403, {
                        "success": False,
                        "message": "You don't have access to view this maintenance record",
                        "user_id": user_id,
                        "building_id": building_id
                    })

                data = {
                    'maintenance_id': item.get('maintenance_id'),
                    'building_id': building_id,
                    'name': item.get('name', f"Maintenance-{maintenance_id}"),
                    'description': item.get('description', ''),
                    'due_date': item.get('due_date'),
                    'month': get_month_name(item.get('month', '')),
                    'year': item.get('year'),
                    'bill_items': item.get('bill_items', []),
                    'wings': item.get('wings', []),
                    'is_all_wings': item.get('is_all_wings', False),
                    'user_id': item.get('user_id'),
                    'status': item.get('status', 'pending'),
                    'created_at': item.get('created_at')
                }

                return build_response(200, {
                    "success": True,
                    "data": data
                })

            except Exception as e:
                print(f"Error fetching maintenance: {str(e)}")
                traceback.print_exc()
                return build_response(500, {
                    "success": False,
                    "message": "Failed to fetch maintenance record",
                    "error": str(e)
                })

        elif http_method == 'OPTIONS' and path == '/get_maintenance':
            return build_response(200, {
                "success": True,
                "message": "CORS preflight successful"
            })

        else:
            return build_response(404, {
                'success': False,
                'message': 'Endpoint not found'
            })

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        traceback.print_exc()
        return build_response(500, {
            'success': False,
            'message': 'Internal server error', 
            'error': str(e)
        })