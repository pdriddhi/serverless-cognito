import json
import boto3
import os
from datetime import datetime
import calendar


dynamodb = boto3.resource('dynamodb')
MAINTENANCE_TABLE = os.environ.get('TABLE_MAINTENANCE', 'MaintenanceRecords-dev')
PAYMENT_TABLE = os.environ.get('TABLE_PAYMENT', 'PaymentRecords-dev')

def get_month_name(month_number):
    """Convert month number to month name"""
    try:
        return calendar.month_name[int(month_number)]
    except (ValueError, IndexError):
        return ""

def lambda_handler(event, context):
    """Get maintenance details by maintenance_id"""
    print("=== GET MAINTENANCE DETAILS API ===")

    try:
        query_params = event.get('queryStringParameters', {}) or {}
        maintenance_id = query_params.get('maintenance_id')

        if not maintenance_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': False,
                    'message': 'maintenance_id parameter is required'
                })
            }

        print(f"Fetching maintenance details for ID: {maintenance_id}")

        table = dynamodb.Table(MAINTENANCE_TABLE)
        response = table.get_item(
            Key={'maintenance_id': maintenance_id}
        )

        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': False,
                    'message': 'Maintenance record not found'
                })
            }

        item = response['Item']
        payment_table = dynamodb.Table(PAYMENT_TABLE)

        payment_response = payment_table.scan(
            FilterExpression=Attr('maintenance_id').eq(maintenance_id)
        )

        payments = payment_response.get('Items', [])

        total_amount = 0
        paid_amount = 0
        unpaid_amount = 0

        for payment in payments:
            amount = float(payment.get('amount', 0))
            total_amount += amount

            if payment.get('payment_status') == 'PAID':
                paid_amount += amount
            else:
                unpaid_amount += amount

        maintenance_data = {
            'maintenance_id': item.get('maintenance_id'),
            'building_id': item.get('building_id'),
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
            'paid_amount': paid_amount,
            'unpaid_amount': unpaid_amount,
            'total_amount': total_amount
        }

        if 'month' in item and isinstance(item['month'], (int, float)):
            maintenance_data['month_number'] = item['month']

        print(f"Found maintenance record: {maintenance_data.get('name')}")

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': True,
                'message': 'Maintenance bill details retrieved successfully',
                'maintenance': maintenance_data
            }, default=str)
        }

    except Exception as e:
        print(f"Error fetching maintenance details: {str(e)}")
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
                'message': 'Failed to retrieve maintenance details',
                'error': str(e)
            })
        }
