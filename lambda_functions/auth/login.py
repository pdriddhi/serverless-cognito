import json
import boto3
import os
import traceback
from botocore.exceptions import ClientError

cognito_client = boto3.client('cognito-idp')
dynamodb = boto3.resource('dynamodb')

USERS_TABLE_NAME = os.environ.get('TABLE_USERS', 'Users-dev')
USER_POOL_ID = os.environ.get('USER_POOL_ID') or os.environ.get('UserPoolId')
CLIENT_ID = os.environ.get('COGNITO_CLIENT_ID') or os.environ.get('CognitoClientId') or os.environ.get('ClientId')

print(f"Login Function - Env Variables: USER_POOL_ID={USER_POOL_ID}, CLIENT_ID={CLIENT_ID}, TABLE={USERS_TABLE_NAME}")

users_table = dynamodb.Table(USERS_TABLE_NAME)

def lambda_handler(event, context):
    try:
        print("=== LOGIN STARTED ===")
        print(f"Event: {event}")
        
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

        if 'AuthenticationResult' not in locals() and 'AuthenticationResult' not in auth_response:
            return {
                'statusCode': 401,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Credentials': 'true'
                },
                'body': json.dumps({
                    'message': 'Authentication incomplete',
                    'success': False
                })
            }

        auth_result = auth_response.get('AuthenticationResult', auth_result) if 'auth_result' not in locals() else auth_result
        
        
        try:
            user_info = cognito_client.get_user(AccessToken=auth_result['AccessToken'])
            user_attributes = {attr['Name']: attr['Value'] for attr in user_info.get('UserAttributes', [])}
            name = user_attributes.get('name', '')
        except Exception as e:
            print(f"Error getting user info: {str(e)}")
            name = ''

        try:
  
            response = users_table.query(
                IndexName='mobile-index',
                KeyConditionExpression='mobile = :m',
                ExpressionAttributeValues={':m': mobile}
            )
            
            if response.get('Items') and len(response['Items']) > 0:
                user_item = response['Items'][0]
                user_type = user_item.get('user_type', 'resident')
                user_id = user_item.get('user_id', cognito_mobile.replace('+', ''))
            else:
  
                user_id = cognito_mobile.replace('+', '')
                user_type = 'resident'
                
                users_table.put_item(
                    Item={
                        'user_id': user_id,
                        'name': name,
                        'mobile': mobile,
                        'cognito_username': cognito_mobile,
                        'user_type': user_type,
                        'status': 'active'
                    }
                )
                
        except Exception as db_error:
            print(f"Database error: {str(db_error)}")
            user_id = cognito_mobile.replace('+', '')
            user_type = 'resident'

      
        response_body = {
            'message': 'Login successful',
            'success': True,
            'user': {
                'name': name,
                'mobile': mobile,
                'user_id': user_id,
                'user_type': user_type
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
