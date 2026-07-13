from flask import Flask, render_template_string, request, jsonify
import qrcode
import socket
import os

app = Flask(__name__)

# --- Get local IP address ---
def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip

# --- Layout state ---
slots = {f"S{i}": "free" for i in range(1, 8)}  # 7 slots

# --- HTML layout ---
layout_html = """
<!DOCTYPE html>
<html>
<head>
    <title>Parking Layout</title>
    <style>
        body { text-align:center; font-family: Arial; background:#f8f9fa; }
        .slot { 
            display:inline-block; 
            width:100px; height:100px; 
            margin:15px; 
            line-height:100px; 
            font-size:20px;
            border-radius:10px;
            color:white;
            cursor:pointer;
        }
        .free { background:green; }
        .occupied { background:red; }
        #exitQR { margin-top:30px; display:none; }
    </style>
</head>
<body>
    <h2>🅿 Select Your Parking Slot</h2>
    <div id="slots"></div>
    <div id="exitQR"></div>

<script>
let slots = {{ slots|tojson }};

function renderSlots() {
    let div = document.getElementById('slots');
    div.innerHTML = '';
    for (let key in slots) {
        let btn = document.createElement('div');
        btn.innerText = key;
        btn.className = 'slot ' + (slots[key] === 'free' ? 'free' : 'occupied');
        btn.onclick = () => selectSlot(key);
        div.appendChild(btn);
    }
}

function selectSlot(slot) {
    fetch('/select?slot=' + slot)
    .then(r => r.json())
    .then(data => {
        if (data.status === 'ok') {
            document.body.innerHTML = `
                <h2>✅ Slot ${slot} Selected!</h2>
                <p>Here is your Exit QR Code:</p>
                <img src="/exit_qr/${slot}" width="200">
                <p>Scan this when exiting.</p>
            `;
        } else {
            alert(data.message);
        }
    });
}

renderSlots();
</script>
</body>
</html>
"""

@app.route('/')
def layout():
    return render_template_string(layout_html, slots=slots)

@app.route('/select')
def select_slot():
    slot = request.args.get('slot')
    if not slot or slots.get(slot) == "occupied":
        return jsonify({"status": "error", "message": "Slot already occupied or invalid."})
    slots[slot] = "occupied"
    # Create QR for exit
    qr_img = qrcode.make(f"http://{get_ip()}:5000/exit?slot={slot}")
    os.makedirs("qrs", exist_ok=True)
    qr_path = f"qrs/exit_{slot}.png"
    qr_img.save(qr_path)
    return jsonify({"status": "ok", "message": "Slot selected."})

@app.route('/exit_qr/<slot>')
def show_exit_qr(slot):
    from flask import send_file
    qr_path = f"qrs/exit_{slot}.png"
    return send_file(qr_path, mimetype='image/png')

@app.route('/exit')
def exit_slot():
    slot = request.args.get('slot')
    if slot in slots:
        slots[slot] = "free"
        return f"<h2>🚗 Slot {slot} is now freed!</h2>"
    return "Invalid slot", 400


if __name__ == '__main__':
    ip = get_ip()
    url = f"http://{ip}:5000"
    print(f"\n🌐 Open this link on phone: {url}\n")

    # Generate QR for layout
    qr = qrcode.make(url)
    qr_path = "layout_qr.png"
    qr.save(qr_path)
    print(f"📱 Scan 'layout_qr.png' to open parking layout on phone.")

    os.system(f"start {qr_path}")
    app.run(host='0.0.0.0', port=5000)