import os
import requests
import google.generativeai as genai
import sys
from datetime import datetime

# 1. 讀取 GitHub Secrets
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def fetch_and_summarize():
    # 抓取新聞
    url = f"https://newsapi.org/v2/everything?q=AI&language=zh&sortBy=publishedAt&pageSize=8&apiKey={NEWS_API_KEY}"
    
    try:
        print("正在獲取新聞資料...")
        response = requests.get(url)
        articles = response.json().get("articles", [])
        
        if not articles:
            with open("daily_report.md", "w", encoding="utf-8") as f:
                f.write("# 🤖 AI 每日新聞洞察\n\n⚠️ 今日無相關新聞。")
            return

        news_content = ""
        for i, a in enumerate(articles):
            news_content += f"\n新聞 {i+1}：{a.get('title')}\n來源：{a.get('source',{}).get('name')}\n連結：{a.get('url')}\n摘要：{a.get('description')}\n"

        # 2. 設定 Gemini
        genai.configure(api_key=GEMINI_API_KEY)
        
        # --- 🚀 自動偵測模型邏輯 ---
        print("正在檢查可用模型清單...")
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        print(f"你的 API Key 可使用的模型包含: {available_models}")

        # 定義我們想嘗試的名稱清單（包含完整路徑與簡稱）
        target_names = [
            'gemini-1.5-flash', 
            'models/gemini-1.5-flash', 
            'gemini-1.5-pro',
            'models/gemini-1.5-pro',
            'gemini-pro',
            'models/gemini-pro'
        ]

        model_to_use = None
        # 先從我們想要的清單裡找
        for name in target_names:
            if any(name == m or name in m for m in available_models):
                model_to_use = name
                break
        
        # 如果都沒對上，就直接用可用清單的第一個
        if not model_to_use and available_models:
            model_to_use = available_models[0]

        if not model_to_use:
            raise Exception("找不到任何可用的 Gemini 模型。")

        print(f"✅ 決定使用模型: {model_to_use}")
        # ---------------------------

        model = genai.GenerativeModel(model_to_use)
        prompt = f"請將以下新聞整理成繁體中文摘要，並列出三個今日最值得關注的科技趨勢：\n{news_content}"
        
        # 執行生成
        ai_response = model.generate_content(prompt)
        
        # 3. 寫入檔案
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open("daily_report.md", "w", encoding="utf-8") as f:
            f.write("# 🤖 AI 每日新聞洞察\n\n")
            f.write(ai_response.text)
            f.write(f"\n\n--- \n**⚙️ 系統資訊**\n- 執行時間：{current_time}\n- 使用模型：`{model_to_use}`")
            
        print("✅ 報告已成功生成！")

    except Exception as e:
        error_msg = f"❌ 執行錯誤：{str(e)}"
        with open("daily_report.md", "w", encoding="utf-8") as f:
            f.write(f"# 🤖 執行異常報告\n\n{error_msg}")
        print(error_msg)

if __name__ == "__main__":
    fetch_and_summarize()
