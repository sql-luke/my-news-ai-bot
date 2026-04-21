import os
import requests
import google.generativeai as genai
import sys
from datetime import datetime

# 1. 讀取密鑰
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def fetch_and_summarize():
    url = f"https://newsapi.org/v2/everything?q=AI&language=zh&sortBy=publishedAt&pageSize=8&apiKey={NEWS_API_KEY}"
    
    try:
        # 抓取新聞
        response = requests.get(url)
        articles = response.json().get("articles", [])
        news_content = ""
        for i, a in enumerate(articles):
            news_content += f"\n新聞 {i+1}：{a.get('title')}\n連結：{a.get('url')}\n"

        # 2. 設定 Gemini
        genai.configure(api_key=GEMINI_API_KEY)
        
        # 獲取「真正」可用的模型清單
        print("正在獲取可用模型清單...")
        raw_models = list(genai.list_models())
        available_names = [m.name for m in raw_models if 'generateContent' in m.supported_generation_methods]
        
        # 顯示在 GitHub Log 中方便除錯
        print(f"你的帳號目前可用的模型完整清單：{available_names}")

        # 策略：挑選包含 'flash' 或 'pro' 的模型，並優先使用最新版
        # 優先順序：1.5-flash > 1.5-pro > 2.0-flash > gemini-pro
        best_model = None
        priority_keywords = ['1.5-flash', '1.5-pro', '2.0-flash', 'gemini-pro']
        
        for keyword in priority_keywords:
            for name in available_names:
                if keyword in name:
                    best_model = name
                    break
            if best_model: break
        
        if not best_model:
            best_model = available_names[0] if available_names else None

        if not best_model:
            raise Exception(f"找不到任何支援 generateContent 的模型。清單為：{available_names}")

        print(f"🚀 最終決定使用模型：{best_model}")

        # 3. 執行生成
        model = genai.GenerativeModel(model_name=best_model)
        prompt = f"請將以下新聞整理成繁體中文摘要，並列出今日科技趨勢：\n{news_content}"
        
        ai_response = model.generate_content(prompt)
        
        # 4. 寫入成果
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open("daily_report.md", "w", encoding="utf-8") as f:
            f.write(f"# 🤖 AI 每日新聞洞察\n\n{ai_response.text}\n\n")
            f.write(f"--- \n**⚙️ 偵錯資訊**\n- 執行時間：{current_time}\n- 選用模型：`{best_model}`\n- 全部可用模型：`{available_names}`")

        print("✅ 任務圓滿完成！")

    except Exception as e:
        error_details = f"錯誤類型：{type(e).__name__}\n內容：{str(e)}"
        with open("daily_report.md", "w", encoding="utf-8") as f:
            f.write(f"# ❌ 執行失敗報告\n\n{error_details}")
        print(f"💥 發生錯誤：{error_details}")

if __name__ == "__main__":
    fetch_and_summarize()
