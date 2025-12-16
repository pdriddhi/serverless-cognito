import json
import boto3
import uuid
from datetime import datetime
import traceback

def lambda_handler(event, context):
    """Main Lambda handler with DynamoDB integration for POST"""
    print("=== MAINTENANCE API ===")
    try:
        http_method = event.get('httpMethod', 'GET')
        path = event.get('path', '')
        print(f"Request: {http_method} {path}")

        # ===== GET /maintenance =====
        if http_method == 'GET' and path == '/maintenance':
            query_params = event.get('queryStringParameters', {}) or {}
            if 'building_id' in query_params:
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                    'body': json.dumps({
                        'message': f'GET maintenance for building {query_params["building_id"]}',
                        'success': True
                    })
                }
            else:
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                    'body': json.dumps({
                        'message': 'GET all maintenance',
                        'success': True
                    })
                }

        # ===== POST /maintenance =====
        elif http_method == 'POST' and path == '/maintenance':
            try:
                body = json.loads(event['body']) if isinstance(event.get('body'), str) else event.get('body', {})
                print(f"POST body: {body}")

                # Validate required fields
                if not body.get('building_id') or not body.get('due_date'):
                    return {
                        "statusCode": 400,
                        "headers": {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                        "body": json.dumps({"error": "building_id and due_date are required"})
                    }

                # Generate maintenance ID
                maintenance_id = f"MAINT-{uuid.uuid4().hex[:8].upper()}"

                # Prepare item to store in DynamoDB
                item = {
                    "maintenance_id": maintenance_id,
                    "building_id": body["building_id"],
                    "due_date": body["due_date"],
                    "bill_items": body.get("bill_items", []),
                    "status": "pending",
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }

                # Write item to DynamoDB
                table = boto3.resource("dynamodb").Table("MaintenanceRecords-dev")
                table.put_item(Item=item)

                # Return success response
                return {
                    "statusCode": 201,
                    "headers": {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                    "body": json.dumps({
                        "success": True,
                        "message": "Maintenance record created",
                        "maintenance_id": maintenance_id,
                        "data": item
                    })
                }

            except json.JSONDecodeError:
                return {
                    "statusCode": 400,
                    "headers": {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                    "body": json.dumps({"error": "Invalid JSON"})
                }

        # ===== Unknown endpoint =====
        else:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Endpoint not found'})
            }

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        traceback.print_exc()
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Internal server error', 'details': str(e)})
        }
