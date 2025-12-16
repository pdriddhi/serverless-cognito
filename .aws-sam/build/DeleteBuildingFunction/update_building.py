import json
import boto3
import os
from datetime import datetime
from decimal import Decimal
import traceback

dynamodb = boto3.resource("dynamodb")

def lambda_handler(event, context):
    try:
        print("=" * 60)
        print("=" * 60)
        
        body = json.loads(event["body"]) if isinstance(event.get("body"), str) else event.get("body", {})
        
        print(f"Request body: {json.dumps(body, indent=2)}")
        
        building_id = body.get("building_id")
        if not building_id:
            return error_response(400, "building_id is required")

        TABLE_NAME = os.environ.get("TABLE_BUILDINGS", "Buildings-dev")
        table = dynamodb.Table(TABLE_NAME)
        
        print(f"Using table: {TABLE_NAME}")

        if "name" in body:
            body["building_name"] = body.pop("name")
            print(f" Mapped 'name' to 'building_name': {body.get('building_name')}")

        update_expr = []
        expr_names = {}
        expr_values = {}

        expr_names["#updated_at"] = "updated_at"
        expr_values[":updated_at"] = datetime.utcnow().isoformat()
        update_expr.append("#updated_at = :updated_at")

        allowed_fields = [
            "building_name",
            "wings",
            "wing_details",
            "status"
        ]

        for field in allowed_fields:
            if field in body:
                expr_names[f"#{field}"] = field
                expr_values[f":{field}"] = to_dynamo(body[field])
                update_expr.append(f"#{field} = :{field}")
                print(f" Added field to update: {field}")

        if "wing_details" in body:
            total_units = 0
            wing_details = body["wing_details"]
            print(f" Calculating total units from wing_details: {wing_details}")
            
            for wing_name, wing_data in wing_details.items():
                print(f"  Processing wing: {wing_name}, data: {wing_data}")
                
                if "total_units" in wing_data:
                    wing_units = wing_data["total_units"]
                    print(f"    Using direct total_units: {wing_units}")
                
                elif "total_floors" in wing_data and "units_per_floor" in wing_data:
                    total_floors = wing_data["total_floors"]
                    units_per_floor = wing_data["units_per_floor"]
                    wing_units = total_floors * units_per_floor
                    print(f"    Calculated: {total_floors} floors × {units_per_floor} units = {wing_units}")
                
                else:
                    wing_units = 0
                    print(f" o unit data found for wing {wing_name}")
                
                total_units += int(wing_units)
                print(f"    Running total: {total_units}")
            
            print(f"Total building units calculated: {total_units}")
            
            expr_names["#total_units_of_building"] = "total_units_of_building"
            expr_values[":total_units_of_building"] = Decimal(total_units)
            update_expr.append("#total_units_of_building = :total_units_of_building")
            print(f" Added total_units_of_building: {total_units}")

        if len(update_expr) == 1:
            return error_response(400, "No fields to update")
        
        print(f" Update Expression: SET {', '.join(update_expr)}")
        print(f" Expression Attribute Names: {expr_names}")
        print(f" Expression Attribute Values: {json.dumps(expr_values, default=str)}")

        response = table.update_item(
            Key={"building_id": building_id},
            UpdateExpression="SET " + ", ".join(update_expr),
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
            ConditionExpression="attribute_exists(building_id)",
            ReturnValues="ALL_NEW"
        )

        print(f" Update successful")
        
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "message": "Building updated successfully",
                "building": json.loads(json.dumps(response["Attributes"], default=decimal_default))
            })
        }

    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        print(f" Building not found: {building_id}")
        return error_response(404, "Building not found")

    except Exception as e:
        print(f" Error: {str(e)}")
        traceback.print_exc()
        return error_response(500, str(e))


def to_dynamo(value):
    if isinstance(value, dict):
        return {k: to_dynamo(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_dynamo(v) for v in value]
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    return value

def decimal_default(obj):
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    raise TypeError

def error_response(code, msg):
    print(f"🚨 Error response: {code} - {msg}")
    return {
        "statusCode": code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps({"message": msg})
    }
