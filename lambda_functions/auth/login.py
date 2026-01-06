import json
import boto3
import os
import traceback
from datetime import datetime
from botocore.exceptions import ClientError

cognito_client = boto3.client('cognito-idp')
dynamodb = boto3.resource('dynamodb')

# Environment variables
USERS_TABLE_NAME = os.environ.get('TABLE_USERS', 'Users-dev')
USER_BUILDING_ROLES_TABLE = os.environ.get('TABLE_USER_BUILDING_ROLES', 'UserBuildingRoles-dev')
USER_POOL_ID = os.environ.get('USER_POOL_ID')
CLIENT_ID = os.environ.get('COGNITO_CLIENT_ID')

print(f"Login Function - Env Variables: USER_POOL_ID={USER_POOL_ID}, CLIENT_ID={CLIENT_ID}")

users_table = dynamodb.Table(USERS_TABLE_NAME)
user_building_roles_table = dynamodb.Table(USER_BUILDING_ROLES_TABLE)

def get_consistent_user_id(mobile):
    """Get consistent user_id based on mobile number"""
    return f"user_{mobile}"

def lambda_handler(event, context):
    try:
        print("=== LOGIN STARTED ===")
        
        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event.get('body', '{}'))
        else:
            body = event.get('body', {})
            
        mobile = body.get('mobile', '').strip()
        password = body.get('password', '').strip()

        if not mobile or not password:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Credentials': 'true'
                },
                'body': json.dumps({
                    'message': 'Mobile and password are required',
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
        print(f"Login attempt for: {cognito_mobile}")

        # COGNITO AUTHENTICATION
        try:
            print("Attempting ADMIN_NO_SRP_AUTH...")
            auth_response = cognito_client.admin_initiate_auth(
                UserPoolId=USER_POOL_ID,
                ClientId=CLIENT_ID,
                AuthFlow='ADMIN_NO_SRP_AUTH',
                AuthParameters={
                    'USERNAME': cognito_mobile,
                    'PASSWORD': password
                }
            )
            
            print(f"Auth response received: {auth_response.get('ChallengeName', 'SUCCESS')}")
            
            if auth_response.get('ChallengeName') == 'NEW_PASSWORD_REQUIRED':
                print("Handling NEW_PASSWORD_REQUIRED challenge...")
                
                challenge_response = cognito_client.admin_respond_to_auth_challenge(
                    UserPoolId=USER_POOL_ID,
                    ClientId=CLIENT_ID,
                    ChallengeName='NEW_PASSWORD_REQUIRED',
                    Session=auth_response['Session'],
                    ChallengeResponses={
                        'USERNAME': cognito_mobile,
                        'NEW_PASSWORD': password
                    }
                )
                auth_result = challenge_response['AuthenticationResult']
            else:
                auth_result = auth_response['AuthenticationResult']
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            print(f"Cognito Auth Error: {error_code} - {error_message}")
            
            if error_code == 'NotAuthorizedException':
                return {
                    'statusCode': 401,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Credentials': 'true'
                    },
                    'body': json.dumps({
                        'message': 'Invalid mobile number or password',
                        'success': False
                    })
                }
            elif error_code == 'UserNotFoundException':
                return {
                    'statusCode': 404,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Credentials': 'true'
                    },
                    'body': json.dumps({
                        'message': 'User not found. Please register first.',
                        'success': False
                    })
                }
            elif error_code == 'UserNotConfirmedException':
                try:
                    print("Auto-confirming user phone number...")
                    cognito_client.admin_update_user_attributes(
                        UserPoolId=USER_POOL_ID,
                        Username=cognito_mobile,
                        UserAttributes=[
                            {'Name': 'phone_number_verified', 'Value': 'true'}
                        ]
                    )
                    
                    auth_response = cognito_client.admin_initiate_auth(
                        UserPoolId=USER_POOL_ID,
                        ClientId=CLIENT_ID,
                        AuthFlow='ADMIN_NO_SRP_AUTH',
                        AuthParameters={
                            'USERNAME': cognito_mobile,
                            'PASSWORD': password
                        }
                    )
                    auth_result = auth_response['AuthenticationResult']
                except Exception as confirm_error:
                    print(f"Auto-confirm failed: {str(confirm_error)}")
                    return {
                        'statusCode': 403,
                        'headers': {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*',
                            'Access-Control-Allow-Credentials': 'true'
                        },
                        'body': json.dumps({
                            'message': 'Please contact administrator to verify your account',
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
                        'message': f'Authentication failed: {error_message}',
                        'success': False,
                        'error_code': error_code
                    })
                }

        # Get user info from Cognito
        try:
            user_info = cognito_client.get_user(AccessToken=auth_result['AccessToken'])
            user_attributes = {attr['Name']: attr['Value'] for attr in user_info.get('UserAttributes', [])}
            name = user_attributes.get('name', '')
        except Exception as e:
            print(f"Error getting user info: {str(e)}")
            name = ''

        # DYNAMODB USERS TABLE HANDLING
        user_id = get_consistent_user_id(mobile)
        
        try:
            # Check if user exists in our Users table
            response = users_table.get_item(
                Key={'user_id': user_id}
            )
            
            if 'Item' in response:
                user_item = response['Item']
                # Update last login
                users_table.update_item(
                    Key={'user_id': user_id},
                    UpdateExpression='SET last_login = :login',
                    ExpressionAttributeValues={':login': datetime.now().isoformat()}
                )
                print(f"User found in DynamoDB: {user_id}")
            else:
                # Create new user record if doesn't exist
                users_table.put_item(
                    Item={
                        'user_id': user_id,
                        'name': name,
                        'mobile': mobile,
                        'cognito_username': cognito_mobile,
                        'status': 'active',
                        'created_at': datetime.now().isoformat(),
                        'last_login': datetime.now().isoformat()
                    }
                )
                print(f"Created new user record in DynamoDB: {user_id}")
                
        except Exception as db_error:
            print(f"Database error: {str(db_error)}")
            # Continue even if DB operation fails

        # GET USER'S BUILDING ROLES
        try:
            roles_response = user_building_roles_table.query(
                IndexName='UserIdIndex',
                KeyConditionExpression='user_id = :uid',
                ExpressionAttributeValues={':uid': user_id}
            )
            
            building_roles = roles_response.get('Items', [])
            print(f"Found {len(building_roles)} building roles for user {user_id}")
            
        except Exception as roles_error:
            print(f"Error fetching user roles: {str(roles_error)}")
            building_roles = []

        # PREPARE RESPONSE
        response_body = {
            'message': 'Login successful',
            'success': True,
            'user': {
                'user_id': user_id,
                'name': name,
                'mobile': mobile,
                'building_roles': building_roles  # Include all building roles
            },
            'tokens': {
                'id_token': auth_result.get('IdToken', ''),
                'access_token': auth_result.get('AccessToken', ''),
                'refresh_token': auth_result.get('RefreshToken', ''),
                'expires_in': auth_result.get('ExpiresIn', 3600)
            }
        }

        print(f"Login successful for user: {mobile}")
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Credentials': 'true'
            },
            'body': json.dumps(response_body)
        }

    except Exception as e:
        print(f"Unexpected login error: {str(e)}")
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Credentials': 'true'
            },
            'body': json.dumps({
                'message': 'Login failed. Please try again.',
                'success': False,
                'error': str(e)
            })
        }