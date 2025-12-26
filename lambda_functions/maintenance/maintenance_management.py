import json
import boto3
import uuid
from datetime import datetime
import traceback

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb')
MAINTENANCE_TABLE = "MaintenanceRecords-dev"

def extract_month_year(due_date):
    """Extract month and year from due_date string"""
    try:
        # Handle different date formats
        date_str = due_date.replace('Z', '+00:00')
        if 'T' in date_str:
            date_obj = datetime.fromisoformat(date_str)
        else:
            date_obj = datetime.strptime(date_str.split('T')[0], '%Y-%m-%d')
        return date_obj.month, date_obj.year
    except Exception:
        # Fallback to current month/year
        now = datetime.utcnow()
        return now.month, now.year

def build_response(status_code, body):
    """Helper to build response"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(body, default=str)
    }

def lambda_handler(event, context):
    """Main Lambda handler"""
    print("=== MAINTENANCE API ===")
    
    try:
        http_method = event.get('httpMethod', 'GET')
        path = event.get('path', '')
        print(f"Request: {http_method} {path}")

        # ===== GET /maintenance =====
        if http_method == 'GET' and path == '/maintenance':
            query_params = event.get('queryStringParameters', {}) or {}
            
            if 'building_id' not in query_params:
                return build_response(400, {
                    'success': False,
                    'message': 'Please provide building_id parameter'
                })
            
            try:
                # Get maintenance records for specific building
                table = dynamodb.Table(MAINTENANCE_TABLE)
                
                response = table.query(
                    IndexName='BuildingIndex',
                    KeyConditionExpression=boto3.dynamodb.conditions.Key('building_id').eq(
                        query_params['building_id']
                    )
                )
                
                items = response.get('Items', [])
                print(f"Found {len(items)} maintenance records for building {query_params['building_id']}")
                
                return build_response(200, {
                    'success': True,
                    'message': f'Found {len(items)} maintenance records',
                    'data': items
                })
                
            except Exception as e:
                print(f"Error querying maintenance: {str(e)}")
                return build_response(500, {
                    'success': False,
                    'error': 'Failed to fetch maintenance records'
                })

        # ===== POST /maintenance =====
        elif http_method == 'POST' and path == '/maintenance':
            try:
                # Parse request body
                body = json.loads(event['body']) if isinstance(event.get('body'), str) else event.get('body', {})
                print(f"POST body: {body}")

                # Validate required fields
                required_fields = ['building_id', 'due_date', 'user_id', 'wings']
                missing_fields = [field for field in required_fields if not body.get(field)]
                
                if missing_fields:
                    return build_response(400, {
                        "error": "Missing required fields",
                        "missing_fields": missing_fields
                    })
                
                # Validate wings
                wings = body.get("wings", [])
                if not isinstance(wings, list):
                    return build_response(400, {
                        "error": "wings must be a list"
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
                    "month": month,           # NEW: Added month field
                    "year": year,            # NEW: Added year field
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
                    "error": "Invalid JSON in request body"
                })

        # ===== Unknown endpoint =====
        else:
            return build_response(404, {
                'error': 'Endpoint not found'
            })

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        traceback.print_exc()
        return build_response(500, {
            'error': 'Internal server error', 
            'details': str(e)
        })
