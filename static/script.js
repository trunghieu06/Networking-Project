// --- TRANSLATION DATA ---
const translations = {
    vi: {
        home: "Trang chủ", apps: "Ứng dụng", tasks: "Tác vụ", files: "Tệp tin", term: "Lệnh", view: "Xem", cam: "Cam", keys: "Phím", pwr: "Nguồn",
        mode: "Chế độ", set: "Cài đặt", lang_btn: "Ngôn ngữ", connected: "Đã kết nối",
        info_title: "Thông Tin Đồ Án", info_subj: "Môn học:", info_subj_val: "Mạng máy tính - Sinh viên Năm 2",
        info_fac: "Khoa:", info_fac_val: "Công nghệ Thông tin - ĐH KHTN, ĐHQG-HCM",
        info_desc: "Mô tả:", info_desc_val: "Hệ thống điều khiển từ xa qua TCP. Quản lý Process, App, File, Terminal, Keylogger, Webcam, Remote Desktop.",
        info_mem: "Thành viên thực hiện:",
        res_title: "Tài nguyên thời gian thực", feat_title: "Tất cả chức năng",
        sc_screen: "Màn hình", sc_webcam: "Webcam", sc_keylog: "Nhật ký", sc_apps: "Ứng dụng", sc_tasks: "Tác vụ", sc_files: "Tệp tin", sc_term: "Lệnh", sc_snap: "Chụp ảnh", sc_power: "Nguồn",
        th_name: "Tên", th_size: "Kích thước", th_action: "Hành động",
        proc_title: "Tiến trình hàng đầu", app_title: "Ứng dụng đã cài",
        screen_title: "Theo dõi màn hình",
        btn_snap: "Chụp & Lưu", btn_record: "Ghi hình", btn_refresh: "Làm mới", btn_start: "Bắt đầu", btn_stop: "Dừng", btn_clear: "Xóa", btn_dl: "Tải về",
        key_title: "Nhật ký phím",
        pwr_title: "Điều khiển Nguồn", pwr_desc: "Cẩn thận! Hành động này sẽ tắt hoặc khởi động lại máy thật.",
        set_title: "Cài đặt kết nối", btn_connect: "Kết nối", btn_close: "Đóng"
    },
    en: {
        home: "Home", apps: "Apps", tasks: "Tasks", files: "Files", term: "Term", view: "View", cam: "Cam", keys: "Keys", pwr: "Power",
        mode: "Mode", set: "Setup", lang_btn: "Language", connected: "Connected",
        info_title: "Project Info", info_subj: "Subject:", info_subj_val: "Computer Networks - 2nd Year Student",
        info_fac: "Faculty:", info_fac_val: "Information Technology - VNUHCM-US",
        info_desc: "Desc:", info_desc_val: "Remote Control System via TCP. Features: Process, App, File, Terminal, Keylogger, Webcam, Remote Desktop.",
        info_mem: "Team Members:",
        res_title: "Real-time Resources", feat_title: "All Features",
        sc_screen: "Screen", sc_webcam: "Webcam", sc_keylog: "Keylog", sc_apps: "Apps", sc_tasks: "Tasks", sc_files: "Files", sc_term: "Term", sc_snap: "Snap", sc_power: "Power",
        th_name: "Name", th_size: "Size", th_action: "Action",
        proc_title: "Top Processes", app_title: "Installed Apps",
        screen_title: "Screen Monitor",
        btn_snap: "Capture", btn_record: "Record", btn_refresh: "Refresh", btn_start: "Start", btn_stop: "Stop", btn_clear: "Clear", btn_dl: "Download",
        key_title: "Live Keylogs",
        pwr_title: "Power Control", pwr_desc: "Warning! These actions affect the physical machine.",
        set_title: "Connection Settings", btn_connect: "Connect", btn_close: "Close"
    }
};

let currentLang = localStorage.getItem('lang') || 'vi';

function toggleLang() {
    currentLang = currentLang === 'vi' ? 'en' : 'vi';
    localStorage.setItem('lang', currentLang);
    updateText();
}

function updateText() {
    const data = translations[currentLang];
    document.querySelectorAll('[data-lang]').forEach(el => {
        const key = el.getAttribute('data-lang');
        if (data[key]) el.textContent = data[key];
    });
}

updateText();

// --- TABS LOGIC ---
function showTab(id) {
    document.querySelectorAll('.tab-content').forEach(e => e.classList.add('hidden'));
    document.querySelectorAll('.nav-item').forEach(e => e.classList.remove('active'));
    const target = document.getElementById('tab-' + id);
    if(target) target.classList.remove('hidden');
    const navLink = document.querySelector(`.sidebar a[href="#${id}"]`) || document.getElementById('nav-home');
    if(navLink) navLink.classList.add('active');
    
    document.getElementById('page-title').textContent = id.toUpperCase();
    
    // --- CẬP NHẬT MỚI: Tự động xóa nội dung Keylog khi mở tab ---
    if(id === 'keylogger') {
        // Gọi hàm này để vừa xóa UI vừa báo Server xóa file log cũ
        // clearLogs(); // Đã xóa phần auto-clear keylogger ở đây theo yêu cầu người dùng
    }
    
    if(id === 'files') loadFiles('.');
    if(id === 'processes') loadProcesses();
    if(id === 'apps') loadApps();
}

// --- HÀM DOWNLOAD KEYLOG ---
function downloadKeylog() {
    // Lấy nội dung text
    const content = document.getElementById('keylog-content').textContent;
    
    // Gửi về server Python (client.py) để lưu
    fetch('/api/save_keylog_local', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ content: content })
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === 'ok') {
            showToast("Đã lưu file: " + data.message, "success");
        } else {
            showToast("Lỗi lưu file: " + data.message, "error");
        }
    })
    .catch(err => {
        
        showToast("Lỗi kết nối!", "error");
        console.error(err);
    });
}

// --- HÀM XÓA KEYLOG (UI + SERVER) ---
function clearLogs() {
    // Xóa ngay lập tức trên giao diện, không cần đợi server
    document.getElementById('keylog-content').textContent = 'Waiting for input...';
    // Gửi lệnh xóa ngầm cho server
    sendControl('keylog_clear');
    // Bỏ focus nút để tránh nhấn Enter nhầm
    document.activeElement.blur();
}

// --- CHART JS ---
const ctx = document.getElementById('sysChart').getContext('2d');
const sysChart = new Chart(ctx, {
    type: 'line',
    data: { labels: [], datasets: [{ label: 'CPU %', data: [], borderColor: '#0a84ff', tension: 0.4 }, { label: 'RAM %', data: [], borderColor: '#30d158', tension: 0.4 }] },
    options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true, max: 100 } } }
});

setInterval(() => {
    if(!document.getElementById('tab-home').classList.contains('hidden')) {
        fetch('/api/stats').then(r=>r.json()).then(d => {
            const now = new Date().toLocaleTimeString();
            if(sysChart.data.labels.length > 10) { sysChart.data.labels.shift(); sysChart.data.datasets[0].data.shift(); sysChart.data.datasets[1].data.shift(); }
            sysChart.data.labels.push(now);
            sysChart.data.datasets[0].data.push(d.cpu);
            sysChart.data.datasets[1].data.push(d.ram);
            sysChart.update();
        });
    }
}, 2000);

// --- WEBCAM & KEYLOGGER ---
function recordWebcam() {
    const sec = document.getElementById('cam-seconds').value;
    const indicator = document.getElementById('rec-indicator');
    indicator.style.display = 'flex';
    sendControl('webcam_record', null, { seconds: sec });
    setTimeout(() => { indicator.style.display = 'none'; }, sec * 1000 + 1000);
}

function toggleKeylog(start) {
    const status = document.getElementById('kl-status');
    if (start) {
        sendControl('keylog_start');
        status.textContent = "RECORDING..."; status.style.color = "#ff3b30";
    } else {
        sendControl('keylog_stop');
        status.textContent = "PAUSED"; status.style.color = "#f39c12";
    }
}

setInterval(() => {
    if(!document.getElementById('tab-keylogger').classList.contains('hidden')) {
        fetch("/keylogger_data").then(r=>r.json()).then(d => {
            const el = document.getElementById('keylog-content');
            if(d.keys && d.keys !== el.textContent) {
                el.textContent = d.keys;
                el.scrollTop = el.scrollHeight;
            }
        });
    }
}, 1000);

// --- FILE EXPLORER ---
let currentPathSeparator = "/";

function loadFiles(path) {
    document.getElementById('file-list').innerHTML = '<tr><td colspan="3"><div class="skeleton"></div><div class="skeleton"></div></td></tr>';
    fetch('/api/files/list', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({path}) })
    .then(r=>r.json()).then(d => {
        if(d.error) { alert(d.error); return; }
        const pathInput = document.getElementById('path-input');
        pathInput.value = d.current_path;
        if (d.current_path.includes("\\")) currentPathSeparator = "\\"; else currentPathSeparator = "/";
        let html = '';
        d.items.forEach(i => {
            const icon = i.type === 'folder' ? '<i class="fa-solid fa-folder file-icon" style="color:#fbc02d"></i>' : '<i class="fa-solid fa-file file-icon"></i>';
            const safePath = i.path.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
            const action = i.type === 'folder' 
                ? `<button onclick="loadFiles('${safePath}')" class="btn" style="padding:4px 8px;">Open</button>`
                : `<a href="/api/files/download?path=${encodeURIComponent(i.path)}" class="btn" style="padding:4px 8px; background:#30d158;"><i class="fa-solid fa-download"></i></a>`;
            let sizeStr = '-';
            if (i.type === 'file') {
                if (i.size < 1024) sizeStr = i.size + ' B';
                else if (i.size < 1024*1024) sizeStr = (i.size/1024).toFixed(1) + ' KB';
                else sizeStr = (i.size/(1024*1024)).toFixed(1) + ' MB';
            }
            html += `<tr class="file-item"><td>${icon} ${i.name}</td><td style="color:#888; font-size:0.9rem">${sizeStr}</td><td>${action}</td></tr>`;
        });
        document.getElementById('file-list').innerHTML = html;
    });
}

function goUp() {
    const current = document.getElementById('path-input').value;
    const lastIndex = current.lastIndexOf(currentPathSeparator);
    if (lastIndex > 0) {
        let parent = current.substring(0, lastIndex);
        if (parent.length === 2 && parent.includes(":")) parent += "\\"; 
        if (parent === "") parent = "/"; 
        loadFiles(parent);
    } else { loadFiles(currentPathSeparator === "\\" ? "C:\\" : "/"); }
}

document.getElementById('path-input').addEventListener("keypress", function(event) {
    if (event.key === "Enter") { loadFiles(this.value); }
});

// --- TERMINAL ---
const termIn = document.getElementById('term-in');
termIn.addEventListener('keypress', function (e) {
    if (e.key === 'Enter') {
        const cmd = termIn.value;
        termIn.value = '';
        document.getElementById('term-out').innerHTML += `<div><span style="color:#0a84ff">user@server:~$</span> ${cmd}</div>`;
        fetch('/api/terminal', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({cmd}) })
        .then(r=>r.json()).then(d => {
            document.getElementById('term-out').innerHTML += `<div style="color:#ccc">${d.output}</div><br>`;
            document.getElementById('term-out').scrollTop = document.getElementById('term-out').scrollHeight;
        });
    }
});

// --- PROCESSES & APPS & COMMON ---
function loadProcesses() {
    const list = document.getElementById('proc-list');
    list.innerHTML = Array(5).fill('<tr><td colspan="5"><div class="skeleton"></div></td></tr>').join('');
    fetch('/api/processes').then(r=>r.json()).then(data => {
        let html = '';
        data.forEach(p => {
            html += `<tr><td style="color:var(--accent)">${p.pid}</td><td>${p.name}</td><td style="color:#ff3b30; font-weight:bold;">${p.cpu_percent}%</td><td>${p.memory_percent.toFixed(1)}%</td><td><button onclick="killProc(${p.pid})" class="btn btn-danger" style="padding:2px 8px; font-size:0.8rem;">Kill</button></td></tr>`;
        });
        list.innerHTML = html;
    });
}
function killProc(pid) {
    if(confirm('Kill ' + pid + '?')) {
        fetch('/control', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({action: 'kill_process', pid: pid})})
        .then(r => r.json()).then(d => { if(d.status === 'ok') { showToast("Success"); loadProcesses(); } else alert(d.message); });
    }
}
function loadApps() {
        document.getElementById('app-list').innerHTML = '<div class="skeleton"></div><div class="skeleton"></div>';
        fetch('/api/apps').then(r=>r.json()).then(apps => {
            let html = '';
            for(const [k,v] of Object.entries(apps)) {
                html += `<div style="display:flex; justify-content:space-between; padding:10px; border-bottom:1px solid #333;"><span>${v.name}</span><div><button onclick="ctrlApp('start','${k}')" class="btn" ${v.running?'disabled':''} style="background:#30d158; opacity:${v.running?0.3:1}">Start</button><button onclick="ctrlApp('stop','${k}')" class="btn btn-danger" ${!v.running?'disabled':''} style="opacity:${!v.running?0.3:1}">Stop</button></div></div>`;
            }
            document.getElementById('app-list').innerHTML = html;
        });
}
function ctrlApp(act, app) { sendControl(act, app); setTimeout(loadApps, 1500); }
function sendControl(action, appKey=null, extraData={}) {
    const payload = { action: action }; if (appKey) payload.app = appKey; Object.assign(payload, extraData);
    fetch('/control', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) })
    .then(r => r.json()).then(data => { if (data.status === 'ok') showToast(data.message, 'success'); else showToast(data.message, 'error'); })
    .catch(() => showToast("Failed", 'error'));
}
function showToast(msg, type='success') {
    const t = document.getElementById('toast'); t.textContent = msg;
    t.style.transform = "translate(-50%, 30px)"; setTimeout(() => t.style.transform = "translate(-50%, -100px)", 3000);
}
function openSettings() { document.getElementById('settingsModal').style.display='flex'; fetch('/api/config_info').then(r=>r.json()).then(d=>{ document.getElementById('in-ip').value=d.ip; document.getElementById('in-port').value=d.port; }); }
function saveSettings() {
    const ip = document.getElementById('in-ip').value; const port = document.getElementById('in-port').value;
    fetch('/api/configure', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ip, port})}).then(()=>{ document.getElementById('settingsModal').style.display='none'; location.reload(); });
}
function toggleTheme() {
    if(document.body.getAttribute('data-theme')==='light') { document.body.removeAttribute('data-theme'); localStorage.setItem('theme','dark'); }
    else { document.body.setAttribute('data-theme','light'); localStorage.setItem('theme','light'); }
}
if(localStorage.getItem('theme')==='light') document.body.setAttribute('data-theme','light');

showTab('home');