import json
import boto3
from datetime import datetime
import os

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['MEMBERS_TABLE'])
users_table = dynamodb.Table(os.environ['USERS_TABLE'])

def validate_user(user_id):
    """
    Check if user exists in Users table
    """
    try:
        response = users_table.get_item(Key={'user_id': user_id})
        return 'Item' in response
    except Exception as e:
        print(f"Error validating user {user_id}: {str(e)}")
        return False

def lambda_handler(event, context):
    try:
        if 'pathParameters' not in event or 'user_id' not in event['pathParameters']:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'user_id is required in path parameters'})
            }
            
        user_id = event['pathParameters']['user_id']
        body = json.loads(event['body'])
        
        
        existing_member = table.get_item(Key={'user_id': user_id})
        if 'Item' not in existing_member:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Member not found'})
            }

        if 'user_id' in body:
            if not validate_user(body['user_id']):
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'error': 'User not found',
                        'message': 'Cannot update to a user_id that does not exist in the system'
                    })
                }

        if 'user_id' in body and body['user_id'] != user_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Cannot change user_id. Create a new member instead.'})
            }

        update_expression = "SET updated_at = :updated_at"
        expression_attribute_values = {
            ':updated_at': datetime.utcnow().isoformat()
        }
        expression_attribute_names = {}
        
        allowed_fields = ['name', 'mobile_no', 'wings', 'floor', 'unit_number', 'building_id']
        
        field_counter = 0
        for field in allowed_fields:
            if field in body:
                if field in ['name', 'floor']:
                    placeholder = f'#field{field_counter}'
                    expression_attribute_names[placeholder] = field
                    update_expression += f", {placeholder} = :{field}"
                else:
                    update_expression += f", {field} = :{field}"
                
                expression_attribute_values[f':{field}'] = body[field]
                field_counter += 1
        
        print(f"Update Expression: {update_expression}")
        print(f"Expression Attribute Names: {expression_attribute_names}")
        print(f"Expression Attribute Values: {expression_attribute_values}")
        
        update_params = {
            'Key': {'user_id': user_id},
            'UpdateExpression': update_expression,
            'ExpressionAttributeValues': expression_attribute_values,
            'ReturnValues': 'ALL_NEW'
        }
        
        if expression_attribute_names:
            update_params['ExpressionAttributeNames'] = expression_attribute_names
        
        response = table.update_item(**update_params)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Member updated successfully',
                'member': response['Attributes']
            })
        }
        
    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Invalid JSON format'})
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }