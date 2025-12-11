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

HOST = "0.0.0.0"
PORT = 5001

# --- BIẾN TOÀN CỤC CHO CAMERA ---
global_cap = None
global_frame = None
camera_lock = threading.Lock()
is_camera_running = True

# --- HÀM CHẠY NGẦM: ĐỌC CAMERA LIÊN TỤC ---
def camera_loop():
    global global_cap, global_frame
    
    # 1. Mở camera (Thử index 0 hoặc 1 nếu dùng iPhone continuity)
    # Tăng độ phân giải lên HD
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    
    # Chỉnh FPS (nếu camera hỗ trợ)
    cap.set(cv2.CAP_PROP_FPS, 30)

    if not cap.isOpened():
        print("[WARNING] Could not open Global Camera thread.")
        return

    global_cap = cap
    print("[INFO] Global Camera started (HD mode).")

    while is_camera_running:
        ret, frame = cap.read()
        if ret:
            with camera_lock:
                global_frame = frame
        else:
            time.sleep(0.1)
    
    cap.release()
    print("[INFO] Global Camera stopped.")

# Khởi động luồng camera ngay khi chạy server
threading.Thread(target=camera_loop, daemon=True).start()


# --- HÀM QUÉT APP ---
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

# --- CÁC HÀM START/STOP/CHECK ---
def is_app_running(name):
    try:
        subprocess.check_output(["pgrep", "-f", name])
        return True
    except:
        return False

def start_app(app_name):
    if is_app_running(app_name): return f"[INFO] {app_name} already running"
    try:
        subprocess.run(["open", "-a", app_name], check=True)
        time.sleep(1)
        return f"[OK] Started {app_name}"
    except Exception as e: return f"[ERROR] Failed to start {app_name}: {e}"

def stop_app(app_name):
    subprocess.run(["osascript", "-e", f'quit app "{app_name}"'])
    time.sleep(0.5)
    if not is_app_running(app_name): return f"[OK] Stopped {app_name}"
    subprocess.run(["pkill", "-f", app_name], check=False)
    return f"[OK] Attempted to stop {app_name}"

# --- HÀM CHỤP MÀN HÌNH STREAM ---
def capture_screen_bytes():
    try:
        img = ImageGrab.grab()
        
        # --- THÊM DÒNG NÀY ĐỂ SỬA LỖI ---
        # Chuyển đổi từ RGBA (có độ trong suốt) sang RGB (chỉ màu sắc)
        img = img.convert("RGB") 
        # -------------------------------

        # Resize nhẹ để giảm lag mạng (nhưng vẫn giữ độ nét tương đối)
        img.thumbnail((1600, 900)) 
        
        img_byte_arr = io.BytesIO()
        # Tăng chất lượng JPEG lên 80
        img.save(img_byte_arr, format='JPEG', quality=80)
        return img_byte_arr.getvalue()
    except Exception as e:
        print(f"[ERROR] Screen capture: {e}")
        return None

# --- HÀM LẤY ẢNH TỪ GLOBAL CAMERA ---
def capture_webcam_bytes():
    with camera_lock:
        if global_frame is None:
            return None
        # Copy frame để tránh conflict khi đang encode
        frame_copy = global_frame.copy()
    
    try:
        # Nén JPEG với chất lượng cao (90)
        # Gửi màu gốc (không bị trắng đen)
        _, buffer = cv2.imencode('.jpg', frame_copy, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        return buffer.tobytes()
    except Exception as e:
        print(f"[ERROR] Webcam encode: {e}")
        return None

# --- CÁC HÀM KHÁC ---
def take_screenshot():
    try:
        os.makedirs("screenshots", exist_ok=True)
        filename = f"screenshots/shot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        subprocess.run(["screencapture", "-x", filename])
        return f"[OK] Screenshot saved: {filename}"
    except Exception as e: return f"[ERROR] {e}"

def record_webcam(seconds):
    # LƯU Ý: Khi dùng Global Camera, hàm này cần mượn frame từ global
    # thay vì mở lại VideoCapture(0) (sẽ gây lỗi conflict thiết bị)
    
    out = None
    try:
        os.makedirs("recordings", exist_ok=True)
        filename = f"recordings/webcam_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        
        # Lấy kích thước từ frame hiện tại
        with camera_lock:
            if global_frame is None: return "[ERROR] Camera not ready"
            height, width, _ = global_frame.shape

        fourcc = cv2.VideoWriter_fourcc(*'avc1')
        out = cv2.VideoWriter(filename, fourcc, 30.0, (width, height))
        
        print(f"[INFO] Recording to {filename}...")
        start_time = time.time()
        
        while (time.time() - start_time) < seconds:
            # Lấy frame từ luồng global
            with camera_lock:
                if global_frame is not None:
                    out.write(global_frame)
            # Ngủ đúng bằng thời gian 1 frame (1/30s)
            time.sleep(0.033)

        return f"[OK] Saved to {os.path.abspath(filename)}"

    except Exception as e:
        return f"[ERROR] Webcam record failed: {e}"
    
    finally:
        if out: out.release()

def send_image_data(conn, img_bytes):
    if img_bytes is None:
        conn.sendall(struct.pack(">L", 0))
        return
    size = len(img_bytes)
    conn.sendall(struct.pack(">L", size))
    conn.sendall(img_bytes)

def shutdown_machine():
    subprocess.Popen(["sudo", "shutdown", "-h", "now"])
    return "[OK] Shutdown sent"

def restart_machine():
    subprocess.Popen(["sudo", "shutdown", "-r", "now"])
    return "[OK] Restart sent"

def get_process_list():
    try:
        cmd = "ps -Aceo pid,pcpu,comm -r | head -n 50"
        output = subprocess.check_output(cmd, shell=True, text=True)
        lines = output.strip().split('\n')
        cleaned = ["PID COMMAND %CPU"]
        for line in lines[1:]:
            parts = line.split(None, 2)
            if len(parts) < 3: continue
            pid, cpu, raw = parts[0], parts[1], parts[2]
            name = raw.split('(')[0].strip() if '(' in raw else raw.strip()
            cleaned.append(f"{pid} {name} {cpu}")
        return "\n".join(cleaned)
    except Exception as e: return f"[ERROR] {e}"

def handle_client(conn, addr):
    try:
        data = conn.recv(4096).decode().strip()
        if not data: return
        parts = data.split()
        command = parts[0].lower()

        if command == "screen_stream":
            img_data = capture_screen_bytes()
            send_image_data(conn, img_data)
            return

        elif command == "webcam_stream":
            img_data = capture_webcam_bytes()
            send_image_data(conn, img_data)
            return

        result = ""
        if command == "list_apps":
            app_status = {k: {"name": v, "running": is_app_running(v)} for k, v in APPS.items()}
            result = json.dumps(app_status)
        elif command == "screenshot": result = take_screenshot()
        elif command in ("start", "stop"):
             if len(parts) < 2: result = "[ERROR] no app"
             else:
                key = " ".join(parts[1:]).lower()
                name = APPS.get(key, " ".join(parts[1:]))
                result = start_app(name) if command == "start" else stop_app(name)
        elif command == "webcam_record":
             if len(parts) < 2: result = "[ERROR] args"
             else: result = record_webcam(int(parts[1]))
        elif command == "keylog_web":
             with open("web_keylog.txt", "a") as f: f.write((parts[1] if len(parts)>1 else "")+'\n')
             conn.sendall(b"OK"); return
        elif command == "keylog_data":
             try: 
                 with open("web_keylog.txt") as f: result=f.read()
             except: result=""
             conn.sendall(result.encode()); return
        elif command == "shutdown": result = shutdown_machine()
        elif command == "restart": result = restart_machine()
        elif command == "list_processes": result = get_process_list()
        else: result = "[ERROR] Unknown"

        conn.sendall(result.encode())

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        print(f"Server listening on {HOST}:{PORT}")
        while True:
            conn, addr = s.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    start_server()