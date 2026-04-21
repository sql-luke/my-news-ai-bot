import os
import requests
import google.generativeai as genai

# 從 GitHub Secrets 讀取鑰匙
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# 設定 Gemini
genai.configure(api_key=GEMINI_API_KEY)

def fetch_and_summarize():
    # 1. 向 News API 索取最新的科技新聞 (以中文為例)
    # 你可以把 q=technology 改成 q=AI 或 q=Taiwan
    url = f"https://newsapi.org/v2/everything?q=AI&language=zh&sortBy=publishedAt&apiKey={NEWS_API_KEY}"
    
    response = requests.get(url).json()
    articles = response.get("articles", [])[:5] # 只取前 5 則

    if not articles:
        print("目前沒有找到相關新聞")
        return

    # 2. 整理新聞內容給 Gemini 分析
    news_content = ""
    for i, a in enumerate(articles):
        news_content += f"\n新聞 {i+1}：{a['title']}\n摘要：{a['description']}\n連結：{a['url']}\n"

    # 3. 呼叫 Gemini 進行深度分析
    model = genai.GenerativeModel('gemini-1.5-flash') # 使用最新的輕量化模型
    prompt = f"""
    你是一個專業的新聞分析師。請根據以下新聞內容，整理出一份簡報：
    1. 總結今日 3 大科技重點。
    2. 分析這些新聞對一般人的潛在影響。
    3. 用繁體中文回答，語氣要輕鬆且專業。
    
    新聞內容：
    {news_content}
    """
    
    ai_response = model.generate_content(prompt)
    
    # 4. 把結果存成 Markdown 檔案
    with open("daily_report.md", "w", encoding="utf-8") as f:
        f.write("# 🤖 AI 每日新聞洞察\n\n")
        f.write(ai_response.text)
        f.write("\n\n--- \n*本報告由 Gemini AI 自動生成*")

if __name__ == "__main__":
    fetch_and_summarize()
