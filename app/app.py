from flask import Flask, render_template, request
from db import save_restock_request, get_stock_events, update_event_status
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

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

@app.route('/info')
def info():
    return render_template('info.html')


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


@app.route('/api/v1/stock_change', methods=["GET", "PUT"])
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

if __name__ == '__main__':
   print("SERVER IS RUNNING")
   app.run(host='0.0.0.0', port=7500, debug=True)