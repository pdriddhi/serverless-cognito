import json
import boto3
import traceback

cognito_client = boto3.client('cognito-idp')
dynamodb = boto3.resource('dynamodb')
users_table = dynamodb.Table('Users-dev')

CLIENT_ID = '7lq01e0ltn75p29mtejaj96je8'
USER_POOL_ID = "ap-south-1_njYFt7IuH"

def lambda_handler(event, context):
    print("=== Lambda invoked ===")
    print("Received event:", event)

    try:
        body = json.loads(event.get('body', '{}'))
        print("Parsed body:", body)

        mobile = body.get('mobile')
        password = body.get('password')
        print(f"Mobile: {mobile}, Password present? {'Yes' if password else 'No'}")

        if not mobile or not password:
            response = {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Mobile and password are required'})
            }
            print("Response (missing fields):", response)
            return response

        # Format mobile for Cognito
        cognito_mobile = f'+91{mobile}'
        print("====>", cognito_mobile)
        print("====>", password)
        
        try:
            resp = cognito_client.initiate_auth(
                ClientId=CLIENT_ID,
                AuthFlow='USER_PASSWORD_AUTH',
                AuthParameters={
                    'USERNAME': cognito_mobile,
                    'PASSWORD': password
                }
            )
            print("Cognito Auth response:", resp)
        except cognito_client.exceptions.NotAuthorizedException:
            print("Cognito: NotAuthorizedException")
            return {
                'statusCode': 401,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Invalid mobile number or password'})
            }
        except cognito_client.exceptions.UserNotFoundException:
            print("Cognito: UserNotFoundException")
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'User not found'})
            }
        except cognito_client.exceptions.UserNotConfirmedException:
            print("Cognito: UserNotConfirmedException")
            return {
                'statusCode': 403,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Please verify your phone number first'})
            }

        
        auth_result = resp['AuthenticationResult']
        id_token = auth_result['IdToken']

        # Get user info from Cognito
        user_info = cognito_client.get_user(
            AccessToken=auth_result['AccessToken']
        )
        print("Cognito user info:", user_info)

        
        name = None
        for attr in user_info.get('UserAttributes', []):
            if attr['Name'] == 'name':
                name = attr['Value']
                break

        # Get user details from DynamoDB
        user_response = users_table.scan(
            FilterExpression='mobile = :mobile',
            ExpressionAttributeValues={':mobile': mobile}
        )
        print("DynamoDB user response:", user_response)

        user_type = 'resident'  # Default
        if user_response.get('Items'):
            user_details = user_response['Items'][0]
            user_type = user_details.get('user_type', 'resident')
            name = name or user_details.get('name', '')

        # Create user_id as +91{mobile}
        user_id = f'+91{mobile}'

        # Final response
        response = {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'message': 'Login successful',
                'user': {
                    'name': name or '',
                    'mobile': mobile,
                    'user_id': user_id,
                    'user_type': user_type
                },
                'tokens': {
                    'id_token': id_token,
                    'access_token': auth_result['AccessToken'],
                    'refresh_token': auth_result['RefreshToken']
                }
            })
        }
        print("Response to return:", response)
        return response

    except Exception as e:
        print(f"Login Error: {str(e)}")
        print("Traceback:", traceback.format_exc())
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Login failed. Please try again.'})
        }
