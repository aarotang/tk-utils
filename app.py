from flask import Flask, request, jsonify
from redemption import KingdomStoryCouponRedemption  # your existing script

app = Flask(__name__)

@app.route("/redeem", methods=["POST"])
def redeem():
    data = request.json
    code = data.get("code")
    if not code:
        return jsonify({"error": "No gift code provided"}), 400

    try:
        redeemer = KingdomStoryCouponRedemption(code)
        redeemer.run_redemption()
        return jsonify({"status": "success", "message": f"Redemption complete for code {code}."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
