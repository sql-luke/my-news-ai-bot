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
LINE_USER_ID = os.getenv("LINE_USER_ID")
GDRIVE_FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID")
GDRIVE_CLIENT_ID = os.getenv("GDRIVE_CLIENT_ID")
GDRIVE_CLIENT_SECRET = os.getenv("GDRIVE_CLIENT_SECRET")
GDRIVE_REFRESH_TOKEN = os.getenv("GDRIVE_REFRESH_TOKEN")

# 設定 Gemini
genai.configure(api_key=GEMINI_API_KEY)

# 語音角色設定
VOICES = {
    "HostA": "zh-TW-HsiaoChenNeural", # 女聲
    "HostB": "zh-TW-YunJheNeural"     # 男聲
}

# ==========================================
# 2. 核心功能：雙人劇本生成
# ==========================================
def generate_podcast_script(news_summary):
    prompt = f"""
    你現在是專業 Podcast 製作人。請根據以下新聞內容，寫一段兩人對話的 Podcast 劇本。
    - HostA (女)：主持人，節奏輕快、負責開場與主要播報。
    - HostB (男)：搭檔，負責提問、補充有趣點、或表達驚訝。
    請確保對話生動，像是在聊天而不是唸稿。
    
    輸出格式：純 JSON 陣列，不要有 Markdown 標記。
    範例：[
      {{"speaker": "HostA", "text": "嘿 B，你知道嗎？今天的氣象..."}},
      {{"speaker": "HostB", "text": "喔？快說來聽聽！"}}
    ]
    
    新聞內容：{news_summary}
    """
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(prompt)
    content = response.text.replace('```json', '').replace('```', '').strip()
    return json.loads(content)

# ==========================================
# 3. 核心功能：語音生成與拼接
# ==========================================
async def generate_audio(script, output_file):
    final_audio = AudioSegment.empty()
    pause = AudioSegment.silent(duration=400) # 對話間隔 0.4 秒
    
    for i, line in enumerate(script):
        text = line['text']
        voice = VOICES.get(line['speaker'], VOICES["HostA"])
        temp_name = f"segment_{i}.mp3"
        
        # 產生單句語音
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(temp_name)
        
        # 拼接
        segment = AudioSegment.from_mp3(temp_name)
        final_audio += segment + pause
        os.remove(temp_name)
    
    final_audio.export(output_file, format="mp3")
    return output_file

# ==========================================
# 4. API 實作：Google Drive 上傳 (使用 Secrets)
# ==========================================
def upload_to_gdrive(file_path):
    print("📡 正在上傳至 Google Drive...")
    # A. 透過 Refresh Token 換取臨時 Access Token
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "client_id": GDRIVE_CLIENT_ID,
        "client_secret": GDRIVE_CLIENT_SECRET,
        "refresh_token": GDRIVE_REFRESH_TOKEN,
        "grant_type": "refresh_token",
    }
    r = requests.post(token_url, data=token_data)
    access_token = r.json().get("access_token")

    # B. 上傳檔案
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
    file_id = res.json().get("id")

    # C. 設定權限為公開讀取並取得連結 (這步很重要，否則 LINE 不能播)
    perm_url = f"https://www.googleapis.com/drive/v3/files/{file_id}/permissions"
    requests.post(perm_url, headers=headers, json={"role": "reader", "type": "anyone"})
    
    # 回傳直接下載連結 (LINE 需要可以直接讀取到 mp3 的網址)
    return f"https://docs.google.com/uc?export=download&id={file_id}"

# ==========================================
# 5. API 實作：LINE Flex Message 推播
# ==========================================
def send_line_podcast(audio_url):
    print("💬 正在發送 LINE 訊息...")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"
    }
    payload = {
        "to": LINE_USER_ID,
        "messages": [{
            "type": "flex",
            "altText": "您的雙聲道新聞 Podcast 已送到！",
            "contents": {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {"type": "text", "text": "🎙️ 今日雙人 Podcast 新聞", "weight": "bold", "size": "xl"},
                        {"type": "text", "text": "Gemini & Edge TTS 聯合製作", "size": "xs", "color": "#aaaaaa"},
                        {
                            "type": "button",
                            "action": {
                                "type": "uri",
                                "label": "立即點擊播放",
                                "uri": audio_url
                            },
                            "style": "primary",
                            "margin": "md"
                        }
                    ]
                }
            }
        }]
    }
    requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=payload)

# ==========================================
# 主程式
# ==========================================
def main():
    # 這裡放你原本抓取新聞的邏輯，以下為測試模擬
    news_content = "今日重點：氣象局發布低溫特報，北部僅12度；美股收紅；台積電漲10元。"
    
    try:
        print("1. 生成劇本...")
        script = generate_podcast_script(news_content)
        
        print("2. 製作音檔...")
        output_file = "podcast.mp3"
        asyncio.run(generate_audio(script, output_file))
        
        print("3. 上傳雲端...")
        audio_link = upload_to_gdrive(output_file)
        
        print(f"4. 發送 LINE (網址: {audio_link})")
        send_line_podcast(audio_link)
        
        print("✅ 任務完成！")
    except Exception as e:
        print(f"❌ 發生錯誤: {e}")

if __name__ == "__main__":
    main()
