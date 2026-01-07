import json
import boto3
import os
import uuid
from datetime import datetime
from botocore.exceptions import ClientError
import traceback

cognito_client = boto3.client('cognito-idp')
dynamodb = boto3.resource('dynamodb')

USERS_TABLE_NAME = os.environ.get('TABLE_USERS', 'Users-dev')
USER_BUILDING_ROLES_TABLE = os.environ.get('TABLE_USER_BUILDING_ROLES', 'UserBuildingRoles-dev')
USER_POOL_ID = os.environ.get('USER_POOL_ID')
CLIENT_ID = os.environ.get('COGNITO_CLIENT_ID')

print(f"Register Function - Env Variables: USER_POOL_ID={USER_POOL_ID}, CLIENT_ID={CLIENT_ID}")

users_table = dynamodb.Table(USERS_TABLE_NAME)
user_building_roles_table = dynamodb.Table(USER_BUILDING_ROLES_TABLE)

def get_consistent_user_id(mobile):
    """Get consistent user_id based on mobile number"""
    return f"user_{mobile}"

def lambda_handler(event, context):
    try:
        print("=== REGISTER STARTED ===")
        
        if isinstance(event.get('body'), str):
            body = json.loads(event.get('body', '{}'))
        else:
            body = event.get('body', {})
            
        name = body.get('name', '').strip()
        mobile = body.get('mobile', '').strip()
        password = body.get('password', '').strip()
        
        building_id = body.get('building_id', '').strip()
        role = body.get('role', 'member').strip()  # Default role is 'member'

        if not name or not mobile or not password:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Credentials': 'true'
                },
                'body': json.dumps({
                    'message': 'Name, mobile, and password are required',
                    'success': False
                })
            }

        if not mobile.isdigit() or len(mobile) != 10:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Credentials': 'true'
                },
                'body': json.dumps({
                    'message': 'Please enter a valid 10-digit mobile number',
                    'success': False
                })
            }

        if len(password) < 6:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Credentials': 'true'
                },
                'body': json.dumps({
                    'message': 'Password must be at least 6 characters',
                    'success': False
                })
            }

        # Check environment variables
        if not USER_POOL_ID or not CLIENT_ID:
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Credentials': 'true'
                },
                'body': json.dumps({
                    'message': 'Server configuration error',
                    'success': False,
                    'error': 'Cognito configuration missing'
                })
            }

        cognito_mobile = f'+91{mobile}'
        
        user_id = get_consistent_user_id(mobile)
        
        print(f"Registering user: {name}, mobile: {mobile}, user_id: {user_id}")

        try:
            user_exists_in_cognito = False
            try:
                cognito_client.admin_get_user(
                    UserPoolId=USER_POOL_ID,
                    Username=cognito_mobile
                )
                user_exists_in_cognito = True
                print(f"User already exists in Cognito: {cognito_mobile}")
            except cognito_client.exceptions.UserNotFoundException:
                user_exists_in_cognito = False
                print(f"User not found in Cognito, will create new...")
            except Exception as e:
                print(f"Error checking user in Cognito: {str(e)}")
                user_exists_in_cognito = False
            
            if not user_exists_in_cognito:
                print("Creating new user in Cognito...")
                response = cognito_client.admin_create_user(
                    UserPoolId=USER_POOL_ID,
                    Username=cognito_mobile,
                    TemporaryPassword=password,
                    MessageAction='SUPPRESS',
                    ForceAliasCreation=True,
                    UserAttributes=[
                        {'Name': 'phone_number', 'Value': cognito_mobile},
                        {'Name': 'phone_number_verified', 'Value': 'true'},
                        {'Name': 'name', 'Value': name},
                        {'Name': 'email', 'Value': f'{mobile}@example.com'}
                    ]
                )
                
                print(f"Cognito user created: {response['User']['Username']}")

                cognito_client.admin_set_user_password(
                    UserPoolId=USER_POOL_ID,
                    Username=cognito_mobile,
                    Password=password,
                    Permanent=True
                )
                
                print("Password set to permanent")
                
            else:
                print("User exists in Cognito, updating...")
                
                try:
                    cognito_client.admin_set_user_password(
                        UserPoolId=USER_POOL_ID,
                        Username=cognito_mobile,
                        Password=password,
                        Permanent=True
                    )
                    print("Updated password in Cognito")
                except Exception as password_error:
                    print(f"Could not update password: {str(password_error)}")
                
                try:
                    cognito_client.admin_update_user_attributes(
                        UserPoolId=USER_POOL_ID,
                        Username=cognito_mobile,
                        UserAttributes=[
                            {'Name': 'name', 'Value': name}
                        ]
                    )
                    print("Updated user attributes in Cognito")
                except Exception as attr_error:
                    print(f"Could not update attributes: {str(attr_error)}")

        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            print(f"Cognito error: {error_code} - {error_message}")
            
            if error_code in ['UsernameExistsException', 'AliasExistsException']:
                print(f"User already exists in Cognito, proceeding with registration...")
                try:
                    cognito_client.admin_set_user_password(
                        UserPoolId=USER_POOL_ID,
                        Username=cognito_mobile,
                        Password=password,
                        Permanent=True
                    )
                    print("Updated password for existing Cognito user")
                except Exception as update_error:
                    print(f"Could not update password: {str(update_error)}")
            else:
                # For other errors, return failure
                return {
                    'statusCode': 500,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Credentials': 'true'
                    },
                    'body': json.dumps({
                        'message': f'Registration failed: {error_message}',
                        'success': False,
                        'error_code': error_code
                    })
                }

        try:
            existing_user_response = users_table.get_item(
                Key={'user_id': user_id}
            )
            
            user_exists_in_db = 'Item' in existing_user_response
            
            if user_exists_in_db:
                # Update existing user
                users_table.update_item(
                    Key={'user_id': user_id},
                    UpdateExpression='SET #name = :name, cognito_username = :cognito, mobile = :mobile, updated_at = :updated',
                    ExpressionAttributeNames={'#name': 'name'},
                    ExpressionAttributeValues={
                        ':name': name,
                        ':cognito': cognito_mobile,
                        ':mobile': mobile,
                        ':updated': datetime.now().isoformat()
                    }
                )
                print(f"Updated existing user in DynamoDB: {user_id}")
            else:
                # Create new user
                users_table.put_item(
                    Item={
                        'user_id': user_id,
                        'cognito_username': cognito_mobile,
                        'name': name,
                        'mobile': mobile,
                        'status': 'active',
                        'created_at': datetime.now().isoformat(),
                        'updated_at': datetime.now().isoformat()
                    }
                )
                print(f"Created new user in DynamoDB: {user_id}")
                
        except Exception as e:
            print(f"Error saving to DynamoDB Users table: {str(e)}")
            # Continue even if DB save fails

        building_role_assigned = None
        if building_id:
            try:
                composite_key = f"{user_id}#{building_id}"
                
                # Check if role already exists
                try:
                    existing_role = user_building_roles_table.get_item(
                        Key={'user_building_composite': composite_key}
                    )
                    
                    if 'Item' in existing_role:
                        # Update existing role
                        user_building_roles_table.update_item(
                            Key={'user_building_composite': composite_key},
                            UpdateExpression='SET #role = :role, updated_at = :updated',
                            ExpressionAttributeNames={'#role': 'role'},
                            ExpressionAttributeValues={
                                ':role': role,
                                ':updated': datetime.now().isoformat()
                            }
                        )
                        print(f"Updated existing role to '{role}' for user {user_id} in building {building_id}")
                    else:
                        # Create new role
                        user_building_roles_table.put_item(
                            Item={
                                'user_building_composite': composite_key,
                                'user_id': user_id,
                                'building_id': building_id,
                                'role': role,
                                'created_at': datetime.now().isoformat(),
                                'updated_at': datetime.now().isoformat()
                            }
                        )
                        print(f"Assigned new role '{role}' to user {user_id} for building {building_id}")
                        
                except Exception as role_check_error:
                    print(f"Error checking existing role: {str(role_check_error)}")
                    # Create new role anyway
                    user_building_roles_table.put_item(
                        Item={
                            'user_building_composite': composite_key,
                            'user_id': user_id,
                            'building_id': building_id,
                            'role': role,
                            'created_at': datetime.now().isoformat(),
                            'updated_at': datetime.now().isoformat()
                        }
                    )
                
                building_role_assigned = {
                    'building_id': building_id,
                    'role': role
                }
            except Exception as role_error:
                print(f"Error assigning building role: {str(role_error)}")
                # Don't fail registration if role assignment fails

        response_data = {
            'message': 'Registration successful',
            'success': True,
            'user': {
                'user_id': user_id,
                'name': name,
                'mobile': mobile,
                'status': 'active'
            }
        }
        
        if building_role_assigned:
            response_data['building_role'] = building_role_assigned

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Credentials': 'true'
            },
            'body': json.dumps(response_data)
        }

    except Exception as e:
        print(f"Unexpected registration error: {str(e)}")
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Credentials': 'true'
            },
            'body': json.dumps({
                'message': 'Registration failed. Please try again.',
                'success': False,
                'error': str(e)
            })
        }