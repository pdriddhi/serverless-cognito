import json
import boto3
import uuid
import os
from datetime import datetime
from decimal import Decimal
from boto3.dynamodb.conditions import Key

# ---------- AWS ----------
dynamodb = boto3.resource("dynamodb")
TABLE_NAME = os.environ["TABLE_UNIT_MAINTENANCE"]
table = dynamodb.Table(TABLE_NAME)

# ---------- Helpers ----------

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

def response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,PATCH,DELETE,OPTIONS"
        },
        "body": json.dumps(body, cls=DecimalEncoder)
    }

def calculate_bill_items(items):
    total = Decimal("0.00")
    updated_items = []

    for item in items:
        price = Decimal(str(item["price_per_unit"]))
        units = Decimal(str(item.get("units_consumed", 1)))
        item_total = price * units

        updated_items.append({
            "name": item["name"],
            "price_per_unit": price,
            "units_consumed": units,
            "item_total": item_total
        })

        total += item_total

    return updated_items, total

# ---------- Handler ----------

def lambda_handler(event, context):
    print("EVENT:", json.dumps(event))

    method = event.get("httpMethod")
    path = event.get("path")

    if method == "OPTIONS":
        return response(200, {})

    # ================= GET =================
    if method == "GET" and path == "/unit_maintenance_bill":
        params = event.get("queryStringParameters") or {}

        if not params.get("building_id"):
            return response(400, {"message": "building_id is required"})

        key_expr = Key("building_id").eq(params["building_id"])

        if params.get("maintenance_id"):
            key_expr &= Key("sk").begins_with(f"MAINT#{params['maintenance_id']}")

        res = table.query(
            IndexName="BuildingIndex",
            KeyConditionExpression=key_expr
        )

        items = res.get("Items", [])

        if params.get("user_id"):
            items = [i for i in items if i.get("user_id") == params["user_id"]]

        return response(200, {
            "success": True,
            "count": len(items),
            "data": items
        })

    # ================= POST =================
    if method == "POST" and path == "/unit_maintenance_bill":
        body = json.loads(event.get("body") or "{}")

        required = [
            "building_id",
            "maintenance_id",
            "user_id",
            "wings",
            "floor",
            "unit_no",
            "bill_items"
        ]

        missing = [f for f in required if f not in body]
        if missing:
            return response(400, {"missing_fields": missing})

        bill_items, total_amount = calculate_bill_items(body["bill_items"])

        unit_id = f"UNIT-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.utcnow().isoformat()

        item = {
            "unit_maintenance_id": unit_id,
            "building_id": body["building_id"],
            "sk": f"MAINT#{body['maintenance_id']}",
            "maintenance_id": body["maintenance_id"],
            "user_id": body["user_id"],
            "wings": body["wings"],
            "floor": str(body["floor"]),
            "unit_no": body["unit_no"],
            "bill_items": bill_items,
            "total_amount": total_amount,
            "status": "pending",
            "payment_status": "unpaid",
            "created_at": now
        }

        table.put_item(Item=item)

        return response(201, {
            "success": True,
            "data": item
        })

    # ================= PATCH =================
    if method == "PATCH" and path.startswith("/unit_maintenance_bill/"):

         path_params = event.get("pathParameters") or {}
         unit_id = path_params.get("id")

         if not unit_id:
             return response(400, {"message": "unit_maintenance_id missing in path"})

         body = json.loads(event.get("body") or "{}")

         update_expr = []
         values = {}

         for field in ["status", "payment_status", "wings", "floor", "unit_no"]:
             if field in body:
                update_expr.append(f"{field} = :{field}")
                values[f":{field}"] = body[field]

         if "bill_items" in body:
             bill_items, total_amount = calculate_bill_items(body["bill_items"])
             update_expr.append("bill_items = :bill_items")
             update_expr.append("total_amount = :total_amount")
             values[":bill_items"] = bill_items
             values[":total_amount"] = total_amount

         if not update_expr:
             return response(400, {"message": "No fields to update"})

         table.update_item(
             Key={"unit_maintenance_id": unit_id},
             UpdateExpression="SET " + ", ".join(update_expr),
             ExpressionAttributeValues=values
         )

         return response(200, {
             "success": True,
             "message": "Unit maintenance bill updated successfully"
          })

    # ================= DELETE =================
    if method == "DELETE" and path.startswith("/unit_maintenance_bill/"):
        path_params = event.get("pathParameters") or {}
        unit_id = path_params.get("id")

        if not unit_id:
            return response(400, {"message": "unit_maintenance_id missing in path"})

        table.delete_item(
            Key={"unit_maintenance_id": unit_id}
        )

        return response(200, {
            "success": True,
            "message": "Bill deleted successfully"
        })

    return response(404, {"message": "Route not found"})
