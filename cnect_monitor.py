import tkinter as tk
from tkinter import messagebox
import subprocess
import os


class SchedulerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Scheduler Control")
        
        self.status_label = tk.Label(root, text="Scheduler Status: Stopped", fg="red")
        self.status_label.pack(pady=10)
        
        self.start_button = tk.Button(root, text="Start Scheduler", command=self.start_scheduler)
        self.start_button.pack(pady=5)
        
        self.stop_button = tk.Button(root, text="Stop Scheduler", command=self.stop_scheduler)
        self.stop_button.pack(pady=5)
        
        self.scheduler_process = None

    def start_scheduler(self):
        if self.scheduler_process is None:
            self.scheduler_process = subprocess.Popen(["python", "scheduler.py"])
            self.status_label.config(text="Scheduler Status: Running", fg="green")
        else:
            messagebox.showinfo("Info", "Scheduler is already running")

    def stop_scheduler(self):
        if self.scheduler_process is not None:
            self.scheduler_process.terminate()
            self.scheduler_process = None
            self.status_label.config(text="Scheduler Status: Stopped", fg="red")
        else:
            messagebox.showinfo("Info", "Scheduler is not running")

if __name__ == "__main__":
    root = tk.Tk()
    app = SchedulerApp(root)
    root.mainloop()