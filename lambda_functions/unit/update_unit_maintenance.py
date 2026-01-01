import json
import boto3
import os
from datetime import datetime
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')
unit_maintenance_table = dynamodb.Table(os.environ['TABLE_UNIT_MAINTENANCE'])
users_table = dynamodb.Table(os.environ['USERS_TABLE'])

def lambda_handler(event, context):
    try:
        unit_maintenance_id = event['pathParameters']['unit_maintenance_id']
        body = json.loads(event.get('body', '{}'))
        
        # Check if exists
        existing = unit_maintenance_table.get_item(Key={'unit_maintenance_id': unit_maintenance_id})
        if 'Item' not in existing:
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'Not found'})
            }
        
        # Validate user if provided
        if 'user_id' in body:
            user_response = users_table.get_item(Key={'user_id': body['user_id']})
            if 'Item' not in user_response:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'User not found'})
                }
        
        # Prepare updates
        update_expr = "SET updated_at = :updated_at"
        expr_values = {':updated_at': datetime.utcnow().isoformat()}
        
        allowed_fields = ['status', 'payment_status', 'wings', 'floor', 
                         'unit_no', 'building_id', 'user_id', 'bill_items']
        
        for field in allowed_fields:
            if field in body:
                update_expr += f", {field} = :{field}"
                expr_values[f":{field}"] = body[field]
        
        # Update
        response = unit_maintenance_table.update_item(
            Key={'unit_maintenance_id': unit_maintenance_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
            ReturnValues='ALL_NEW'
        )
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'message': 'Updated successfully',
                'data': response['Attributes']
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
