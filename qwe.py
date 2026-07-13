from flask import Flask, render_template_string, request, jsonify, send_file, redirect
import qrcode
import socket
import os
import threading
import cv2
import numpy as np

app = Flask(__name__)

# ---------- Get local IP ----------
def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip

# ---------- Parking Slots ----------
slots = {f"S{i}": "free" for i in range(1, 8)}
os.makedirs("qrs", exist_ok=True)

# ---------- HTML for layout ----------
layout_html = """
<!DOCTYPE html>
<html>
<head>
    <title>Smart Parking Layout</title>
    <style>
        body { text-align:center; font-family:Arial; background:#f8f9fa; }
        h2 { margin-top:20px; }
        .slot {
            display:inline-block;
            width:100px; height:100px;
            margin:15px;
            border-radius:10px;
            line-height:100px;
            color:white; font-size:22px;
            cursor:pointer; font-weight:bold;
            transition: transform 0.2s;
        }
        .slot:hover { transform:scale(1.1); }
        .free { background:green; }
        .occupied { background:red; cursor:not-allowed; }
    </style>
</head>
<body>
    <h2>🅿 Tap a Green Slot to Park</h2>
    <div id="slots"></div>

<script>
let slots = {{ slots|tojson }};

function render() {
    let div = document.getElementById("slots");
    div.innerHTML = "";
    for (let s in slots) {
        let d = document.createElement("div");
        d.innerText = s;
        d.className = "slot " + (slots[s] === "free" ? "free" : "occupied");
        d.onclick = () => selectSlot(s);
        div.appendChild(d);
    }
}

function selectSlot(slot) {
    if (slots[slot] === "occupied") {
        alert(slot + " is already occupied!");
        return;
    }
    fetch("/select?slot=" + slot)
      .then(r => r.json())
      .then(d => {
          if (d.status === "ok") {
              document.body.innerHTML = `
                  <h2>✅ ${slot} Reserved!</h2>
                  <p>Here is your Exit QR Code:</p>
                  <img src="/exit_qr/${slot}" width="250">
                  <p><a href="/exit_qr/${slot}" download="exit_${slot}.png">⬇ Download QR</a></p>
              `;
          } else {
              alert(d.message);
          }
      });
}

render();
</script>
</body>
</html>
"""

# ---------- Flask routes ----------
@app.route('/')
def home():
    return redirect('/layout')

@app.route('/layout')
def layout():
    return render_template_string(layout_html, slots=slots)

@app.route('/select')
def select_slot():
    slot = request.args.get("slot")
    if not slot or slot not in slots:
        return jsonify({"status": "error", "message": "Invalid slot"})
    if slots[slot] == "occupied":
        return jsonify({"status": "error", "message": "Slot already occupied"})
    slots[slot] = "occupied"
    qr = qrcode.make(f"http://{get_ip()}:5000/exit?slot={slot}")
    qr.save(f"qrs/{slot}.png")
    print(f"🅿 Slot {slot} booked; exit QR saved at qrs/{slot}.png")
    return jsonify({"status": "ok"})

@app.route('/exit_qr/<slot>')
def exit_qr(slot):
    return send_file(f"qrs/{slot}.png", mimetype="image/png")

@app.route('/exit')
def exit_slot():
    slot = request.args.get("slot")
    if slot in slots:
        slots[slot] = "free"
        print(f"🚗 Slot {slot} freed.")
        return f"<h2>🚗 Slot {slot} freed. Thank you!</h2>"
    return "Invalid slot", 400

# ---------- Show layout on laptop ----------
def show_layout():
    while True:
        img = np.ones((500, 1000, 3), np.uint8) * 255
        for i, (slot, state) in enumerate(slots.items()):
            x = 100 + (i % 4) * 200
            y = 100 + (i // 4) * 200
            color = (0, 255, 0) if state == "free" else (0, 0, 255)
            cv2.rectangle(img, (x, y), (x + 120, y + 120), color, -1)
            cv2.putText(img, slot, (x + 30, y + 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.imshow("Live Parking Layout", img)
        if cv2.waitKey(200) == 27:
            break
    cv2.destroyAllWindows()

# ---------- Run ----------
if __name__ == "__main__":
    ip = get_ip()
    url = f"http://{ip}:5000/"
    print(f"\n🌐 Scan this QR or open {url} on your phone.\n")
    qrcode.make(url).save("layout_qr.png")
    os.system("start layout_qr.png")

    threading.Thread(target=show_layout, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)