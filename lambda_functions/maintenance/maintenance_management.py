import json
import boto3
import uuid
import os
from datetime import datetime
import traceback
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
MAINTENANCE_TABLE = os.environ.get('TABLE_MAINTENANCE', 'MaintenanceRecords-dev')
USERS_TABLE = os.environ.get('TABLE_USERS', 'Users-dev')
BUILDINGS_TABLE = os.environ.get('TABLE_BUILDINGS', 'Buildings-dev')
USER_BUILDING_ROLES_TABLE = os.environ.get('TABLE_USER_BUILDING_ROLES', 'UserBuildingRoles-dev') 

def check_user_is_admin(user_id, building_id):
    """Check if user is admin for the given building"""
    try:
        if not USER_BUILDING_ROLES_TABLE:
            print("WARNING: USER_BUILDING_ROLES_TABLE not configured, skipping admin check")
            return False
            
        table = dynamodb.Table(USER_BUILDING_ROLES_TABLE)
        composite_key = f"{user_id}#{building_id}"
        
        response = table.get_item(Key={'user_building_composite': composite_key})
        
        if 'Item' in response:
            user_role = response['Item'].get('role')
            print(f"User role for building {building_id}: {user_role}")
            return user_role == 'admin'
        
        print(f"No role found for user {user_id} in building {building_id}")
        return False
        
    except Exception as e:
        print(f"Error checking user role: {str(e)}")
        return False

def extract_month_year(due_date):
    """Extract month and year from due_date string"""
    try:
        date_str = due_date.replace('Z', '+00:00')
        if 'T' in date_str:
            date_obj = datetime.fromisoformat(date_str)
        else:
            date_obj = datetime.strptime(date_str.split('T')[0], '%Y-%m-%d')
        return date_obj.month, date_obj.year
    except Exception:
        now = datetime.utcnow()
        return now.month, now.year

def build_response(status_code, body):
    """Helper to build response"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token',
            'Access-Control-Allow-Methods': 'POST,OPTIONS'
        },
        'body': json.dumps(body, default=str)
    }

def lambda_handler(event, context):
    """Main Lambda handler for creating maintenance records"""
    print("=== MAINTENANCE POST API ===")
    print(f"Event: {json.dumps(event, default=str)}")

    try:
        http_method = event.get('httpMethod', 'POST')
        path = event.get('path', '')

        if http_method == 'POST' and path == '/maintenance':
            try:
                body = json.loads(event['body']) if isinstance(event.get('body'), str) else event.get('body', {})
                print(f"POST body: {body}")

                required_fields = ['building_id', 'due_date', 'user_id', 'wings']
                missing_fields = [field for field in required_fields if not body.get(field)]
                
                if missing_fields:
                    return build_response(400, {
                        "success": False,
                        "message": "Missing required fields",
                        "missing_fields": missing_fields
                    })

                building_id = body["building_id"]
                user_id = body["user_id"]

                if not check_user_is_admin(user_id, building_id):
                    return build_response(403, {
                        "success": False,
                        "message": "Only building admin can create maintenance records",
                        "user_id": user_id,
                        "building_id": building_id
                    })

                wings = body.get("wings", [])
                if not isinstance(wings, list):
                    return build_response(400, {
                        "success": False,
                        "message": "wings must be a list"
                    })
                
                users_table = dynamodb.Table(USERS_TABLE)
                user_response = users_table.get_item(Key={"user_id": user_id})
                if "Item" not in user_response:
                    return build_response(403, {
                        "success": False,
                        "message": f"user_id {user_id} does not exist or is invalid"
                    })

                buildings_table = dynamodb.Table(BUILDINGS_TABLE)
                building_response = buildings_table.get_item(Key={"building_id": building_id})
                if "Item" not in building_response:
                    return build_response(403, {
                        "success": False,
                        "message": f"building_id {building_id} does not exist or is invalid"
                    })
                
                is_all_wings = len(wings) == 0
                
                due_date = body["due_date"]
                month, year = extract_month_year(due_date)
                
                maintenance_id = f"MAINT-{uuid.uuid4().hex[:8].upper()}"

                item = {
                    "maintenance_id": maintenance_id,
                    "building_id": building_id,
                    "user_id": user_id,
                    "due_date": due_date,
                    "month": month,
                    "year": year,
                    "wings": wings,
                    "is_all_wings": is_all_wings,
                    "description": body.get("description", ""),
                    "bill_items": body.get("bill_items", []),
                    "status": "pending",
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }

                table = dynamodb.Table(MAINTENANCE_TABLE)
                table.put_item(Item=item)

                return build_response(201, {
                    "success": True,
                    "message": "Maintenance record created successfully",
                    "maintenance_id": maintenance_id,
                    "data": item
                })

            except json.JSONDecodeError:
                return build_response(400, {
                    "success": False,
                    "message": "Invalid JSON in request body"
                })
            except Exception as e:
                print(f"Error creating maintenance: {str(e)}")
                traceback.print_exc()
                return build_response(500, {
                    "success": False,
                    "message": "Failed to create maintenance record",
                    "error": str(e)
                })

        elif http_method == 'OPTIONS' and path == '/maintenance':
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