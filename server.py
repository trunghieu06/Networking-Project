import socket
import subprocess
import threading
import time
import os
from datetime import datetime
import cv2

HOST = "0.0.0.0"
PORT = 5001

APPS = {
    "calculator": "Calculator",
    "notes": "Notes",
    "textedit": "TextEdit",
    "safari": "Safari",
    "terminal": "Terminal",
    "finder": "Finder",
    "preview": "Preview",
    "messages": "Messages",
    "calendar": "Calendar",
    "contacts": "Contacts",
    "mail": "Mail"
}


def is_app_running(name):
    try:
        subprocess.check_output(["pgrep", "-x", name])
        return True
    except:
        return False


def start_app(app_name):
    if app_name not in APPS.values():
        return f"[ERROR] Unknown app: {app_name}"
    if is_app_running(app_name):
        return f"[INFO] {app_name} already running"
    subprocess.run(["open", "-a", app_name])
    time.sleep(0.3)
    if is_app_running(app_name):
        return f"[OK] Started {app_name}"
    return f"[ERROR] Failed to start {app_name}"


def stop_app(app_name):
    if not is_app_running(app_name):
        return f"[ERROR] {app_name} not running"
    subprocess.run(["osascript", "-e", f'quit app "{app_name}"'])
    time.sleep(0.3)
    if not is_app_running(app_name):
        return f"[OK] Stopped {app_name}"
    subprocess.run(["killall", app_name], check=False)
    time.sleep(0.2)
    if not is_app_running(app_name):
        return f"[OK] Forced stop {app_name}"
    return f"[ERROR] Could not stop {app_name}"


def take_screenshot():
    try:
        os.makedirs("screenshots", exist_ok=True)
        filename = f"screenshots/shot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        subprocess.run(["screencapture", filename])
        return f"[OK] Screenshot saved: {filename}"
    except Exception as e:
        return f"[ERROR] Screenshot failed: {e}"


def record_webcam(seconds):
    cap = None
    out = None
    try:
        # 1. Đảm bảo Photo Booth tắt để không chiếm cam
        subprocess.run(["killall", "Photo Booth"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # 2. Mở Camera (0 là default webcam)
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return "[ERROR] Could not open webcam (Check permissions)"

        # 3. Cấu hình file lưu
        os.makedirs("recordings", exist_ok=True) # Lưu vào thư mục recordings cho gọn
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"recordings/webcam_{timestamp}.mp4"
        
        # Lấy thông số camera
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = 20.0 # Set cứng hoặc dùng cap.get(cv2.CAP_PROP_FPS)

        # Cấu hình codec (mp4v chạy tốt trên macOS)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(filename, fourcc, fps, (width, height))

        # 4. Bắt đầu ghi
        start_time = time.time()
        while (time.time() - start_time) < seconds:
            ret, frame = cap.read()
            if ret:
                out.write(frame)
            else:
                break
            
            # (Tùy chọn) Thêm delay nhỏ để giảm tải CPU nếu cần, nhưng cv2.read() thường đã block theo FPS
            # time.sleep(0.01) 

        return f"[OK] Recording saved to {os.path.abspath(filename)}"

    except Exception as e:
        return f"[ERROR] Webcam record failed: {e}"
    
    finally:
        # 5. Giải phóng tài nguyên chắc chắn
        if cap and cap.isOpened():
            cap.release()
        if out:
            out.release()
        cv2.destroyAllWindows() # Đảm bảo đóng mọi cửa sổ ngầm nếu có

def shutdown_machine():
    subprocess.Popen(["sudo", "shutdown", "-h", "now"])
    return "[OK] Shutdown command sent"


def restart_machine():
    subprocess.Popen(["sudo", "shutdown", "-r", "now"])
    return "[OK] Restart command sent"


def handle_client(conn, addr):
    print(f"Client {addr} connected.")
    while True:
        try:
            data = conn.recv(4096).decode().strip()
            if not data:
                break
            print("Received:", data)
            parts = data.split()
            command = parts[0].lower()

            # CHỈ CÒN webcam_record
            if command == "webcam_record":
                if len(parts) < 2:
                    result = "[ERROR] webcam_record <seconds>"
                else:
                    try:
                        sec = int(parts[1])
                        if sec not in (1, 2, 5, 10, 20, 30):
                            result = "[ERROR] Allowed durations: 1/2/5/10/20/30"
                        else:
                            result = record_webcam(sec)
                    except:
                        result = "[ERROR] Invalid seconds"
                conn.sendall(result.encode())
                continue

            if command in ("start", "stop"):
                if len(parts) < 2:
                    conn.sendall(b"[ERROR] Missing app name")
                    continue
                app_key = " ".join(parts[1:])
                app_name = APPS.get(app_key.lower(), app_key)
                result = start_app(app_name) if command == "start" else stop_app(app_name)

            elif command == "screenshot":
                result = take_screenshot()

            elif command == "keylog_web":
                key = parts[1] if len(parts) > 1 else ""
                with open("web_keylog.txt", "a") as f:
                    f.write(key + '\n')
                conn.sendall(b"[OK] Logged key")
                continue

            elif command == "keylog_data":
                try:
                    with open("web_keylog.txt", "r") as f:
                        keys = f.read()
                except FileNotFoundError:
                    keys = ""
                conn.sendall(keys.encode())
                continue


            elif command == "shutdown":
                result = shutdown_machine()

            elif command == "restart":
                result = restart_machine()

            else:
                result = "[ERROR] Unknown command"

            conn.sendall(result.encode())

        except Exception as e:
            try:
                conn.sendall(f"[ERROR] {e}".encode())
            except:
                pass
            break

    conn.close()
    print(f"Client {addr} disconnected.")


def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print(f"Server listening on {HOST}:{PORT}")
        while True:
            conn, addr = s.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    start_server()
