from flask import Flask, render_template, request, jsonify, redirect, session
from db import *
from flask_cors import CORS
import logging
import uuid
from datetime import datetime, timezone

import requests
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
from db import get_customer, get_team_secret
from ods_client import submit_delivery

app = Flask(__name__)
CORS(
    app,
    resources={r"/*": {"origins": "*"}},
    allow_headers=["Content-Type", "X-API-Key"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
)

def unauthorized():
    return {
        "status": "error",
        "data": None,
        "error": {
            "code": "UNAUTHORIZED",
            "message": "Invalid team's secret or your team doesn't have permission for this API"
        }
    }, 401

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/providers')
def providers():
    return render_template('providers.html')

@app.route("/subscriptions", methods=["GET"])
def subscriptions():
   return render_template("subscriptions.html")

# return app

@app.route('/api/v1/restock_request', methods=["GET", "POST"])
def restock_request():
   if request.method == "POST":
      if request.headers.get("X-API-Key") != "bestTeam":
         return unauthorized()
      data = request.get_json()
      return {
         "status": "success",
         "data": {"requestId": save_restock_request(data.get("vendorId"), data.get("manifest"))},
         "error": None
      }, 200


@app.route('/api/v1/stock_change', methods=["GET", "PUT", "POST"])
def stock_change():
   if request.method == "GET":
      if request.headers.get("X-API-Key") != "bestTeam":
         return {
        "status": "error",
        "data": None,
        "error": {
            "code": "UNAUTHORIZED",
            "message": "Invalid team's secret or your team doesn't have permission for this API"
        }
    }, 401
      
      return {
         "status": "success",
         "data": {"events": get_stock_events()},
         "error": None
      }, 200
   elif request.method == "PUT":
      if request.headers.get("X-API-Key") != "bestTeam":
         return unauthorized()
      data = request.get_json()
      event_id = data.get("eventId")
      status = data.get("status")
      update_event_status(event_id, status)
      return {
         "status": "success",
         "data": {"eventId": event_id, "status": status},
         "error": None
      }, 200

   elif request.method == "POST":
      # if request.headers.get("X-API-Key") != "bestTeam":
      #    return unauthorized()
      data = request.get_json()
      products = data.get("products")
      status = data.get("status")
      if not products or not status:
         return {
           "status": "error",
           "data": None,
           "error": {
              "code": "VALIDATION_ERROR",
              "message": "products and status are required"
         }
      }, 400
      event_id = save_stock_event(products, status)
      return {
          "status": "success",
          "data": {"eventId": event_id, "status": status},
          "error": None
      }, 200

# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=5001, debug=False)
if __name__ == '__main__':
   print("SERVER IS RUNNING")
   app.run(host='0.0.0.0', port=7500, debug=True)