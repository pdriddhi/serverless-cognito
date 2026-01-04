import json
import boto3
import uuid
import os
from datetime import datetime
import traceback
from boto3.dynamodb.conditions import Key

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb')
MAINTENANCE_TABLE = os.environ.get('TABLE_MAINTENANCE', 'MaintenanceRecords-dev')
USERS_TABLE = os.environ.get('TABLE_USERS', 'Users-dev')
BUILDINGS_TABLE = os.environ.get('TABLE_BUILDINGS', 'Buildings-dev')

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

        # ===== POST /maintenance =====
        if http_method == 'POST' and path == '/maintenance':
            try:
                # Parse request body
                body = json.loads(event['body']) if isinstance(event.get('body'), str) else event.get('body', {})
                print(f"POST body: {body}")

                # Validate required fields
                required_fields = ['building_id', 'due_date', 'user_id', 'wings']
                missing_fields = [field for field in required_fields if not body.get(field)]
                
                if missing_fields:
                    return build_response(400, {
                        "success": False,
                        "message": "Missing required fields",
                        "missing_fields": missing_fields
                    })

                # Validate wings
                wings = body.get("wings", [])
                if not isinstance(wings, list):
                    return build_response(400, {
                        "success": False,
                        "message": "wings must be a list"
                    })
                
                # ===== Validate user_id =====
                users_table = dynamodb.Table(USERS_TABLE)
                user_response = users_table.get_item(Key={"user_id": body["user_id"]})
                if "Item" not in user_response:
                    return build_response(403, {
                        "success": False,
                        "message": f"user_id {body['user_id']} does not exist or is invalid"
                    })

                # ===== Validate building_id =====
                buildings_table = dynamodb.Table(BUILDINGS_TABLE)
                building_response = buildings_table.get_item(Key={"building_id": body["building_id"]})
                if "Item" not in building_response:
                    return build_response(403, {
                        "success": False,
                        "message": f"building_id {body['building_id']} does not exist or is invalid"
                    })
                
                # Check if wings list is empty (means all wings)
                is_all_wings = len(wings) == 0
                
                # Extract month and year from due_date
                due_date = body["due_date"]
                month, year = extract_month_year(due_date)
                
                # Generate maintenance ID
                maintenance_id = f"MAINT-{uuid.uuid4().hex[:8].upper()}"

                # Prepare item to store in DynamoDB
                item = {
                    "maintenance_id": maintenance_id,
                    "building_id": body["building_id"],
                    "user_id": body["user_id"],
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

                # Write to DynamoDB
                table = dynamodb.Table(MAINTENANCE_TABLE)
                table.put_item(Item=item)

                # Return success response
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

        # ===== OPTIONS /maintenance (for CORS) =====
        elif http_method == 'OPTIONS' and path == '/maintenance':
            return build_response(200, {
                "success": True,
                "message": "CORS preflight successful"
            })

        # ===== Unknown endpoint =====
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
