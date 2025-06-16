#!/usr/bin/env python3
"""
Medical expense viewer & analyzer
CLI:
  python medical_log.py --summary month      # 月別合計
  python medical_log.py --summary hospital   # 病院別合計
GUI:
  python medical_log.py                      # CSV を選択し、月/病院 × 棒/円グラフ
"""
import csv, sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
plt.rcParams['font.family'] = 'Hiragino Sans'   # macOS 標準
plt.rcParams['axes.unicode_minus'] = False      # －記号の化け防止
plt.rcParams['font.size'] = 10                  # 任意

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

CSV_PATH   = Path(__file__).with_name("records.csv")
FIELDS     = ["date", "hospital", "amount", "description"]

# ---------- CSV ----------
def init_csv():
    if not CSV_PATH.exists():
        with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, FIELDS).writeheader()

def load():
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        return [{**row, "amount": int(row["amount"])} for row in r]

# ---------- SUMMARY ----------
def summarise(by: str):
    data = load()
    bucket = defaultdict(int)
    for r in data:
        key = r["date"][:7] if by == "month" else r["hospital"]
        bucket[key] += r["amount"]
    for k, v in sorted(bucket.items(), key=lambda x: -x[1]):
        print(f"{k:15} {v:>10} 円")

# ---------- GUI ----------
class Viewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Medical Expense Viewer")
        f = ttk.Frame(root, padding=10); f.grid()

        ttk.Button(f, text="CSVファイルを選択", command=self.load_csv)\
            .grid(row=0, column=0, columnspan=4, pady=5)

        ttk.Label(f, text="集計軸:").grid(row=1, column=0, sticky=tk.W)
        self.group_by = tk.StringVar(value="hospital")
        ttk.Radiobutton(f, text="病院", variable=self.group_by, value="hospital")\
            .grid(row=1, column=1, sticky=tk.W)
        ttk.Radiobutton(f, text="月", variable=self.group_by, value="month")\
            .grid(row=1, column=2, sticky=tk.W)

        ttk.Label(f, text="グラフ種類:").grid(row=2, column=0, sticky=tk.W)
        self.graph_type = tk.StringVar(value="bar")
        ttk.Radiobutton(f, text="棒", variable=self.graph_type, value="bar")\
            .grid(row=2, column=1, sticky=tk.W)
        ttk.Radiobutton(f, text="円", variable=self.graph_type, value="pie")\
            .grid(row=2, column=2, sticky=tk.W)

        ttk.Button(f, text="グラフ更新", command=self.update_graph)\
            .grid(row=3, column=0, columnspan=4, pady=5)

        # 月選択コンボボックス（macOSバグ回避のため最初からreadonlyで生成し、不要時は非表示）
        self.month_label = ttk.Label(f, text="月選択:")
        self.month_combo = ttk.Combobox(f, state="readonly", width=10)
        self.month_combo.bind("<<ComboboxSelected>>", lambda e: self.update_graph())
        self.month_label.grid(row=4, column=0, sticky=tk.W)
        self.month_combo.grid(row=4, column=1, columnspan=2, sticky=tk.W)
        self.month_label.grid_remove()
        self.month_combo.grid_remove()

        self.figure = plt.Figure(figsize=(8, 6))
        self.canvas = FigureCanvasTkAgg(self.figure, master=f)
        self.canvas.get_tk_widget().grid(row=5, column=0, columnspan=4, pady=10)
        self.df = None

    # ----- event handlers -----
    def load_csv(self):
        p = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if not p: return
        try:
            self.df = pd.read_csv(p)
            messagebox.showinfo("OK", "CSV 読込完了")
            self.update_month_combo()
            # CSV読込後にも必ずon_group_by_changeを呼ぶ
            self.on_group_by_change()
            self.update_graph()
        except Exception as e:
            messagebox.showerror("ERROR", str(e))

    def update_month_combo(self):
        # 月リストを更新（常に全データから抽出）
        if self.df is not None and "date" in self.df:
            months = sorted(self.df["date"].astype(str).str[:7].unique())
            print("DEBUG: months =", months)  # デバッグ用
            self.month_combo['values'] = months
            if months:
                self.month_combo.current(0)
                if self.group_by.get() == "month":
                    self.month_label.grid()
                    self.month_combo.grid()
            else:
                self.month_combo.set('')
                self.month_label.grid_remove()
                self.month_combo.grid_remove()

    def on_group_by_change(self, *args):
        # 集計軸が月で月リストがあれば表示、それ以外は非表示
        if self.group_by.get() == "month" and self.month_combo['values']:
            self.month_label.grid()
            self.month_combo.grid()
        else:
            self.month_label.grid_remove()
            self.month_combo.grid_remove()
        self.update_graph()

    def update_graph(self):
        if self.df is None:
            messagebox.showwarning("警告", "CSV を先に読み込んでください"); return
        if self.group_by.get() == "month":
            # 月選択で絞り込み、その月の病院ごと
            selected_month = self.month_combo.get()
            if not selected_month:
                self.figure.clear(); self.canvas.draw(); return
            tmp = self.df[self.df["date"].astype(str).str[:7] == selected_month]
            if tmp.empty:
                self.figure.clear(); self.canvas.draw(); return
            series = tmp.groupby("hospital")["amount"].sum()
            title = f"{selected_month} の病院別医療費"
        else:
            # 病院別（全期間）
            series = self.df.groupby("hospital")["amount"].sum()
            title = "病院別医療費"

        self.figure.clear(); ax = self.figure.add_subplot(111)
        if self.graph_type.get() == "pie":
            ax.pie(series, labels=series.index, autopct="%1.1f%%")
        else:
            series.plot(kind="bar", ax=ax); ax.set_ylabel("金額（円）")
        ax.set_title(title); self.figure.tight_layout(); self.canvas.draw()

# ---------- ENTRY ----------
if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--summary":
        init_csv(); summarise(sys.argv[2])
    else:
        root = tk.Tk(); Viewer(root); root.mainloop()
