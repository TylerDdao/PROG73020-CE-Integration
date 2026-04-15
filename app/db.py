import mysql.connector
import os
import traceback
import psycopg2
from config import Config

def get_connection():
    print("[INFO] Getting connection...")
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST", "mysql_db"),
        port=int(os.environ.get("DB_PORT", 3306)),
        user=os.environ.get("DB_USER", "appuser"),
        password=os.environ.get("DB_PASSWORD", "apppassword"),
        database=os.environ.get("DB_NAME", "inventory"),
    )

def save_restock_request(vendor_id, manifests):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        if not vendor_id or not manifests:
            raise ValueError("vendor_id or manifests missing")

        cursor.execute(
            "INSERT INTO restock_requests (vendor_id) VALUES (%s)",
            (vendor_id,)
        )
        request_id = cursor.lastrowid

        for manifest in manifests:
            product_id = manifest.get("productId")
            quantity = manifest.get("quantityOrder")

            if product_id is None or quantity is None:
                raise ValueError(f"Invalid manifest: {manifest}")

            cursor.execute(
                """INSERT INTO restock_requests_manifests 
                   (request_id, product_id, quantity_order) 
                   VALUES (%s, %s, %s)""",
                (request_id, product_id, quantity)
            )

        conn.commit()
        print(f"[INFO] Restock request {request_id} added")
        return request_id

    except Exception as e:
        conn.rollback()
        print("[ERROR] save_restock_request failed:")
        traceback.print_exc()
        return None

    finally:
        cursor.close()
        conn.close()

def save_stock_event(products, status):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        if not products :
            raise ValueError("Products missing")

        cursor.execute(
            "INSERT INTO stock_events (status) VALUES (%s)",(status,)
        )
        event_id = cursor.lastrowid

        for product in products:
            product_id = product.get("productId")
            quantity = product.get("quantityChange")
            unit = product.get("unit")

            if product_id is None or quantity is None:
                raise ValueError(f"Invalid product: {product}")

            cursor.execute(
                """INSERT INTO stock_events_products 
                   (stock_event_id, product_id, quantity_change, unit) 
                   VALUES (%s, %s, %s, %s)""",
                (event_id, product_id, quantity, unit,)
            )

        conn.commit()
        print(f"[INFO] Stock event {event_id} posted")
        return event_id

    except Exception as e:
        conn.rollback()
        print("[ERROR] save_restock_request failed:")
        traceback.print_exc()
        return None

    finally:
        cursor.close()
        conn.close()


def get_stock_events():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT 
                se.stock_event_id,
                se.status,
                sep.product_id,
                sep.quantity_change,
                sep.unit
            FROM stock_events se
            LEFT JOIN stock_events_products sep 
                ON se.stock_event_id = sep.stock_event_id
            ORDER BY se.stock_event_id
        """)

        rows = cursor.fetchall()
        events = {}

        for row in rows:
            eid = row["stock_event_id"]

            if eid not in events:
                events[eid] = {
                    "eventId": eid,
                    "status": row["status"],
                    "products": []
                }

            if row["product_id"] is not None:
                events[eid]["products"].append({
                    "productId": row["product_id"],
                    "quantityChange": row["quantity_change"],
                    "unit": row["unit"]
                })

        print("[INFO] Stock events retrieved")
        return list(events.values())

    except Exception:
        print("[ERROR] get_stock_events failed:")
        traceback.print_exc()
        return None

    finally:
        cursor.close()
        conn.close()


def update_event_status(event_id, status):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        if not event_id or not status:
            raise ValueError("Missing event_id or status")

        cursor.execute(
            "UPDATE stock_events SET status = %s WHERE stock_event_id = %s",
            (status, event_id)
        )

        if cursor.rowcount == 0:
            raise ValueError("Event not found")

        conn.commit()
        print(f"[INFO] Stock event {event_id} updated → {status}")
        return True

    except Exception:
        print("[ERROR] update_event_status failed:")
        traceback.print_exc()
        return False

    finally:
        cursor.close()
        conn.close()


def get_db_connection():
    return psycopg2.connect(
        host=Config.db_host(),
        port=Config.db_port(),
        dbname=Config.db_name(),
        user=Config.db_user(),
        password=Config.db_password()
    )


def get_customer(client_id, mobile):
    """
    Look up a customer by client_id and mobile number (C&S credentials).
    Returns the customer row dict on success, None if not found.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT client_id, address, produce, meat, dairy, delivery_count "
                "FROM customer WHERE client_id = %s AND mobile = %s LIMIT 1",
                (client_id, mobile),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            cols = ["client_id", "address", "produce", "meat", "dairy", "delivery_count"]
            return dict(zip(cols, row))
    finally:
        conn.close()


def get_team_secret():
    query = """
        SELECT secret
        FROM dtsecrets
        WHERE teamname = %s
        LIMIT 1
    """

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, (Config.team_name(),))
            row = cursor.fetchone()

            if row is None:
                raise ValueError(f"No secret found for team '{Config.team_name()}'")

            return row[0]
    finally:
        conn.close()
