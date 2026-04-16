import logging
import uuid
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, redirect, render_template, request, session
from flask_cors import CORS

from agnet_client import AgNetError, get_product_catalog
from cis_client import (
    CISError,
    InsufficientStockError,
    LockExpiredError,
    lock_inventory,
    request_order_lock,
    ship_locked_order,
    ship_order,
)
from cfp_client import sync_primary_files
from config import Config
from db import (
    get_customer,
    get_team_secret,
    create_delivery,
    get_all_deliveries,
    get_customer_by_client_id,
    get_delivery_by_order_id,
    increment_delivery_count,
    update_customer_aggregates,
    update_delivery_status,
)
from ods_client import submit_delivery


def create_app():
    app = Flask(__name__)
    app.secret_key = Config.SECRET_KEY
    CORS(app)

    # Sync CFP primary files on startup — non-blocking, failure is logged only
    try:
        sync_primary_files()
    except Exception as e:
        logging.getLogger(__name__).warning("CFP startup sync failed: %s", e)

    # ------------------------------------------------------------------
    # Homepage — shop (inventory from CIS + AgNet catalog)
    # ------------------------------------------------------------------

    @app.route("/", methods=["GET"])
    def index():
        _log = logging.getLogger(__name__)

        cis_items = []
        try:
            cis_resp = requests.get(
                f"{Config.CIS_BASE_URL}/inventory/pooled",
                headers={"X-API-Key": Config.CIS_API_KEY},
                timeout=8,
            )
            cis_resp.raise_for_status()
            cis_items = cis_resp.json().get("items", [])
        except Exception as e:
            _log.warning("CIS inventory fetch failed: %s", e)

        agnet_catalog = {}
        try:
            agnet_catalog = get_product_catalog()
        except AgNetError as e:
            _log.warning("AgNet catalog fetch failed: %s", e)

        return render_template(
            "index.html",
            cis_items=cis_items,
            agnet_catalog=list(agnet_catalog.values()),
            client_id=session.get("client_id"),
        )

    @app.route("/api/inventory", methods=["GET"])
    def api_inventory():
        try:
            resp = requests.get(
                f"{Config.CIS_BASE_URL}/inventory/pooled",
                headers={"X-API-Key": Config.CIS_API_KEY},
                timeout=8,
            )
            resp.raise_for_status()
            return jsonify(resp.json()), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 503

    # ------------------------------------------------------------------
    # Team secret
    # ------------------------------------------------------------------

    @app.route("/secret", methods=["GET"])
    def secret():
        secret_value = get_team_secret()
        return jsonify({"secret": secret_value}), 200

    # ------------------------------------------------------------------
    # C&S Authentication — login / callback / logout
    # ------------------------------------------------------------------

    @app.route("/login", methods=["GET", "POST"])
    def login():
        _log = logging.getLogger(__name__)

        if request.method == "GET":
            return render_template("login.html", error=None)

        client_id = (request.form.get("client_id") or "").strip()
        mobile    = (request.form.get("mobile") or "").strip()

        if not client_id or not mobile:
            return render_template("login.html", error="Please enter your Client ID and mobile number.")

        try:
            customer = get_customer(client_id, mobile)
        except Exception as e:
            _log.warning("DB error during login: %s", e)
            return render_template("login.html", error="Service unavailable. Please try again.")

        if not customer:
            return render_template("login.html", error="Invalid Client ID or mobile number.")

        import jwt as pyjwt
        from datetime import timedelta
        token = pyjwt.encode(
            {
                "client_id": customer["client_id"],
                "exp": datetime.now(timezone.utc) + timedelta(hours=4),
            },
            Config.CS_JWT_PASS,
            algorithm="HS256",
        )
        session["user_token"] = token
        session["client_id"]  = customer["client_id"]

        return redirect("/")

    @app.route("/auth/cs", methods=["GET"])
    def auth_cs():
        """Optional fallback — accepts a C&S-issued JWT via query param."""
        _log = logging.getLogger(__name__)
        token = request.args.get("token", "").strip()

        if not token:
            return redirect("/login")

        try:
            import jwt as pyjwt
            decoded = pyjwt.decode(token, Config.CS_JWT_PASS, algorithms=["HS256"])
            client_id = decoded.get("client_id")
            if not client_id:
                raise ValueError("JWT missing client_id")
            session["user_token"] = token
            session["client_id"] = client_id
        except Exception as e:
            _log.warning("C&S auth callback failed: %s", e)
            return redirect("/login")

        return redirect("/")

    @app.route("/logout", methods=["GET"])
    def logout():
        session.pop("user_token", None)
        session.pop("client_id", None)
        session.pop("cart_items", None)
        return redirect("/")

    # ------------------------------------------------------------------
    # Tyler's routes — providers, info, restock
    # ------------------------------------------------------------------

    @app.route("/providers")
    def providers():
        return render_template("providers.html")

    @app.route("/info")
    def info():
        return render_template("info.html")

    @app.route("/api/v1/restock_request", methods=["GET", "POST"])
    def restock_request():
        if request.method == "POST":
            if request.headers.get("X-API-Key") != "bestTeam":
                return {
                    "status": "error",
                    "data": None,
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": "Invalid team's secret or your team don't have permission for this API"
                    }
                }, 401
            data = request.get_json()
            print(f"vendorId: {data.get('vendorId')}")
            print(f"manifest: {data.get('manifest')}")
            return {"status": "success", "data": None, "error": None}, 200

    # ------------------------------------------------------------------
    # Legacy pass-through routes
    # ------------------------------------------------------------------

    @app.route("/orders/request", methods=["POST"])
    def orders_request():
        body = request.get_json(silent=True)
        if not body or "items" not in body:
            return jsonify({"error": "Missing required field: items"}), 400

        items = body["items"]
        if not isinstance(items, list) or len(items) == 0:
            return jsonify({"error": "items must be a non-empty list"}), 400

        try:
            result = lock_inventory(items)
            return jsonify(result), 200
        except InsufficientStockError as e:
            return jsonify({"error": str(e)}), 409
        except CISError as e:
            return jsonify({"error": str(e)}), e.status_code

    @app.route("/orders/ship", methods=["POST"])
    def orders_ship():
        body = request.get_json(silent=True)
        if not body or "order_id" not in body:
            return jsonify({"error": "Missing required field: order_id"}), 400

        order_id = body["order_id"]

        try:
            result = ship_order(order_id)
            return jsonify(result), 200
        except LockExpiredError as e:
            return jsonify({"error": str(e)}), 410
        except InsufficientStockError as e:
            return jsonify({"error": str(e)}), 409
        except CISError as e:
            return jsonify({"error": str(e)}), e.status_code

    # ------------------------------------------------------------------
    # Checkout
    # ------------------------------------------------------------------

    @app.route("/checkout/demo", methods=["GET"])
    def checkout_demo():
        session["cart_items"] = [
            {"productId": "PROD-CARROTS", "productName": "Carrots", "quantity": 2.5, "unit": "kg"},
            {"productId": "PROD-ONIONS", "productName": "Onions", "quantity": 1.0, "unit": "kg"},
            {"productId": "PROD-MILK", "productName": "Whole Milk", "quantity": 2.0, "unit": "l"},
        ]
        session["user_token"] = "demo-token"
        return redirect("/checkout")

    @app.route("/checkout/initiate", methods=["POST"])
    def checkout_initiate():
        body = request.get_json(silent=True)
        if not body or "items" not in body:
            return jsonify({"error": "Missing required field: items"}), 400

        items = body["items"]
        if not isinstance(items, list) or len(items) == 0:
            return jsonify({"error": "items must be a non-empty list"}), 400

        session["cart_items"] = items
        session["user_token"] = body.get("userToken")

        return jsonify({"redirect_url": "/checkout"}), 200

    @app.route("/checkout", methods=["GET"])
    def checkout():
        cart_items = session.get("cart_items")
        if not cart_items:
            return jsonify({"error": "No cart found. Please start from the store."}), 400

        prefill = {}
        user_token = session.get("user_token")
        if user_token:
            try:
                import jwt as pyjwt
                from cfp_client import get_client
                decoded = pyjwt.decode(user_token, Config.CS_JWT_PASS, algorithms=["HS256"])
                client = get_client(decoded.get("client_id", ""))
                if client and client.get("address"):
                    addr = client["address"]
                    parts = [p.strip() for p in addr.split(",")]
                    if len(parts) >= 3:
                        prov_postal = parts[-1].strip().split()
                        prefill = {
                            "addressLine1": parts[0],
                            "city": parts[-2].strip(),
                            "province": prov_postal[0] if prov_postal else "ON",
                            "postalCode": prov_postal[1] if len(prov_postal) > 1 else "",
                        }
            except Exception as e:
                logging.getLogger(__name__).warning("CFP address prefill failed: %s", e)

        return render_template("checkout.html", cart_items=cart_items, prefill=prefill)

    @app.route("/checkout/submit", methods=["POST"])
    def checkout_submit():
        body = request.get_json(silent=True)
        if not body:
            return jsonify({"error": "Invalid request body"}), 400

        for field in ("addressLine1", "city", "province"):
            if not body.get(field):
                return jsonify({"error": f"Missing required field: {field}"}), 400

        cart_items = body.get("items") or session.get("cart_items")
        if not cart_items:
            return jsonify({"error": "No cart found. Please start from the store."}), 400

        drop_off = body.get("dropOff", True)

        manifest = [
            {"productId": item["productId"], "quantity": item["quantity"], "unit": item["unit"]}
            for item in cart_items
        ]

        parts = [body["addressLine1"]]
        if body.get("addressLine2"):
            parts.append(body["addressLine2"])
        postal = body.get("postalCode", "").strip()
        city_line = f"{body['city']}, {body['province']}"
        if postal:
            city_line += f" {postal}"
        parts.append(city_line)
        shipping_address = ", ".join(parts)

        f2f_order_id = (
            f"F2F-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
            f"-{uuid.uuid4().hex[:8].upper()}"
        )

        try:
            lock_result = request_order_lock(f2f_order_id, shipping_address, manifest)
        except InsufficientStockError as e:
            return jsonify({"error": "out_of_stock", "message": str(e)}), 409
        except CISError as e:
            return jsonify({"error": "cis_error", "message": str(e)}), 503

        lock_order_id = lock_result["lockOrderId"]
        lock_token    = lock_result["lockToken"]

        try:
            ship_result = ship_locked_order(lock_order_id, lock_token)
        except LockExpiredError:
            return jsonify({"error": "lock_expired", "message": "Order could not be finalised. Please try again."}), 409
        except CISError as e:
            return jsonify({"error": "cis_error", "message": str(e)}), 503

        shipping_id = ship_result["shippingId"]

        destination = {
            "addressLine1": body["addressLine1"],
            "addressLine2": body.get("addressLine2", ""),
            "city": body["city"],
            "province": body["province"],
            "postalCode": body.get("postalCode", ""),
        }
        submit_delivery(f2f_order_id, shipping_id, destination, drop_off)

        user_token = session.get("user_token")
        if user_token:
            try:
                import jwt as pyjwt
                decoded = pyjwt.decode(user_token, Config.CS_JWT_PASS, algorithms=["HS256"])
                client_id = decoded.get("client_id")
                if client_id:
                    produce = sum(1 for i in cart_items if i.get("category") == "Produce")
                    meat    = sum(1 for i in cart_items if i.get("category") == "Meat")
                    dairy   = sum(1 for i in cart_items if i.get("category") == "Dairy")
                    requests.post(
                        f"{Config.CS_BASE_URL}/update-delivery",
                        json={"client_id": client_id, "produce": produce, "meat": meat, "dairy": dairy},
                        timeout=5,
                    )
            except Exception as e:
                logging.getLogger(__name__).warning("C&S update-delivery failed: %s", e)

        session.pop("cart_items", None)
        session.pop("user_token", None)

        return jsonify({
            "status": "success",
            "f2fOrderId": f2f_order_id,
            "shippingId": shipping_id,
            "message": "Your order has been placed successfully!",
        }), 200

    @app.route("/subscriptions", methods=["GET"])
    def subscriptions():
        return render_template("subscriptions.html")
    
   # ---------------------------------------------------
    # Delivery Execution routes 
    # ---------------------------------------------------

    def send_update_to_customer_and_subscriptions(client_id, produce, meat, dairy):
        payload = {
            "client_id": client_id,
            "produce": produce,
            "meat": meat,
            "dairy": dairy,
        }

        try:
            response = requests.post(
                Config.cs_update_delivery_url(),
                json=payload,
                timeout=10,
            )
            return {
                "status_code": response.status_code,
                "response_text": response.text,
            }
        except Exception as e:
            return {
                "status_code": None,
                "response_text": str(e),
            }

    # Create delivery order
    @app.route("/order", methods=["POST"])
    def create_order():
        data = request.get_json(silent=True)

        if not data:
            return jsonify({"error": "Invalid JSON body"}), 400

        warehouse_order_number = data.get("warehouseOrderNumber")
        destination = data.get("destination", {})
        special_requirements = data.get("specialRequirements", {})
        requested_at = data.get("requestedAtUtc")

        if not warehouse_order_number:
            return jsonify({"error": "warehouseOrderNumber is required"}), 400

        city = destination.get("city")
        if city not in ["Waterloo", "Kitchener", "Cambridge"]:
            return jsonify({
                "error": "City must be Waterloo, Kitchener, or Cambridge"
            }), 400

        address_parts = [
            destination.get("addressLine1", ""),
            destination.get("addressLine2", ""),
            city,
            destination.get("province", ""),
            destination.get("postalCode", ""),
        ]
        destination_address = ", ".join(part for part in address_parts if part)

        drop_off = special_requirements.get("dropOff", False)

        try:
            create_delivery(
                order_id=warehouse_order_number,
                driver_name="Unassigned",
                status="Received",
                needs_signature=not drop_off,
                destination_address=destination_address,
            )

            return jsonify({
                "status": "success",
                "data": {
                    "message": "Order received and saved to delivery table",
                    "warehouseOrderNumber": warehouse_order_number,
                    "requestedAtUtc": requested_at,
                },
                "error": None,
            }), 201

        except Exception as e:
            return jsonify({
                "status": "error",
                "data": None,
                "error": str(e),
            }), 500

    # Update customer aggregates
    @app.route("/order/aggregates", methods=["POST"])
    def order_aggregates():
        data = request.get_json(silent=True)

        if not data:
            return jsonify({"error": "Invalid JSON body"}), 400

        client_id = data.get("client_id")
        produce = data.get("produce")
        meat = data.get("meat")
        dairy = data.get("dairy")

        if not client_id or produce is None or meat is None or dairy is None:
            return jsonify({
                "error": "client_id, produce, meat, and dairy are required"
            }), 400

        try:
            updated_rows = update_customer_aggregates(client_id, produce, meat, dairy)

            if updated_rows == 0:
                return jsonify({
                    "status": "error",
                    "data": None,
                    "error": "Customer not found",
                }), 404

            return jsonify({
                "status": "success",
                "data": {
                    "client_id": client_id,
                    "produce": produce,
                    "meat": meat,
                    "dairy": dairy,
                },
                "error": None,
            }), 200

        except Exception as e:
            return jsonify({
                "status": "error",
                "data": None,
                "error": str(e),
            }), 500

    # Complete delivery
    @app.route("/order/complete", methods=["POST"])
    def complete_order():
        data = request.get_json(silent=True)

        if not data:
            return jsonify({"error": "Invalid JSON body"}), 400

        order_id = data.get("order_id")
        client_id = data.get("client_id")

        if not order_id or not client_id:
            return jsonify({"error": "order_id and client_id are required"}), 400

        try:
            updated_rows = update_delivery_status(order_id, "Delivered")
            if updated_rows == 0:
                return jsonify({
                    "status": "error",
                    "data": None,
                    "error": "Delivery not found",
                }), 404

            customer_rows = increment_delivery_count(client_id)
            if customer_rows == 0:
                return jsonify({
                    "status": "error",
                    "data": None,
                    "error": "Customer not found",
                }), 404

            customer = get_customer_by_client_id(client_id)
            if not customer:
                return jsonify({
                    "status": "error",
                    "data": None,
                    "error": "Customer not found",
                }), 404

            outbound_result = send_update_to_customer_and_subscriptions(
                client_id=customer["client_id"],
                produce=customer["produce"],
                meat=customer["meat"],
                dairy=customer["dairy"],
            )

            return jsonify({
                "status": "success",
                "data": {
                    "message": "Order marked complete",
                    "order_id": order_id,
                    "client_id": client_id,
                    "customer_update_result": outbound_result,
                },
                "error": None,
            }), 200

        except Exception as e:
            return jsonify({
                "status": "error",
                "data": None,
                "error": str(e),
            }), 500

    # Delivery dashboard
    @app.route("/delivery", methods=["GET"])
    def delivery_dashboard():
        rows = get_all_deliveries()
        deliveries = []

        for row in rows:
            deliveries.append({
                "id": row[0],
                "order_id": row[1],
                "driver": row[2],
                "status": row[3],
                "needs_signature": row[4],
                "destination_address": row[5],
            })

        return render_template("delivery_dashboard.html", deliveries=deliveries)

    # Delivery details page
    @app.route("/delivery/<order_id>", methods=["GET"])
    def delivery_details(order_id):
        row = get_delivery_by_order_id(order_id)

        if not row:
            return "Delivery not found", 404

        delivery = {
            "id": row[0],
            "order_id": row[1],
            "driver": row[2],
            "status": row[3],
            "needs_signature": row[4],
            "destination_address": row[5],
        }

        return render_template("delivery_details.html", delivery=delivery)

    
    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
