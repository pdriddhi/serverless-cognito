import json
import boto3
import os
import uuid
from datetime import datetime
from botocore.exceptions import ClientError
import traceback

# Initialize clients
cognito_client = boto3.client('cognito-idp')
dynamodb = boto3.resource('dynamodb')

# Environment variables with fallback
USERS_TABLE_NAME = os.environ.get('TABLE_USERS', 'Users-dev')
USER_POOL_ID = os.environ.get('USER_POOL_ID') or os.environ.get('UserPoolId')
CLIENT_ID = os.environ.get('COGNITO_CLIENT_ID') or os.environ.get('CognitoClientId') or os.environ.get('ClientId')

print(f"Register Function - Env Variables: USER_POOL_ID={USER_POOL_ID}, CLIENT_ID={CLIENT_ID}")

users_table = dynamodb.Table(USERS_TABLE_NAME)

def lambda_handler(event, context):
    try:
        print("=== REGISTER STARTED ===")
        print(f"Event: {json.dumps(event, default=str)}")
        
        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event.get('body', '{}'))
        else:
            body = event.get('body', {})
            
        name = body.get('name', '').strip()
        mobile = body.get('mobile', '').strip()
        password = body.get('password', '').strip()
        user_type = body.get('user_type', 'resident').strip()

        # Validation
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

        # Format mobile for Cognito
        cognito_mobile = f'+91{mobile}'
        user_id = str(uuid.uuid4())
        
        print(f"Registering user: {name}, mobile: {cognito_mobile}")

        # Check if user already exists in Cognito
        try:
            cognito_client.admin_get_user(
                UserPoolId=USER_POOL_ID,
                Username=cognito_mobile
            )
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Credentials': 'true'
                },
                'body': json.dumps({
                    'message': 'Mobile number already registered',
                    'success': False
                })
            }
        except cognito_client.exceptions.UserNotFoundException:
            print(f"User {cognito_mobile} not found in Cognito, proceeding with registration...")
        except ClientError as e:
            if e.response['Error']['Code'] == 'AccessDeniedException':
                print("Permission error checking existing user, proceeding anyway...")
            else:
                raise e

        # Create user in Cognito
        try:
            print(f"Creating user in Cognito...")
            
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

            # Set permanent password
            cognito_client.admin_set_user_password(
                UserPoolId=USER_POOL_ID,
                Username=cognito_mobile,
                Password=password,
                Permanent=True
            )
            
            print("Password set to permanent")

        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            print(f"Cognito error: {error_code} - {error_message}")
            
            if error_code in ['UsernameExistsException', 'AliasExistsException']:
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Credentials': 'true'
                    },
                    'body': json.dumps({
                        'message': 'Mobile number already registered',
                        'success': False
                    })
                }
            else:
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

        # Store user in DynamoDB
        try:
            users_table.put_item(
                Item={
                    'user_id': user_id,
                    'cognito_username': cognito_mobile,
                    'name': name,
                    'mobile': mobile,
                    'user_type': user_type,
                    'status': 'active',
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat()
                }
            )
            print(f"User saved to DynamoDB with ID: {user_id}")
        except Exception as e:
            print(f"Error saving to DynamoDB: {str(e)}")
            # Don't rollback Cognito user - registration is still successful

        # Return success response
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Credentials': 'true'
            },
            'body': json.dumps({
                'message': 'Registration successful',
                'success': True,
                'user': {
                    'user_id': user_id,
                    'name': name,
                    'mobile': mobile,
                    'user_type': user_type,
                    'status': 'active'
                }
            })
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
