from flask import Flask, jsonify, render_template_string, request
import numpy as np
import os
import qrcode

app = Flask(__name__)

LAYOUT_FILE = "layout.png"
SPOTS_FILE = "parking_spots.npy"
QR_FOLDER = "qr_codes"
os.makedirs(QR_FOLDER, exist_ok=True)

# Load layout data
spots = np.load(SPOTS_FILE, allow_pickle=True)
spot_status = ["Free"] * len(spots)

# HTML for phone layout
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<title>Smart Parking Layout</title>
<style>
body { background-color: #111; color: white; text-align: center; font-family: Arial; }
.slot { display: inline-block; width: 100px; height: 100px; margin: 10px; border-radius: 10px; line-height: 100px; cursor: pointer; font-size: 20px; font-weight: bold; }
.free { background-color: green; }
.occupied { background-color: red; cursor: not-allowed; }
</style>
</head>
<body>
<h1>🚗 Select Your Parking Slot</h1>
<div id="slots"></div>
<p id="msg"></p>

<script>
async function loadSlots() {
    let res = await fetch('/status');
    let data = await res.json();
    let container = document.getElementById('slots');
    container.innerHTML = '';
    data.slots.forEach((s, i) => {
        let div = document.createElement('div');
        div.className = 'slot ' + (s === 'Free' ? 'free' : 'occupied');
        div.innerText = i + 1;
        if (s === 'Free') {
            div.onclick = async () => {
                let r = await fetch('/select?slot=' + (i + 1));
                let txt = await r.text();
                document.getElementById('msg').innerHTML = txt;
                loadSlots();
            };
        }
        container.appendChild(div);
    });
}
loadSlots();
setInterval(loadSlots, 3000);
</script>
</body>
</html>
"""

@app.route('/layout')
def layout():
    return render_template_string(HTML_TEMPLATE)

@app.route('/status')
def status():
    return jsonify({"slots": spot_status})

@app.route('/select')
def select():
    slot = int(request.args.get("slot", 0)) - 1
    if slot < 0 or slot >= len(spot_status):
        return "❌ Invalid slot"
    if spot_status[slot] == "Occupied":
        return "⚠ Slot already occupied!"
    spot_status[slot] = "Occupied"

    # Generate QR for exit
    qr_filename = os.path.join(QR_FOLDER, f"slot_{slot+1}_exit.png")
    qr_data = f"Exit_Slot_{slot+1}"
    qrcode.make(qr_data).save(qr_filename)

    return f"✅ Slot {slot+1} booked. Exit QR generated!"

if __name__ == "__main__":
    import socket
    ip = socket.gethostbyname(socket.gethostname())
    print(f"\n🚀 Server running at: http://{ip}:5000/layout")
    print("📱 Open this link on your phone (same Wi-Fi) to select slot.\n")
    app.run(host="0.0.0.0", port=5000)