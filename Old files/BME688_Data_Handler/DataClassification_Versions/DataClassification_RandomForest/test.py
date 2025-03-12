import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import os
from dataProcessor import DataProcessor, FEATURES
import pandas as pd

class SimpleProcessorGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("Simple Data Processor")
        self.file_path_var = tk.StringVar()
        self.log_text = None
        self.setup_ui()

    def setup_ui(self):
        frame = tk.Frame(self.master)
        frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        tk.Label(frame, text="Input CSV File:").grid(row=0, column=0, sticky="w")
        tk.Entry(frame, textvariable=self.file_path_var, width=60).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        tk.Button(frame, text="Browse", command=self.browse_file).grid(row=0, column=2, padx=5)

        tk.Button(frame, text="Process", command=self.process_file).grid(row=1, column=0, columnspan=3, pady=5)

        self.log_text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, width=70, height=15)
        self.log_text.grid(row=2, column=0, columnspan=3, pady=5, sticky="nsew")
        frame.rowconfigure(2, weight=1)

    def browse_file(self):
        path = filedialog.askopenfilename(
            title="Select CSV File",
            filetypes=[("CSV Files","*.csv"),("All Files","*.*")]
        )
        if path:
            self.file_path_var.set(path)

    def process_file(self):
        path = self.file_path_var.get().strip()
        if not path or not os.path.isfile(path):
            messagebox.showerror("Error", "Please select a valid CSV file.")
            return
        processor = DataProcessor()
        try:
            df = processor.read_csv(path)
        except Exception as e:
            messagebox.showerror("Error", f"Could not read file:\n{e}")
            return
        window_size = 5
        stride = 1
        selected_features = list(FEATURES.keys())
        try:
            data = processor.process_data(df, window_size, stride, selected_features)
            out_path = os.path.join(os.path.dirname(path), "processed_features.csv")
            processor.save_output(data, out_path)
            self.log_text.delete("1.0", tk.END)
            self.log_text.insert(tk.END, f"Processing complete.\nRows read: {len(df)}\nRows processed: {len(data)}\nOutput saved to:\n{out_path}\n")
        except Exception as e:
            messagebox.showerror("Error", f"Processing failed:\n{e}")

def main():
    root = tk.Tk()
    app = SimpleProcessorGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
