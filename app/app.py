from flask import Flask, render_template, request, jsonify, make_response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

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

# Restock request (Prod team - Supply team)
@app.route('/api/v1/restock_request', methods = ["GET", "POST"])
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
      # Supposed to save restock to a database (Will be working with Data team)
      print(f"vendorId: {data.get("vendorId")}")
      print(f"manifest: {data.get("manifest")}")
      return {
            "status": "sucess",
            "data": None,
            "error": None
         }, 200
      

@app.route("/checkout")
def checkout():
    cart_items = [
        {"name": "Sample Item", "price": 20, "quantity": 1, "image": "/static/sample.jpg"}
    ]

    subtotal = 20
    tax = 2
    total = 22

    return render_template(
        "checkout.html",
        cart_items=cart_items,
        subtotal=subtotal,
        tax=tax,
        total=total
    )
   
if __name__ == '__main__':
   app.run(host='0.0.0.0', port=7500, debug=True)

