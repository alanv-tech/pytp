import socket
import threading
import time
import tkinter as tk
from datetime import datetime, timedelta, timezone
import struct
import random 
import tkinter.messagebox as messagebox

TIME_ZONES = {
    "UTC": 0, "EST": -5, "EDT": -4, "PST": -8, "PDT": -7,
    "GMT": 0, "CET": 1, "JST": 9, "AEST": 10
}

class NTPServer:
    def __init__(self, host='localhost', port=8080, log_callback=None):
        self.host = host
        self.port = port
        self.log_callback = log_callback
        self.server_socket = None
        self.is_running = False
        self.is_suspended = False
        self.start_time = None
        self.suspended_at = None
        self.total_suspended_time = 0
        self.thread = None

    def log(self, message):
        if self.log_callback:
            self.log_callback(message)

    def start(self):
        if not self.is_running:
            try:
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.server_socket.bind((self.host, self.port))
                self.is_running = True
                self.is_suspended = False
                self.start_time = time.time()
                self.total_suspended_time = 0
                self.thread = threading.Thread(target=self.run, daemon=True)
                self.thread.start()
                self.log("Server online on port 8080.")
            except Exception as e:
                self.log(f"Error: {e}")

    def toggle_suspend(self):
        if self.is_running:
            self.is_suspended = not self.is_suspended
            if self.is_suspended:
                self.suspended_at = time.time()
                self.log("PAUSED: Ignoring incoming requests.")
            else:
                self.total_suspended_time += (time.time() - self.suspended_at)
                self.log("RESUMED: Processing requests.")

    def run(self):
        while self.is_running:
            try:
                self.server_socket.settimeout(1.0)
                data, addr = self.server_socket.recvfrom(48)
                if self.is_suspended:
                    self.log(f"[DENY] Req from {addr[0]}:{addr[1]}")
                    continue
                if data:
                    current_time = time.time()
                    ntp_time = current_time + 2208988800
                    seconds = int(ntp_time)
                    fraction = int((ntp_time - seconds) * (2**32))
                    response = struct.pack('!12I', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, seconds, fraction)
                    self.server_socket.sendto(response, addr)
                    self.log(f"Sent to {addr[0]}:{addr[1]}")
            except socket.timeout:
                continue
            except socket.error:
                break

    def stop(self):
        if self.is_running:
            self.is_running = False
            if self.server_socket:
                self.server_socket.close()
            self.log("Server stopped.")

    def get_uptime(self):
        if self.start_time and self.is_running:
            if self.is_suspended:
                return int(self.suspended_at - self.start_time - self.total_suspended_time)
            return int(time.time() - self.start_time - self.total_suspended_time)
        return 0

class NTPServerGUI:
    def __init__(self, master, quit_callback):
        self.master = master
        self.quit_callback = quit_callback
        self.master.title("NTP Control Panel")
        self.master.geometry("500x650")
        self.master.resizable(False, False)
        
        self.server = NTPServer(log_callback=self.add_log)
        self.is_running = False
        self.active_clients = []

        ctrl_frame = tk.Frame(master)
        ctrl_frame.pack(fill="x", pady=15, padx=15)
        ctrl_frame.columnconfigure((0, 1, 2), weight=1)

        self.start_button = tk.Button(ctrl_frame, text="Start Server", width=12, bg="#d4edda", command=self.start_server)
        self.start_button.grid(row=0, column=0, sticky="w")
        self.suspend_button = tk.Button(ctrl_frame, text="Suspend Server", width=12, bg="#fff3cd", command=self.suspend_server, state=tk.DISABLED)
        self.suspend_button.grid(row=0, column=1)
        self.stop_button = tk.Button(ctrl_frame, text="Stop Server", width=12, bg="#f8d7da", command=self.stop_server, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=2, sticky="e")

        self.uptime_label = tk.Label(master, text="Status: Offline\nUptime: 0 seconds", font=("Arial", 10, "bold"))
        self.uptime_label.pack(pady=5)

        tk.Label(master, text="Server Logs:", font=("Arial", 9, "bold")).pack(anchor="w", padx=15)
        self.log_text = tk.Text(master, height=15, width=55, state=tk.DISABLED, bg="#f8f8f8", font=("Consolas", 9))
        self.log_text.pack(padx=15, pady=5)

        footer_frame = tk.Frame(master)
        footer_frame.pack(fill="x", side="bottom", padx=15, pady=20)
        footer_frame.columnconfigure((0, 1, 2), weight=1, uniform="footer_cols")

        BTN_WIDTH = 20

        tk.Button(footer_frame, text="New Simulated Client", width=BTN_WIDTH, command=self.open_client).grid(row=0, column=0, sticky="n")
        tk.Button(footer_frame, text="Close Program", width=BTN_WIDTH, command=self.quit_callback).grid(row=0, column=1, sticky="n")
        self.sync_button = tk.Button(footer_frame, text="Synchronize", width=BTN_WIDTH, state=tk.DISABLED, command=self.run_sync)
        self.sync_button.grid(row=0, column=2, sticky="n")

        self.client_count_label = tk.Label(footer_frame, text="Clients Connected: 0", font=("Arial", 8), fg="gray", width=BTN_WIDTH, anchor="center")
        self.client_count_label.grid(row=1, column=0, sticky="n", pady=(5, 0))

        self.offset_label = tk.Label(footer_frame, text="Offset: N/A", font=("Arial", 8, "bold"), fg="gray", width=BTN_WIDTH, anchor="center")
        self.offset_label.grid(row=1, column=2, sticky="n", pady=(5, 0))

        self.update_ui_loop()

    def open_client(self):
        client_window = tk.Toplevel(self.master)
        client_instance = NTPClientGUI(client_window, self)
        self.active_clients.append(client_instance)
        self.check_sync_state()

    def remove_client(self, client_instance):
        if client_instance in self.active_clients:
            self.active_clients.remove(client_instance)
        self.check_sync_state()

    def check_sync_state(self):
        count = len(self.active_clients)
        self.client_count_label.config(text=f"Clients Connected: {count}")
        if count >= 2:
            self.sync_button.config(state=tk.NORMAL)
        else:
            self.sync_button.config(state=tk.DISABLED)
            self.offset_label.config(text="Offset: N/A", fg="gray")

    def calculate_drift(self):
        timestamps = [c.last_ts for c in self.active_clients if c.last_ts is not None]
        if len(timestamps) < 2: return
        diff_ms = (max(timestamps) - min(timestamps)) * 1000
        color = "red" if diff_ms > 50 else ("#D4AC0D" if diff_ms > 10 else "green")
        self.offset_label.config(text=f"Offset: {diff_ms:.2f} ms", fg=color)

    def run_sync(self):
        self.add_log("Synchronizing...")
        for client in list(self.active_clients):
            delay = random.randint(5, 100)
            self.master.after(delay, client.force_sync_cycle)
        self.master.after(1100, self.calculate_drift)

    def add_log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.master.after(0, lambda: self._write_log(f"[{timestamp}] {message}\n"))

    def _write_log(self, full_message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, full_message)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def start_server(self):
        self.server.start()
        self.is_running = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.suspend_button.config(state=tk.NORMAL, text="Suspend Server")

    def suspend_server(self):
        self.server.toggle_suspend()
        self.suspend_button.config(text="Resume Server" if self.server.is_suspended else "Suspend Server")

    def stop_server(self):
        self.server.stop()
        self.is_running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.suspend_button.config(state=tk.DISABLED)

    def update_ui_loop(self):
        if self.is_running:
            uptime = self.server.get_uptime()
            status = "SUSPENDED" if self.server.is_suspended else "RUNNING"
            self.uptime_label.config(text=f"Status: {status}\nUptime: {uptime} seconds")
            if len(self.active_clients) >= 2: self.calculate_drift()
        self.master.after(1000, self.update_ui_loop)

class NTPClient:
    def __init__(self, host='localhost', port=8080):
        self.host, self.port = host, port

    def fetch_raw_timestamp(self):
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client_socket.settimeout(0.5)
        try:
            client_socket.sendto(b'\x1b' + 47 * b'\0', (self.host, self.port))
            data, _ = client_socket.recvfrom(48)
            if data:
                unpacked = struct.unpack('!12I', data)
                return unpacked[10] + (unpacked[11] / 2**32) - 2208988800 
        except: return None
        finally: client_socket.close()

class NTPClientGUI:
    def __init__(self, master, server_gui):
        self.master, self.server_gui = master, server_gui
        self.master.title("Simulated Client")
        self.master.geometry("350x320")
        self.master.resizable(False, False)
        
        self.client = NTPClient()
        self.last_ts = None
        self.selected_tz = tk.StringVar(master, "UTC")
        self.after_id = None 

        tk.Label(master, text="Select Time Zone:").pack(pady=5)
        tk.OptionMenu(master, self.selected_tz, *TIME_ZONES.keys()).pack()
        self.auto_refresh_var = tk.BooleanVar(value=False)
        tk.Checkbutton(master, text="Auto Refresh (1s)", variable=self.auto_refresh_var, command=self.toggle_refresh).pack(pady=5)
        tk.Button(master, text="Fetch Time", width=15, command=self.fetch_time).pack(pady=5)
        
        self.time_frame = tk.Frame(master)
        self.time_frame.pack(pady=5)
        
        self.time_label_main = tk.Label(self.time_frame, text="Time Not Fetched", font=("Helvetica", 14, "bold"))
        self.time_label_main.pack(side="left")
        
        self.time_label_ms = tk.Label(self.time_frame, text="", font=("Helvetica", 9), fg="gray")
        self.time_label_ms.pack(side="left", pady=(5, 0))

        tk.Button(master, text="Close Client", width=15, command=self.on_close).pack(pady=60)
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        if self.after_id: self.master.after_cancel(self.after_id)
        self.server_gui.remove_client(self)
        self.master.destroy()

    def toggle_refresh(self):
        if self.after_id: self.master.after_cancel(self.after_id)
        if self.auto_refresh_var.get():
            self.auto_refresh_loop()

    def auto_refresh_loop(self):
        if self.auto_refresh_var.get():
            self.fetch_time()
            self.after_id = self.master.after(1000, self.auto_refresh_loop)

    def force_sync_cycle(self):
        if self.after_id: self.master.after_cancel(self.after_id)
        self.auto_refresh_var.set(True)
        self.auto_refresh_loop()

    def fetch_time(self):
        def network_task():
            ts = self.client.fetch_raw_timestamp()
            if ts:
                self.master.after(0, lambda: self._update_ui(ts))
            else:
                self.master.after(0, lambda: self.time_label_main.config(text="Time Not Available", fg="red"))

        threading.Thread(target=network_task, daemon=True).start()

    def _update_ui(self, ts):
        self.last_ts = ts
        offset = TIME_ZONES.get(self.selected_tz.get(), 0)
        dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(timezone(timedelta(hours=offset)))
        
        main_time = dt.strftime('%H:%M:%S')
        ms_part = f".{dt.strftime('%f')[:3]}"
        
        self.time_label_main.config(text=main_time, fg="black")
        self.time_label_ms.config(text=ms_part)

def main():
    root = tk.Tk()
    def on_closing():
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            server_gui.stop_server()
            root.destroy()
    server_gui = NTPServerGUI(root, on_closing)
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()