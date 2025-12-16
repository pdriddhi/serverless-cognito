import json
import boto3
import uuid
from datetime import datetime
import random
import string

cognito_client = boto3.client('cognito-idp')
dynamodb = boto3.resource('dynamodb')
users_table = dynamodb.Table('Users-dev')

USER_POOL_ID = 'ap-south-1_njYFt7IuH'

def lambda_handler(event, context):
    try:
        print("=== REGISTER FUNCTION STARTED ===")
        body = json.loads(event['body'])

        name = body.get('name')
        mobile = body.get('mobile')
        password = body.get('password')
        user_type = body.get('user_type', 'resident')

        print(f"Registering: {name}, {mobile}")

        # Validation
        if not name or not mobile or not password:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Name, mobile and password are required'})
            }

        if not mobile.isdigit() or len(mobile) != 10:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Please enter a valid 10-digit mobile number'})
            }

        cognito_mobile = f'+91{mobile}'
        print(f"Formatted mobile: {cognito_mobile}")

        # Check if user already exists
        try:
            existing = cognito_client.admin_get_user(
                UserPoolId=USER_POOL_ID,
                Username=cognito_mobile
            )
            print(f"User already exists: {existing['Username']}")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Mobile number already registered'})
            }
        except cognito_client.exceptions.UserNotFoundException:
            print("User does not exist, proceeding with registration...")
            pass

        # Create temporary password (required by Cognito)
        temp_password = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        print(f"Generated temp password: {temp_password}")
        print(f"User provided password: {password}")

        # Step 1: Create user with temporary password
        print("Calling admin_create_user...")
        response = cognito_client.admin_create_user(
            UserPoolId=USER_POOL_ID,
            Username=cognito_mobile,
            TemporaryPassword=temp_password,
            MessageAction='SUPPRESS',  # Don't send SMS/email
            UserAttributes=[
                {'Name': 'phone_number', 'Value': cognito_mobile},
                {'Name': 'phone_number_verified', 'Value': 'true'},
                {'Name': 'name', 'Value': name}
            ]
        )
        
        user_id = response['User']['Username']
        print(f"User created with ID: {user_id}")

        # Step 2: IMMEDIATELY set permanent password
        print("Setting permanent password...")
        try:
            cognito_client.admin_set_user_password(
                UserPoolId=USER_POOL_ID,
                Username=cognito_mobile,
                Password=password,  # User's actual password
                Permanent=True
            )
            print("Permanent password set successfully")
        except Exception as password_error:
            print(f"Error setting password: {password_error}")
            # Try alternative: force change password
            try:
                cognito_client.admin_initiate_auth(
                    UserPoolId=USER_POOL_ID,
                    ClientId='7lq01e0ltn75p29mtejaj96je8',  # Your Cognito Client ID
                    AuthFlow='ADMIN_NO_SRP_AUTH',
                    AuthParameters={
                        'USERNAME': cognito_mobile,
                        'PASSWORD': temp_password
                    }
                )
                print("Admin auth successful for password change")
            except Exception as auth_error:
                print(f"Admin auth failed: {auth_error}")

        # Step 3: Store in DynamoDB
        print("Storing in DynamoDB...")
        users_table.put_item(Item={
            'user_id': user_id,
            'name': name,
            'mobile': mobile,
            'password': password,
            'cognito_mobile': cognito_mobile,
            'user_type': user_type,
            'status': 'confirmed',
            'created_at': datetime.now().isoformat()
        })
        print("DynamoDB storage successful")

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'message': 'Registration successful',
                'user': {
                    'name': name,
                    'mobile': mobile,
                    'user_id': user_id,
                    'user_type': user_type,
                    'status': 'confirmed'
                }
            })
        }
        
    except cognito_client.exceptions.UsernameExistsException:
        print("Username already exists exception")
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Mobile number already registered'})
        }
        
    except Exception as e:
        print(f"Registration Error: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Registration failed. Please try again.'})
        }
