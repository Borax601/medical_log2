from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64
import csv
from datetime import datetime

# --- 【重要】CSVの列名をここで定義します ---
# あなたのCSVファイルに合わせて英語に変更しました
DATE_COL = 'date'
HOSPITAL_COL = 'hospital'
AMOUNT_COL = 'amount'
CATEGORY_COL = 'description' # description に変更

# 日本語フォント設定
try:
    import matplotlib.font_manager as fm
    jp_fonts = ['IPAexGothic', 'Noto Sans CJK JP', 'Hiragino Sans']
    avail_fonts = set(f.name for f in fm.fontManager.ttflist)
    font_found = False
    for font in jp_fonts:
        if font in avail_fonts:
            plt.rcParams['font.family'] = font
            font_found = True
            break
    if not font_found:
        print("日本語フォントが見つかりませんでした。グラフの文字化けが発生する可能性があります。")
except ImportError:
    print("matplotlibがインストールされていないか、フォント関連のモジュールに問題があります。")

app = Flask(__name__)
CSV_FILE = 'records.csv'

@app.route('/', methods=['GET', 'POST'])
def index():
    # --- データ追加処理 (POSTリクエストの場合) ---
    if request.method == 'POST':
        date = request.form.get('date')
        hospital = request.form.get('hospital')
        amount = request.form.get('amount')
        category = request.form.get('category', 'N/A')

        if date and hospital and amount:
            with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # ファイルが空でヘッダーがない場合にヘッダーを書き込む
                # This assumes the file is created with headers. If not, this logic is needed.
                # if f.tell() == 0:
                #     writer.writerow([DATE_COL, HOSPITAL_COL, AMOUNT_COL, CATEGORY_COL])
                writer.writerow([date, hospital, amount, category])
        return redirect(url_for('index'))

    # --- データ表示処理 (GETリクエストの場合) ---
    try:
        df = pd.read_csv(CSV_FILE)
        required_columns = [DATE_COL, HOSPITAL_COL, AMOUNT_COL, CATEGORY_COL]
        if not all(col in df.columns for col in required_columns):
            missing_cols = [col for col in required_columns if col not in df.columns]
            return f"エラー: CSVファイルに必要なカラムがありません。不足しているカラム: {', '.join(missing_cols)}"
        
        df[AMOUNT_COL] = pd.to_numeric(df[AMOUNT_COL], errors='coerce').fillna(0)
    except FileNotFoundError:
        return f"エラー: {CSV_FILE}ファイルが見つかりません。同じフォルダにありますか？"
    except Exception as e:
        return f"エラーが発生しました: {e}"

    hospitals = sorted(df[HOSPITAL_COL].dropna().unique())
    months = sorted(df[DATE_COL].str[:7].dropna().unique())
    
    selected_hospital = request.args.get('hospital', '全て')
    selected_month = request.args.get('month', '全て')

    filtered_df = df.copy()
    if selected_hospital != '全て':
        filtered_df = filtered_df[filtered_df[HOSPITAL_COL] == selected_hospital]
    if selected_month != '全て':
        filtered_df = filtered_df[filtered_df[DATE_COL].str.startswith(selected_month)]

    records = filtered_df.to_dict(orient='records')
    columns = df.columns.tolist()

    # --- グラフ生成 ---
    bar_img = None
    if not filtered_df.empty:
        bar_data = filtered_df.groupby(HOSPITAL_COL)[AMOUNT_COL].sum()
        if not bar_data.empty:
            plt.figure(figsize=(8, 5))
            bar_data.plot(kind='bar', color='skyblue')
            plt.title('医療機関ごとの合計金額')
            plt.ylabel('金額（円）')
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()
            buf = io.BytesIO()
            plt.savefig(buf, format='png')
            plt.close()
            buf.seek(0)
            bar_img = base64.b64encode(buf.getvalue()).decode('utf-8')

    pie_img = None
    if not filtered_df.empty:
        pie_data = filtered_df.groupby(CATEGORY_COL)[AMOUNT_COL].sum()
        if not pie_data.empty and pie_data.sum() > 0:
            plt.figure(figsize=(5, 5))
            pie_data.plot(kind='pie', autopct='%1.1f%%', startangle=90)
            plt.title('区分ごとの金額割合')
            plt.ylabel('')
            plt.tight_layout()
            # ↓↓↓↓ ここが修正箇所です！ io.io.BytesIO() -> io.BytesIO() ↓↓↓↓
            buf = io.BytesIO()
            plt.savefig(buf, format='png')
            plt.close()
            buf.seek(0)
            pie_img = base64.b64encode(buf.getvalue()).decode('utf-8')

    return render_template(
        'index.html',
        records=records,
        columns=columns,
        hospitals=['全て'] + hospitals,
        months=['全て'] + months,
        selected_hospital=selected_hospital,
        selected_month=selected_month,
        bar_img=bar_img,
        pie_img=pie_img
    )

@app.route('/delete', methods=['POST'])
def delete():
    date = request.form.get('date')
    hospital = request.form.get('hospital')
    amount = request.form.get('amount')
    description = request.form.get('description')

    df = pd.read_csv(CSV_FILE, dtype=str)
    def match_row(row):
        # descriptionが空欄やnanでも一致とみなす
        desc = row[CATEGORY_COL]
        return (
            row[DATE_COL] == date and
            row[HOSPITAL_COL] == hospital and
            row[AMOUNT_COL] == amount and
            (desc == description or pd.isna(desc) or desc == '' or desc == 'nan' or description == '' or description == 'nan')
        )
    df = df[~df.apply(match_row, axis=1)]
    df.to_csv(CSV_FILE, index=False, encoding='utf-8')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
