import tkinter as tk
from tkinter import messagebox, ttk
import requests
import threading

API_BASE = "http://localhost:5000"

class VehicleApp:
    def __init__(self, root):
        self.root = root
        self.root.title("无人驾驶拼车系统 - 车辆端")
        self.root.geometry("500x550")
        self.root.configure(bg="#f8f9fa")
        self.vehicle_id = ""
        self.setup_ui()

    def setup_ui(self):
        title = tk.Label(self.root, text="无人驾驶拼车系统", font=("微软雅黑", 20, "bold"), bg="#f8f9fa", fg="#2c3e50")
        title.pack(pady=15)
        subtitle = tk.Label(self.root, text="车辆端", font=("微软雅黑", 14), bg="#f8f9fa", fg="#7f8c8d")
        subtitle.pack(pady=5)
        frame = tk.Frame(self.root, bg="white", padx=20, pady=20, relief="ridge", bd=2)
        frame.pack(pady=15, padx=20, fill="x")
        tk.Label(frame, text="车辆ID:", font=("微软雅黑", 10), bg="white").grid(row=0, column=0, sticky="w", pady=5)
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
        tk.Label(frame, text="座位数:", font=("微软雅黑", 10), bg="white").grid(row=3, column=0, sticky="w", pady=5)
        self.seats_spin = tk.Spinbox(frame, from_=1, to=8, font=("微软雅黑", 10))
        self.seats_spin.grid(row=3, column=1, sticky="ew", pady=5)
        self.seats_spin.delete(0, "end")
        self.seats_spin.insert(0, "4")
        frame.columnconfigure(1, weight=1)
        btn_frame = tk.Frame(self.root, bg="#f8f9fa")
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="注册车辆", font=("微软雅黑", 12), bg="#27ae60", fg="white", padx=25, pady=10, command=self.register_vehicle).pack(side="left", padx=5)
        tk.Button(btn_frame, text="查看乘客", font=("微软雅黑", 12), bg="#3498db", fg="white", padx=25, pady=10, command=self.check_passengers).pack(side="left", padx=5)
        list_frame = tk.Frame(self.root, bg="#f8f9fa")
        list_frame.pack(pady=15, padx=20, fill="both", expand=True)
        tk.Label(list_frame, text="已匹配的乘客：", font=("微软雅黑", 12, "bold"), bg="#f8f9fa", anchor="w").pack(fill="x")
        columns = ("ID", "起点", "终点")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=6)
        self.tree.heading("ID", text="乘客ID")
        self.tree.heading("起点", text="起点")
        self.tree.heading("终点", text="终点")
        self.tree.column("ID", width=100)
        self.tree.column("起点", width=120)
        self.tree.column("终点", width=120)
        self.tree.pack(fill="both", expand=True)
        self.status_label = tk.Label(self.root, text="系统就绪", font=("微软雅黑", 9), bg="#ecf0f1", fg="#7f8c8d", pady=5)
        self.status_label.pack(side="bottom", fill="x")

    def register_vehicle(self):
        self.vehicle_id = self.id_entry.get()
        start = self.start_entry.get()
        end = self.end_entry.get()
        seats = int(self.seats_spin.get())
        if not self.vehicle_id:
            messagebox.showwarning("提示", "请输入车辆ID")
            return
        try:
            response = requests.post(f"{API_BASE}/vehicle/register", json={"vehicle_id": self.vehicle_id, "start": start, "end": end, "seats": seats})
            if response.status_code == 200:
                messagebox.showinfo("成功", "车辆注册成功！")
                self.status_label.config(text=f"车辆 {self.vehicle_id} 已就绪", fg="#27ae60")
            else:
                messagebox.showerror("错误", response.json().get("error", "注册失败"))
        except Exception as e:
            messagebox.showerror("错误", f"连接失败: {str(e)}")

    def check_passengers(self):
        if not self.vehicle_id:
            messagebox.showwarning("提示", "请先注册车辆")
            return
        self.status_label.config(text="正在查询...", fg="#f39c12")
        self.root.update()
        thread = threading.Thread(target=self._do_check)
        thread.start()

    def _do_check(self):
        try:
            response = requests.get(f"{API_BASE}/vehicle/check", params={"vehicle_id": self.vehicle_id})
            result = response.json()
            self.root.after(0, lambda: self._show_passengers(result))
        except Exception as e:
            self.root.after(0, lambda: self.status_label.config(text=f"错误: {str(e)}", fg="#e74c3c"))

    def _show_passengers(self, result):
        for item in self.tree.get_children():
            self.tree.delete(item)
        passengers = result.get("matched_passengers", [])
        for p in passengers:
            self.tree.insert("", "end", values=(p["id"], p["start"], p["end"]))
        count = len(passengers)
        self.status_label.config(text=f"查询完成，匹配到 {count} 位乘客" if count > 0 else "暂无匹配乘客", fg="#27ae60" if count > 0 else "#95a5a6")

if __name__ == "__main__":
    root = tk.Tk()
    app = VehicleApp(root)
    root.mainloop()
