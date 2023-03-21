from flask import Flask, render_template
import pandas as pd

app = Flask(__name__)

@app.route('/')
def index():
    # 读取本地 CSV 文件
    df = pd.read_csv('log.csv')

    # 获取最后10行数据
    last_10 = df.tail(10)

    # 将数据传递给模板
    return render_template('index.html', data=last_10)

if __name__ == '__main__':
    app.run(debug=True)


