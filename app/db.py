import psycopg2
from psycopg2 import DatabaseError

from config import Config


# Create DB connection
def get_connection():
    return psycopg2.connect(
        host=Config.db_host(),
        dbname=Config.db_name(),
        user=Config.db_user(),
        password=Config.db_password(),
        port=Config.db_port(),
        connect_timeout=5,
    )


# Get customer for login
def get_customer(client_id, mobile):
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT client_id, mobile
            FROM customer
            WHERE client_id = %s AND mobile = %s
            """,
            (client_id, mobile),
        )

        row = cur.fetchone()
        if not row:
            return None

        return {
            "client_id": row[0],
            "mobile": row[1],
        }

    finally:
        cur.close()
        conn.close()


# Get team secret value
def get_team_secret():
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT secret_value
            FROM team_secret
            LIMIT 1
            """
        )

        row = cur.fetchone()
        if not row:
            return None

        return row[0]

    finally:
        cur.close()
        conn.close()


# Insert a new delivery
def create_delivery(order_id, driver_name, status, needs_signature, destination_address):
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO delivery (
                order_id,
                delivery_driver_name,
                status,
                needs_signature,
                destination_address
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                order_id,
                driver_name,
                status,
                str(needs_signature),
                destination_address,
            ),
        )
        conn.commit()
        return True

    except DatabaseError:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()


# Get all deliveries
def get_all_deliveries():
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT
                id,
                order_id,
                delivery_driver_name,
                status,
                needs_signature,
                destination_address
            FROM delivery
            ORDER BY id
            """
        )
        return cur.fetchall()

    finally:
        cur.close()
        conn.close()


# Get one delivery by order id
def get_delivery_by_order_id(order_id):
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT
                id,
                order_id,
                delivery_driver_name,
                status,
                needs_signature,
                destination_address
            FROM delivery
            WHERE order_id = %s
            """,
            (order_id,),
        )
        return cur.fetchone()

    finally:
        cur.close()
        conn.close()


# Update delivery status
def update_delivery_status(order_id, new_status):
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            UPDATE delivery
            SET status = %s
            WHERE order_id = %s
            """,
            (new_status, order_id),
        )
        conn.commit()
        return cur.rowcount

    except DatabaseError:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()


# Update produce / meat / dairy counts
def update_customer_aggregates(client_id, produce, meat, dairy):
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            UPDATE customer
            SET produce = %s,
                meat = %s,
                dairy = %s
            WHERE client_id = %s
            """,
            (produce, meat, dairy, client_id),
        )
        conn.commit()
        return cur.rowcount

    except DatabaseError:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()


# Increase delivery count
def increment_delivery_count(client_id):
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            UPDATE customer
            SET delivery_count = delivery_count + 1
            WHERE client_id = %s
            """,
            (client_id,),
        )
        conn.commit()
        return cur.rowcount

    except DatabaseError:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()


# Get customer data for outbound update
def get_customer_by_client_id(client_id):
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT
                client_id,
                produce,
                meat,
                dairy,
                delivery_count
            FROM customer
            WHERE client_id = %s
            """,
            (client_id,),
        )

        row = cur.fetchone()
        if not row:
            return None

        return {
            "client_id": row[0],
            "produce": row[1],
            "meat": row[2],
            "dairy": row[3],
            "delivery_count": row[4],
        }

    finally:
        cur.close()
        conn.close()