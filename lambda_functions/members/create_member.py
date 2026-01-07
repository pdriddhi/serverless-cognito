import json
import boto3
from datetime import datetime
import os
import traceback

dynamodb = boto3.resource('dynamodb')
members_table = dynamodb.Table(os.environ['MEMBERS_TABLE'])
users_table = dynamodb.Table(os.environ['USERS_TABLE'])

def lambda_handler(event, context):
    try:
        print(f"=== START: Create Member ===")
        
        if 'body' not in event:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Request body is missing'})
            }
        
        try:
            body = json.loads(event['body'])
        except:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Invalid JSON format'})
            }
        
        required_fields = ['user_id', 'building_id', 'name', 'mobile_no']
        for field in required_fields:
            if field not in body or not str(body.get(field, '')).strip():
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                    'body': json.dumps({'error': f'Missing or empty field: {field}'})
                }
        
        user_id = str(body['user_id']).strip()
        building_id = str(body['building_id']).strip()
        name = str(body['name']).strip()
        mobile_no = str(body['mobile_no']).strip()
        
        print(f"Processing: User={user_id}, Building={building_id}")
        
        try:
            response = users_table.get_item(Key={'user_id': user_id})
            if 'Item' not in response:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                    'body': json.dumps({'error': 'User does not exist'})
                }
            print(f"User validation passed: {user_id}")
        except Exception as e:
            print(f"Error validating user: {str(e)}")
            traceback.print_exc()
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Error validating user'})
            }
        
        try:
            response = members_table.query(
                IndexName='building-index',
                KeyConditionExpression='building_id = :b AND user_id = :u',
                ExpressionAttributeValues={
                    ':b': building_id,
                    ':u': user_id
                }
            )
            
            print(f"Duplicate check - Count: {response.get('Count', 0)}")
            
            if response.get('Count', 0) > 0:
                print(f"Duplicate found for user {user_id} in building {building_id}")
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                    'body': json.dumps({'error': 'User already exists in this building'})
                }
            
            print("No duplicate found")
            
        except Exception as e:
            print(f"Error checking duplicates: {str(e)}")
            traceback.print_exc()
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': f'Error checking duplicates: {str(e)}'})
            }
        
        now = datetime.utcnow().isoformat()
        
        member_item = {
            'user_id': user_id,
            'building_id': building_id,
            'name': name,
            'mobile_no': mobile_no,
            'created_at': now,
            'updated_at': now
        }
        
        optional_fields = ['wings', 'floor', 'unit_number', 'email', 'emergency_contact']
        for field in optional_fields:
            if field in body and body[field] is not None:
                value = str(body[field]).strip()
                if value:
                    member_item[field] = value
        
        print(f"Creating member item: {member_item}")
        
        try:
            members_table.put_item(Item=member_item)
            print("Member saved successfully to DynamoDB")
        except Exception as e:
            print(f"Error saving to DynamoDB: {str(e)}")
            traceback.print_exc()
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Error saving member'})
            }
        
        response_data = {
            'message': 'Member created successfully',
            'user_id': user_id,
            'building_id': building_id,
            'name': name,
            'mobile_no': mobile_no,
            'created_at': now
        }
        
        if 'unit_number' in member_item:
            response_data['unit_number'] = member_item['unit_number']
        if 'floor' in member_item:
            response_data['floor'] = member_item['floor']
        if 'wings' in member_item:
            response_data['wings'] = member_item['wings']
        
        print(f"=== SUCCESS: Member created ===")
        print(f"Response: {response_data}")
        
        return {
            'statusCode': 201,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps(response_data)
        }
        
    except Exception as e:
        print(f"=== UNEXPECTED ERROR ===")
        print(f"Error: {str(e)}")
        traceback.print_exc()
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Internal server error'})
        }