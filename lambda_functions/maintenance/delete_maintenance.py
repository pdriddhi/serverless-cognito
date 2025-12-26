import json
import boto3
import os

dynamodb = boto3.resource('dynamodb')
MAINTENANCE_TABLE = os.environ.get('TABLE_MAINTENANCE', 'MaintenanceRecords-dev')
PAYMENT_TABLE = os.environ.get('TABLE_PAYMENT', 'PaymentRecords-dev')

def check_payments_exist(maintenance_id):
    """Check if any payments exist for this maintenance bill"""
    try:
        table = dynamodb.Table(PAYMENT_TABLE)

        response = table.query(
            IndexName='MaintenanceIndex',
            KeyConditionExpression=boto3.dynamodb.conditions.Key('maintenance_id').eq(maintenance_id)
        )

        return len(response.get('Items', [])) > 0
    except Exception as e:
        print(f"Error checking payments: {str(e)}")
        return True

def lambda_handler(event, context):
    """Delete maintenance record by maintenance_id"""
    print("=== DELETE MAINTENANCE API ===")

    try:
        query_params = event.get('queryStringParameters', {}) or {}
        maintenance_id = query_params.get('maintenance_id')

        print(f"Query params: {query_params}")
        print(f"Maintenance ID to delete: {maintenance_id}")

        if not maintenance_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': False,
                    'message': 'maintenance_id is required in query parameters'
                })
            }

        print(f"Attempting to delete maintenance: {maintenance_id}")

        maintenance_table = dynamodb.Table(MAINTENANCE_TABLE)

        try:
            response = maintenance_table.get_item(
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

            maintenance_data = response['Item']
            building_id = maintenance_data.get('building_id')

            payments_exist = check_payments_exist(maintenance_id)

            if payments_exist:
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'success': False,
                        'message': 'Cannot delete maintenance bill because payments exist for it. Delete payments first.'
                    })
                }

            maintenance_table.delete_item(
                Key={'maintenance_id': maintenance_id}
            )

            print(f"Successfully deleted maintenance: {maintenance_id}")

            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': True,
                    'message': 'Maintenance bill deleted successfully',
                    'deleted_maintenance': {
                        'maintenance_id': maintenance_id,
                        'building_id': building_id,
                        'name': maintenance_data.get('name'),
                        'description': maintenance_data.get('description')
                    }
                })
            }

        except maintenance_table.meta.client.exceptions.ResourceNotFoundException:
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

    except Exception as e:
        print(f"Error deleting maintenance: {str(e)}")
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
                'message': 'Failed to delete maintenance bill',
                'error': str(e)
            })
        }
