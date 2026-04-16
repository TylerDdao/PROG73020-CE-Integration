import psycopg2
from psycopg2 import DatabaseError

from config import Config


# Create PostgreSQL connection using config values
def get_connection():
    return psycopg2.connect(
        host=Config.db_host(),
        dbname=Config.db_name(),
        user=Config.db_user(),
        password=Config.db_password(),
        port=Config.db_port(),
        connect_timeout=5
    )


# Insert a new delivery row
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
                str(needs_signature),  # store boolean as text if DB expects varchar
                destination_address
            )
        )

        # Save insert
        conn.commit()
        return True

    except DatabaseError:
        # Undo changes if insert fails
        conn.rollback()
        raise

    finally:
        # Always close DB objects
        cur.close()
        conn.close()


# Get all deliveries for dashboard
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


# Get one delivery using order id
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
            (order_id,)
        )

        return cur.fetchone()

    finally:
        cur.close()
        conn.close()


# Update delivery status like Received -> Delivered
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
            (new_status, order_id)
        )

        # Save update
        conn.commit()

        # Return number of rows updated
        return cur.rowcount

    except DatabaseError:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()


# Update customer category totals
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
            (produce, meat, dairy, client_id)
        )

        conn.commit()
        return cur.rowcount

    except DatabaseError:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()


# Increase completed delivery count by 1
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
            (client_id,)
        )

        conn.commit()
        return cur.rowcount

    except DatabaseError:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()


# Get customer details for outbound update
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
            (client_id,)
        )

        row = cur.fetchone()

        # Return None if customer not found
        if not row:
            return None

        # Return customer as dictionary
        return {
            "client_id": row[0],
            "produce": row[1],
            "meat": row[2],
            "dairy": row[3],
            "delivery_count": row[4]
        }

    finally:
        cur.close()
        conn.close()