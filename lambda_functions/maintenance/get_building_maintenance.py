import json
import boto3
import os
from datetime import datetime
import calendar
from boto3.dynamodb.conditions import Key
from auth_utils import require_auth

dynamodb = boto3.resource('dynamodb')
MAINTENANCE_TABLE = os.environ.get('TABLE_MAINTENANCE', 'MaintenanceRecords-dev')

def get_month_name(month_number):
    """Convert month number to month name"""
    try:
        return calendar.month_name[int(month_number)]
    except (ValueError, IndexError):
        return ""

def generate_maintenance_name(item):
    """Generate maintenance name from month and year"""
    month = get_month_name(item.get('month', ''))
    year = item.get('year', '')

    if month and year:
        return f"{month}-{year}-Maintenance"
    elif 'due_date' in item:
        try:
            due_date = datetime.fromisoformat(item['due_date'].replace('Z', '+00:00'))
            return due_date.strftime("%B-%Y-Maintenance")
        except:
            return f"Maintenance-{item.get('maintenance_id', '')}"
    else:
        return f"Maintenance-{item.get('maintenance_id', '')}"

def format_maintenance_bill(item):
    """Format maintenance bill as per required response"""
    return {
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
    }

@require_auth
def lambda_handler(event, context):
    """Get all maintenance bills for a building"""
    print("=== GET BUILDING MAINTENANCE API ===")
    print(f"Authenticated user: {event.get('user', {})}")

    try:
        user = event.get('user', {})
        user_building_id = user.get('building_id')
        user_type = user.get('user_type', 'resident')
        
        query_params = event.get('queryStringParameters', {}) or {}
        building_id = query_params.get('building_id')

        # If no building_id provided, use the user's building
        if not building_id and user_building_id:
            building_id = user_building_id
        
        if not building_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': False,
                    'message': 'building_id parameter is required or user must be associated with a building'
                })
            }
        
        # Authorization: Users can only access their own building's maintenance
        if user_building_id != building_id and user_type not in ['admin', 'manager']:
            return {
                'statusCode': 403,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': False,
                    'message': 'You can only access maintenance bills from your own building'
                })
            }

        print(f"Fetching maintenance bills for building: {building_id}")

        table = dynamodb.Table(MAINTENANCE_TABLE)

        response = table.query(
            IndexName='BuildingIndex',
            KeyConditionExpression=Key('building_id').eq(building_id)
        )

        items = response.get('Items', [])

        if not items:
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': True,
                    'message': 'No maintenance bills found for this building',
                    'maintenance_bills': [],
                    'count': 0
                })
            }

        maintenance_bills = [format_maintenance_bill(item) for item in items]
        maintenance_bills.sort(key=lambda x: x.get('due_date', ''), reverse=True)

        print(f"Found {len(maintenance_bills)} maintenance bills for building {building_id}")

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': True,
                'message': f'Found {len(maintenance_bills)} maintenance bills',
                'maintenance_bills': maintenance_bills,
                'count': len(maintenance_bills)
            }, default=str)
        }

    except Exception as e:
        print(f"Error fetching building maintenance: {str(e)}")
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
                'message': 'Failed to retrieve maintenance bills',
                'error': str(e)
            })
        }