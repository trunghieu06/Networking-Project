from flask import Flask, render_template, request
import socket
from flask import jsonify
import os
import json # <--- THÊM IMPORT JSON

TCP_SERVER_IP = "127.0.0.1"
TCP_PORT = 5001

app = Flask(__name__)

def send_tcp_command(cmd):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((TCP_SERVER_IP, TCP_PORT))
            s.sendall(cmd.encode())
            result = s.recv(16384).decode() 
        return result
    except Exception as e:
        return f"[ERROR] {e}"

# --- HÀM MỚI ĐỂ LẤY DANH SÁCH APP ---
def get_remote_apps():
    try:
        response = send_tcp_command("list_apps")
        # Nếu server trả về lỗi hoặc chuỗi không phải JSON
        if response.startswith("[ERROR]"):
            return {}
        return json.loads(response)
    except:
        return {}

@app.route("/")
def home():
    return render_template("index.html", title="Home", mode=None)

@app.route("/start")
def start_page():
    # Lấy danh sách app từ server
    app_list = get_remote_apps()
    return render_template("index.html", title="Start Application", mode="start", app_list=app_list)

@app.route("/stop")
def stop_page():
    # Lấy danh sách app từ server
    app_list = get_remote_apps()
    return render_template("index.html", title="Stop Application", mode="stop", app_list=app_list)

@app.route("/apps")
def manage_apps_page():
    # Lấy danh sách app từ server
    app_list = get_remote_apps()
    return render_template("index.html", title="Application Manager", mode="apps", app_list=app_list)

@app.route("/screenshot")
def screenshot_page():
    return render_template("index.html", title="Take Screenshot", mode="screenshot")

@app.route("/webcam")
def webcam_page():
    return render_template("index.html", title="Webcam Control", mode="webcam")

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
    try:
        os.remove("web_keylog.txt")
    except FileNotFoundError:
        pass
    keys = "[No keys logged yet]"
    return render_template("index.html", title="Keylogger", mode="keylogger", keys=keys)

@app.route("/keylogger_data")
def keylogger_data():
    try:
        with open("web_keylog.txt", "r") as f:
            keys = f.read()
    except FileNotFoundError:
        keys = ""
    return jsonify({"keys": keys})

@app.route("/logkey_web", methods=["POST"])
def logkey_web():
    key = request.json.get("key")
    if not key:
        return jsonify({"status": "error"})
    send_tcp_command(f"keylog_web {key}")
    return jsonify({"status": "ok"})

@app.route("/control", methods=["POST"])
def control_action():
    action = request.form.get("action")
    app_name = request.form.get("app")
    seconds = request.form.get("seconds") 

    if action in ("start", "stop"):
        if not app_name:
            msg = "[ERROR] Missing app name"
            # Khi render lỗi, ta cũng cần truyền lại app_list để dropdown không bị trống
            app_list = get_remote_apps()
            return render_template("index.html", title="Error", message=msg, mode=action, app_list=app_list)
        command = f"{action} {app_name}"

    elif action == "screenshot":
        command = "screenshot"

    elif action == "webcam_record":
        if not seconds or not seconds.isdigit():
            return render_template("index.html", title="Error",
                                   message="[ERROR] Invalid seconds")
        command = f"webcam_record {seconds}"

    elif action == "shutdown":
        command = "shutdown"

    elif action == "restart":
        command = "restart"

    else:
        return render_template("index.html", title="Error", message=f"[ERROR] Unknown action {action}")

    result = send_tcp_command(command)
    
    # Sau khi thực hiện start/stop, ta vẫn ở màn hình đó, nên cần load lại list
    app_list = {}
    if action in ("start", "stop"):
        app_list = get_remote_apps()
        
    # Giữ nguyên mode để user thấy kết quả ngay tại màn hình đó
    return render_template("index.html", title="Result", message=result, mode=action, app_list=app_list)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)