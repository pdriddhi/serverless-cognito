import json
import boto3
import os
from decimal import Decimal
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")
TABLE_NAME = os.environ["TABLE_UNIT_MAINTENANCE"]
table = dynamodb.Table(TABLE_NAME)


def decimal_to_native(obj):
    if isinstance(obj, list):
        return [decimal_to_native(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: decimal_to_native(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    else:
        return obj


def response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(decimal_to_native(body))
    }


def lambda_handler(event, context):
    print("EVENT:", json.dumps(event))

    path_params = event.get("pathParameters") or {}
    query_params = event.get("queryStringParameters") or {}

    http_method = event.get("httpMethod")
    path = event.get("path", "")

    print(f"Method: {http_method}, Path: {path}")
    print(f"Path Params: {path_params}")
    print(f"Query Params: {query_params}")

    if path_params and "unit_maintenance_id" in path_params:
        unit_maintenance_id = path_params["unit_maintenance_id"]
        print(f"Fetching by path param ID: {unit_maintenance_id}")

        try:
            res = table.get_item(
                Key={"unit_maintenance_id": unit_maintenance_id}
            )
            
            if "Item" not in res:
                return response(404, {
                    "success": False,
                    "message": "Unit maintenance not found"
                })

            return response(200, {
                "success": True,
                "data": res["Item"]
            })
        except Exception as e:
            print(f"Error fetching by ID: {str(e)}")
            return response(500, {
                "success": False,
                "message": f"Error: {str(e)}"
            })

    elif query_params and "unit_maintenance_id" in query_params:
        unit_maintenance_id = query_params["unit_maintenance_id"]
        print(f"Fetching by query param ID: {unit_maintenance_id}")

        try:
            res = table.get_item(
                Key={"unit_maintenance_id": unit_maintenance_id}
            )
            
            if "Item" not in res:
                return response(404, {
                    "success": False,
                    "message": "Unit maintenance not found"
                })

            return response(200, {
                "success": True,
                "data": res["Item"]
            })
        except Exception as e:
            print(f"Error fetching by ID: {str(e)}")
            return response(500, {
                "success": False,
                "message": f"Error: {str(e)}"
            })

    elif query_params and "building_id" in query_params:
        building_id = query_params["building_id"]
        print(f"Fetching by building: {building_id}")

        try:
            res = table.query(
                IndexName="BuildingIndex",
                KeyConditionExpression=Key("building_id").eq(building_id)
            )

            items = res.get("Items", [])

            return response(200, {
                "success": True,
                "count": len(items),
                "data": items
            })
        except Exception as e:
            print(f"Error fetching by building: {str(e)}")
            return response(500, {
                "success": False,
                "message": f"Error: {str(e)}"
            })

    elif query_params and "user_id" in query_params:
        user_id = query_params["user_id"]
        print(f"Fetching by user: {user_id}")

        try:
            res = table.query(
                IndexName="UserIndex",
                KeyConditionExpression=Key("user_id").eq(user_id)
            )

            items = res.get("Items", [])

            return response(200, {
                "success": True,
                "count": len(items),
                "data": items
            })
        except Exception as e:
            print(f"Error fetching by user: {str(e)}")
            return response(500, {
                "success": False,
                "message": f"Error: {str(e)}"
            })

    else:
        print("Fetching all records")
        try:
            res = table.scan()
            items = res.get("Items", [])

            return response(200, {
                "success": True,
                "count": len(items),
                "data": items
            })
        except Exception as e:
            print(f"Error fetching all: {str(e)}")
            return response(500, {
                "success": False,
                "message": f"Error: {str(e)}"
            })
