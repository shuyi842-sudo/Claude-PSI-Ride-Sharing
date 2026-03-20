import tkinter as tk
from tkinter import messagebox
import requests
import threading

API_BASE = "http://localhost:5000"

class PassengerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("无人驾驶拼车系统 - 乘客端")
        self.root.geometry("400x500")
        self.root.configure(bg="#f0f8ff")
        self.passenger_id = ""
        self.setup_ui()

    def setup_ui(self):
        title = tk.Label(self.root, text="无人驾驶拼车系统", font=("微软雅黑", 20, "bold"), bg="#f0f8ff", fg="#2c3e50")
        title.pack(pady=20)
        subtitle = tk.Label(self.root, text="乘客端", font=("微软雅黑", 14), bg="#f0f8ff", fg="#7f8c8d")
        subtitle.pack(pady=5)
        frame = tk.Frame(self.root, bg="white", padx=20, pady=20)
        frame.pack(pady=20, padx=20, fill="x")
        tk.Label(frame, text="乘客ID:", font=("微软雅黑", 10), bg="white").grid(row=0, column=0, sticky="w", pady=5)
        self.id_entry = tk.Entry(frame, font=("微软雅黑", 10))
        self.id_entry.grid(row=0, column=1, sticky="ew", pady=5)
        tk.Label(frame, text="起点:", font=("微软雅黑", 10), bg="white").grid(row=1, column=0, sticky="w", pady=5)
        self.start_entry = tk.Entry(frame, font=("微软雅黑", 10))
        self.start_entry.grid(row=1, column=1, sticky="ew", pady=5)
        self.start_entry.insert(0, "科技园A区")
        tk.Label(frame, text="终点:", font=("微软雅黑", 10), bg="white").grid(row=2, column=0, sticky="w", pady=5)
        self.end_entry = tk.Entry(frame, font=("微软雅黑", 10))
        self.end_entry.grid(row=2, column=1, sticky="ew", pady=5)
        self.end_entry.insert(0, "市中心B区")
        frame.columnconfigure(1, weight=1)
        btn_frame = tk.Frame(self.root, bg="#f0f8ff")
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="请求匹配", font=("微软雅黑", 12), bg="#3498db", fg="white", padx=30, pady=10, command=self.request_match).pack(side="left", padx=5)
        tk.Button(btn_frame, text="重置", font=("微软雅黑", 12), bg="#95a5a6", fg="white", padx=20, pady=10, command=self.reset).pack(side="left", padx=5)
        self.result_frame = tk.Frame(self.root, bg="#f0f8ff")
        self.result_frame.pack(pady=20, padx=20, fill="both", expand=True)
        self.result_label = tk.Label(self.result_frame, text="等待请求匹配...", font=("微软雅黑", 11), bg="#ecf0f1", fg="#7f8c8d", padx=20, pady=20)
        self.result_label.pack(fill="both", expand=True)

    def request_match(self):
        self.passenger_id = self.id_entry.get()
        start = self.start_entry.get()
        end = self.end_entry.get()
        if not self.passenger_id:
            messagebox.showwarning("提示", "请输入乘客ID")
            return
        self.result_label.config(text="正在匹配中...", fg="#f39c12")
        self.root.update()
        thread = threading.Thread(target=self._do_match, args=(self.passenger_id, start, end))
        thread.start()

    def _do_match(self, p_id, start, end):
        try:
            requests.post(f"{API_BASE}/passenger/register", json={"passenger_id": p_id, "start": start, "end": end})
            response = requests.post(f"{API_BASE}/match", json={"passenger_id": p_id})
            result = response.json()
            self.root.after(0, lambda: self._show_match_result(result))
        except Exception as e:
            self.root.after(0, lambda: self.result_label.config(text=f"错误: {str(e)}", fg="#e74c3c"))

    def _show_match_result(self, result):
        if result.get("success"):
            vehicle = result["vehicle"]
            code = result["match_code"]
            text = f"匹配成功！

车辆ID: {vehicle['id']}
车辆路线: {vehicle['route']}
剩余座位: {vehicle['seats']}

验证码: {code}

凭此验证码上车"
            self.result_label.config(text=text, fg="#27ae60", font=("微软雅黑", 10))
        else:
            self.result_label.config(text=f"{result['message']}", fg="#e74c3c", font=("微软雅黑", 12))

    def reset(self):
        self.result_label.config(text="等待请求匹配...", fg="#7f8c8d", font=("微软雅黑", 11))

if __name__ == "__main__":
    root = tk.Tk()
    app = PassengerApp(root)
    root.mainloop()
