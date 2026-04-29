import os
import json
import asyncio
import requests
import edge_tts
from pydub import AudioSegment
import google.generativeai as genai

# ==========================================
# 1. 讀取 GitHub Secrets 環境變數
# ==========================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
LINE_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
# ⚠️ 注意：已經移除 LINE_USER_ID，因為我們改用全體群發廣播！
GDRIVE_FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID")
GDRIVE_CLIENT_ID = os.getenv("GDRIVE_CLIENT_ID")
GDRIVE_CLIENT_SECRET = os.getenv("GDRIVE_CLIENT_SECRET")
GDRIVE_REFRESH_TOKEN = os.getenv("GDRIVE_REFRESH_TOKEN")

if not GEMINI_API_KEY:
    print("❌ 嚴重錯誤：找不到 GEMINI_API_KEY")
    exit(1)

genai.configure(api_key=GEMINI_API_KEY)

VOICES = {
    "HostA": "zh-TW-HsiaoChenNeural", # 女聲
    "HostB": "zh-TW-YunJheNeural"     # 男聲
}

# ==========================================
# 2. 核心功能：雙人劇本生成 (頭條加強版)
# ==========================================
def generate_podcast_script(news_summary):
    prompt = f"""
    你現在是專業的 AI Podcast 製作人，風格模仿 NotebookLM。
    請根據以下新聞內容，寫一段 HostA (女) 與 HostB (男) 的深度聊天劇本。
    
    【核心播報任務】
    請務必在對話中，清晰且自然地帶出以下重點：
    1. 3 則國際重大頭條新聞。
    2. 3 則國內重大頭條新聞。
    3. 其他生活、科技或氣象重點。
    
    【製作要求】
    1. 非常口語化：多使用「嗯...」、「對啊」、「其實」、「你知道嗎？」、「我跟你說喔」。
    2. 反應式對話：當 HostA 講完一個新聞點，HostB 不要直接講下一個，要先給予短回應。
    3. 節奏感：每句話不要太長，像真實聊天一樣有來有往。
    
    輸出格式：純 JSON 陣列，不要有任何 Markdown 標記或說明文字。
    範例：[
      {{"speaker": "HostA", "text": "各位聽眾早安！今天的國內外大事真的很多，首先來關心國際焦點..."}},
      {{"speaker": "HostB", "text": "沒錯，第一件大事就跟我們息息相關..."}}
    ]
    
    今日新聞內容：
    {news_summary}
    """
    
    print("🔍 查詢可用模型...")
    available_models = []
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name.replace('models/', ''))
    except Exception as e:
        print(f"查詢失敗: {e}")

    preferred = ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-pro']
    selected = next((m for m in preferred if m in available_models), available_models[0])
    print(f"🚀 使用模型: {selected}")
    
    try:
        model = genai.GenerativeModel(selected)
        response = model.generate_content(prompt)
        
        content = response.text.strip()
        triple_backticks = chr(96) * 3 
        content = content.replace(triple_backticks + "json", "").replace(triple_backticks, "").strip()
            
        return json.loads(content)
    except Exception as e:
        raise Exception(f"生成劇本失敗: {e}")

# ==========================================
# 3. 核心功能：語音生成與拼接
# ==========================================
async def generate_audio(script, output_file):
    print("🎙️ 正在生成語音並進行無縫拼接...")
    final_audio = AudioSegment.empty()
    
    for i, line in enumerate(script):
        text = line.get('text', '')
        speaker = line.get('speaker', 'HostA')
        voice = VOICES.get(speaker, VOICES["HostA"])
        temp_name = f"segment_{i}.mp3"
        
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(temp_name)
        
        segment = AudioSegment.from_mp3(temp_name)
        
        pause_duration = 300 if speaker == "HostB" else 500
        pause = AudioSegment.silent(duration=pause_duration)
        
        final_audio += segment + pause
        os.remove(temp_name)
    
    final_audio.export(output_file, format="mp3", bitrate="128k")
    return output_file

# ==========================================
# 4. API 實作：Google Drive 上傳
# ==========================================
def upload_to_gdrive(file_path):
    print("📡 正在上傳至 Google Drive...")
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "client_id": GDRIVE_CLIENT_ID,
        "client_secret": GDRIVE_CLIENT_SECRET,
        "refresh_token": GDRIVE_REFRESH_TOKEN,
        "grant_type": "refresh_token",
    }
    r = requests.post(token_url, data=token_data)
    r.raise_for_status()
    access_token = r.json().get("access_token")

    metadata = {
        "name": os.path.basename(file_path),
        "parents": [GDRIVE_FOLDER_ID]
    }
    files = {
        'data': ('metadata', json.dumps(metadata), 'application/json'),
        'file': open(file_path, 'rb')
    }
    upload_url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
    headers = {"Authorization": f"Bearer {access_token}"}
    res = requests.post(upload_url, headers=headers, files=files)
    res.raise_for_status()
    file_id = res.json().get("id")

    perm_url = f"https://www.googleapis.com/drive/v3/files/{file_id}/permissions"
    requests.post(perm_url, headers=headers, json={"role": "reader", "type": "anyone"})
    
    return f"https://docs.google.com/uc?export=download&id={file_id}"

# ==========================================
# 5. API 實作：LINE 廣播 (Broadcast)
# ==========================================
def send_line_podcast_broadcast(audio_url):
    print("💬 正在向【所有好友】發送 LINE 群發訊息...")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"
    }
    
    # 群發 API 不需要指定 "to" 欄位，它會自動發給所有沒封鎖機器的的好友
    payload = {
        "messages": [{
            "type": "flex",
            "altText": "雙聲道頭條新聞 Podcast 已送到！",
            "contents": {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {"type": "text", "text": "🎙️ 今日國內外大事 Podcast", "weight": "bold", "size": "xl"},
                        {"type": "text", "text": "為您整理 6 大國內外頭條", "size": "xs", "color": "#aaaaaa", "margin": "sm"},
                        {
                            "type": "button",
                            "action": {
                                "type": "uri",
                                "label": "▶️ 立即收聽",
                                "uri": audio_url
                            },
                            "style": "primary",
                            "color": "#1DB446",
                            "margin": "xl"
                        }
                    ]
                }
            }
        }]
    }
    
    # 改為呼叫 broadcast API 網址
    line_url = "https://api.line.me/v2/bot/message/broadcast"
    res = requests.post(line_url, headers=headers, json=payload)
    res.raise_for_status()
    print("✅ 群發廣播成功！所有好友都收到了！")

# ==========================================
# 主程式
# ==========================================
def main():
    # 這裡的模擬資料加入了國內外各三則的具體內容
    # 未來如果你接上真正的爬蟲，只要把爬到的頭條塞進這個字串即可
    news_content = """
    【國際重大頭條】
    1. 蘋果發布最新 AI 晶片，宣稱效能提升 30%，股價大漲。
    2. 聯合國召開緊急氣候峰會，多國承諾提前達成淨零碳排。
    3. 日本央行意外宣布升息，日圓急遽升值，震驚全球市場。

    【國內重大頭條】
    1. 立法院三讀通過居住正義法案，提高囤房稅率最高至 4.8%。
    2. 台積電宣布將在南部科學園區擴建新廠，預計創造上萬就業機會。
    3. 疾管署發布流感警報，單週就診人數突破 10 萬人次，呼籲盡速施打疫苗。

    【科技與生活】
    科技：OpenAI 推出全新語音模型，反應速度媲美真人對話。
    氣象：強烈冷氣團明晚南下，北部低溫下探 12 度，全台有雨。
    生活：最新醫學研究顯示，睡前滑手機超過半小時，深層睡眠時間減少 20%。
    """
    
    try:
        print("🚀 開始執行 AI Podcast 任務...")
        script = generate_podcast_script(news_content)
        
        output_file = "daily_news_podcast.mp3"
        asyncio.run(generate_audio(script, output_file))
        
        audio_link = upload_to_gdrive(output_file)
        
        # 改為呼叫群發函數
        send_line_podcast_broadcast(audio_link)
        
        print("🎉 全部優化任務已完成！")
    except Exception as e:
        print(f"\n❌ 錯誤: {e}")

if __name__ == "__main__":
    main()
