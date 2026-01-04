import json
import os
import boto3
import traceback
from boto3.dynamodb.conditions import Key
from calendar import month_name

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb')
MAINTENANCE_TABLE = os.environ.get('TABLE_MAINTENANCE', 'MaintenanceRecords-dev')

def get_month_name(month_number):
    """Convert month number to month name, e.g., 1 -> January"""
    try:
        month_number = int(month_number)
        if 1 <= month_number <= 12:
            return month_name[month_number]
    except:
        pass
    return ""

def generate_maintenance_name(item):
    """Generate maintenance name if not present"""
    return f"Maintenance - {item.get('month', '')}/{item.get('year', '')}"

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
    """GET /get_building_maintenance Lambda handler"""
    print("=== GET BUILDING MAINTENANCE API ===")
    print(f"Event: {json.dumps(event, default=str)}")

    try:
        http_method = event.get('httpMethod', 'GET')
        path = event.get('path', '')

        if http_method == 'GET':
            query_params = event.get('queryStringParameters', {}) or {}
            building_id = query_params.get('building_id')

            if not building_id:
                return build_response(400, {
                    "success": False,
                    "message": "building_id is required"
                })

            try:
                table = dynamodb.Table(MAINTENANCE_TABLE)

                response = table.query(
                    IndexName='BuildingIndex',
                    KeyConditionExpression=Key('building_id').eq(building_id)
                )

                items = response.get('Items', [])

                # Prepare response data
                data = []
                for item in items:
                    data.append({
                        'maintenance_id': item.get('maintenance_id'),
                        'building_id': item.get('building_id'),
                        'name': item.get('name') or generate_maintenance_name(item),
                        'description': item.get('description', ''),
                        'due_date': item.get('due_date'),
                        'month': get_month_name(item.get('month', '')),
                        'year': item.get('year'),
                        'bill_items': item.get('bill_items', []),
                        'created_at': item.get('created_at'),
                        'wings': item.get('wings', []),
                        'is_all_wings': item.get('is_all_wings', False),
                        'status': item.get('status', 'pending'),
                        'user_id': item.get('user_id')
                    })

                return build_response(200, {
                    "success": True,
                    "building_id": building_id,
                    "total_records": len(data),
                    "data": data
                })

            except Exception as e:
                print(f"Error fetching maintenance records: {str(e)}")
                traceback.print_exc()
                return build_response(500, {
                    "success": False,
                    "message": "Failed to fetch maintenance records",
                    "error": str(e)
                })

        elif http_method == 'OPTIONS' and path == '/get_building_maintenance':
            return build_response(200, {
                "success": True,
                "message": "CORS preflight successful"
            })

        else:
            return build_response(404, {
                "success": False,
                "message": "Endpoint not found"
            })

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        traceback.print_exc()
        return build_response(500, {
            "success": False,
            "message": "Internal server error",
            "error": str(e)
        })
