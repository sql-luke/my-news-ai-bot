import os
import requests
import google.generativeai as genai
import sys

# 讀取金鑰
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def fetch_and_summarize():
    # 改用關鍵字搜尋 (Everything)，這樣抓到資料的機率最高
    # 你可以把 q=AI 改成你感興趣的字，例如 q=Apple 或 q=Nvidia
    url = f"https://newsapi.org/v2/everything?q=AI&language=zh&sortBy=publishedAt&pageSize=5&apiKey={NEWS_API_KEY}"
    
    try:
        response = requests.get(url)
        data = response.json()
        articles = data.get("articles", [])
        
        report_text = ""
        
        if not articles:
            report_text = "⚠️ 今日 News API 沒有回傳任何相關新聞。"
        else:
            # 整理新聞內容
            news_content = ""
            for i, a in enumerate(articles):
                news_content += f"\n新聞 {i+1}：{a.get('title','')}\n摘要：{a.get('description','')}\n"
            
            # 呼叫 Gemini
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"請將以下新聞整理成繁體中文摘要：\n{news_content}"
            ai_response = model.generate_content(prompt)
            report_text = ai_response.text

        # 🚀 重點：無論如何都一定要寫出檔案！
        with open("daily_report.md", "w", encoding="utf-8") as f:
            f.write("# 🤖 AI 每日新聞洞察\n\n")
            f.write(report_text)
            
        print("✅ 檔案已成功寫入 daily_report.md")

    except Exception as e:
        # 如果真的大爆炸，也要寫出錯誤報告，不要讓下一個步驟找不到檔案
        with open("daily_report.md", "w", encoding="utf-8") as f:
            f.write(f"❌ 程式執行發生錯誤：{e}")
        print(f"❌ 發生錯誤：{e}")

if __name__ == "__main__":
    fetch_and_summarize()
