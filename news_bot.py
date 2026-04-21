import os
import requests
import google.generativeai as genai
import sys

# 讀取金鑰
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def fetch_and_summarize():
    # 1. 抓取新聞 (Everything 模式最穩定)
    url = f"https://newsapi.org/v2/everything?q=AI&language=zh&sortBy=publishedAt&pageSize=5&apiKey={NEWS_API_KEY}"
    
    try:
        response = requests.get(url)
        data = response.json()
        articles = data.get("articles", [])
        
        report_text = ""
        
        if not articles:
            report_text = "⚠️ 今日 News API 沒有回傳任何相關新聞。"
        else:
            news_content = ""
            for i, a in enumerate(articles):
                news_content += f"\n新聞 {i+1}：{a.get('title','')}\n摘要：{a.get('description','')}\n"
            
            # 2. 設定 Gemini 與模型偵測
            genai.configure(api_key=GEMINI_API_KEY)
            
            # --- 🚀 自動偵測可用模型邏輯 ---
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            print(f"你目前可用的模型有: {available_models}")
            
            # 優先順序：1.5-flash > 1.5-pro > gemini-pro
            target_models = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-pro']
            chosen_model = None
            
            for tm in target_models:
                if tm in available_models:
                    chosen_model = tm
                    break
            
            if not chosen_model:
                chosen_model = available_models[0] # 如果都沒有，就抓第一個能用的
            
            print(f"🔄 正在使用模型: {chosen_model}")
            # ---------------------------
            
            model = genai.GenerativeModel(chosen_model)
            prompt = f"請將以下新聞整理成繁體中文摘要，並列出三個今日最值得關注的科技趨勢：\n{news_content}"
            
            ai_response = model.generate_content(prompt)
            report_text = ai_response.text

        # 3. 寫入檔案
        with open("daily_report.md", "w", encoding="utf-8") as f:
            f.write("# 🤖 AI 每日新聞洞察\n\n")
            f.write(report_text)
            f.write(f"\n\n--- \n*使用模型：{chosen_model}*")
            
        print("✅ 報告生成成功！")

    except Exception as e:
        with open("daily_report.md", "w", encoding="utf-8") as f:
            f.write(f"❌ 發生錯誤：{e}")
        print(f"❌ 錯誤細節：{e}")

if __name__ == "__main__":
    fetch_and_summarize()
