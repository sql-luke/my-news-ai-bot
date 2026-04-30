import os
import json
import asyncio
import requests
import time
import xml.etree.ElementTree as ET
import edge_tts
from pydub import AudioSegment
import google.generativeai as genai

# ==========================================
# 1. 讀取 GitHub Secrets 環境變數
# ==========================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
LINE_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
GDRIVE_FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID")
GDRIVE_CLIENT_ID = os.getenv("GDRIVE_CLIENT_ID")
GDRIVE_CLIENT_SECRET = os.getenv("GDRIVE_CLIENT_SECRET")
GDRIVE_REFRESH_TOKEN = os.getenv("GDRIVE_REFRESH_TOKEN")

if not GEMINI_API_KEY:
    print("❌ 嚴重錯誤：找不到 GEMINI_API_KEY")
    exit(1)

genai.configure(api_key=GEMINI_API_KEY)

VOICES = {
    "HostA": "zh-TW-HsiaoChenNeural", # 女聲 (主導播報)
    "HostB": "zh-TW-YunJheNeural"     # 男聲 (搭檔互動)
}

# ==========================================
# 2. 自動抓取 Google 即時新聞
# ==========================================
def fetch_real_time_news():
    print("📰 正在為「晨間廣播節目表」抓取各分類即時資訊...")
    
    def get_news_from_rss(url, limit=2):
        try:
            res = requests.get(url, timeout=15)
            res.raise_for_status()
            root = ET.fromstring(res.content)
            items = root.findall('.//item')
            news_list = []
            for item in items[:limit]:
                title = item.find('title').text
                news_list.append(f"- {title}")
            return "\n".join(news_list)
        except Exception as e:
            return f"無法抓取此分類: {e}"

    weather_url = "https://news.google.com/rss/search?q=%E5%8F%B0%E7%81%A3+%E5%A4%A9%E6%B0%A3+%E6%BA%AB%E5%BA%A6&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    world_url = "https://news.google.com/rss/headlines/section/topic/WORLD?hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    finance_url = "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    tech_url = "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    ent_url = "https://news.google.com/rss/headlines/section/topic/ENTERTAINMENT?hl=zh-TW&gl=TW&ceid=TW:zh-Hant"

    final_content = f"""
    🌤️【氣象情報】：\n{get_news_from_rss(weather_url, 2)}
    🌍【國際頭條】：\n{get_news_from_rss(world_url, 2)}
    💰【財經市場】：\n{get_news_from_rss(finance_url, 2)}
    🔬【科技酷報】：\n{get_news_from_rss(tech_url, 2)}
    🍿【生活娛樂】：\n{get_news_from_rss(ent_url, 2)}
    """
    print("✅ 節目素材抓取完成！")
    return final_content

# ==========================================
# 3. 核心功能：雙人劇本生成 (Gemini 1.5 Pro 頂級版)
# ==========================================
def generate_podcast_script(news_summary):
    prompt = f"""
    你現在是頂級的 AI 晨間廣播節目製作人，風格模仿 NotebookLM，自然、生動、幽默。
    請根據以下「即時新聞內容」，寫一段 HostA (女) 與 HostB (男) 的晨間廣播劇本。
    
    【廣播節目表流程】
    1. 🌤️ 早安氣象站：HostA 開場問好，並給出出門建議。
    2. 🌍 國際頭條雷達：兩人聊聊世界發生的大事。
    3. 💰 財經與市場：帶出股市脈動或理財趨勢。
    4. 🔬 科技酷報：分享 AI 新知或 3C 產品消息。
    5. 🍿 生活與娛樂：聊聊影劇或流行文化。
    6. 📖 每日一句：送上一句激勵人心的名言。
    
    【對話要求】
    1. 絕對口語化：多用「沒錯」、「對呀」、「你知道嗎」、「哇塞」。
    2. 反應式對話：一人講完重要資訊，另一人要給予簡短的情緒反應。
    3. 避免純符號：台詞中一定要有文字，不能只有表情符號。
    
    輸出格式：純 JSON 陣列 (List of objects)，絕對不要包在 dict 裡面，不要 Markdown 標記。
    範例：[ {{"speaker": "HostA", "text": "大家好..."}}, {{"speaker": "HostB", "text": "早安..."}} ]
    
    今日節目素材：
    {news_summary}
    """
    
    print("🚀 準備呼叫頂級模型：gemini-1.5-pro...")
    
    for attempt in range(3):
        try:
            model = genai.GenerativeModel('gemini-1.5-pro')
            response = model.generate_content(prompt, request_options={"timeout": 60})
            
            content = response.text.strip()
            triple_backticks = chr(96) * 3 
            content = content.replace(triple_backticks + "json", "").replace(triple_backticks, "").strip()
            
            script_data = json.loads(content)
            
            if isinstance(script_data, dict):
                print("⚠️ 偵測到劇本被包裝在字典中，正在自動解開...")
                for key, value in script_data.items():
                    if isinstance(value, list):
                        script_data = value
                        break
                        
            if isinstance(script_data, list) and len(script_data) > 0:
                print(f"✅ 成功使用 1.5-pro 解析劇本！共產生 {len(script_data)} 句對話。")
                return script_data
            else:
                raise Exception("解析後的劇本為空或格式錯誤。")
            
        except Exception as e:
            error_msg = str(e)
            print(f"⚠️ 執行失敗 (第 {attempt + 1} 輪): {error_msg}")
            print("⏳ 稍微暫停 10 秒後重試...")
            time.sleep(10)
            continue
            
    raise Exception("❌ 多次嘗試皆無法成功生成劇本，請檢查 API 狀態。")

# ==========================================
# 4. 核心功能：語音生成與 BGM 混音
# ==========================================
async def generate_audio(script, output_file):
    print(f"🎙️ 準備開始錄製 {len(script)} 句對話...")
    final_audio = AudioSegment.empty()
    success_count = 0
    
    for i, line in enumerate(script):
        if not isinstance(line, dict): continue
            
        text = line.get('text', '').strip()
        speaker = line.get('speaker', 'HostA')
        voice = VOICES.get(speaker, VOICES["HostA"])
        temp_name = f"segment_{i}.mp3"
        
        if not text: continue
            
        try:
            print(f"  🗣️ 錄製中 [{speaker}]: {text[:20]}...")
            communicate = edge_tts.Communicate(text, voice)
            await asyncio.wait_for(communicate.save(temp_name), timeout=60.0)
            
            if os.path.exists(temp_name) and os.path.getsize(temp_name) > 0:
                segment = AudioSegment.from_mp3(temp_name)
                pause_duration = 300 if speaker == "HostB" else 450
                pause = AudioSegment.silent(duration=pause_duration)
                
                final_audio += segment + pause
                success_count += 1
        except Exception as e:
            print(f"  ❌ 失敗: {e}")
        finally:
            if os.path.exists(temp_name):
                os.remove(temp_name)
    
    if len(final_audio) > 0 and success_count > 0:
        print(f"✅ 錄製完畢！成功縫合 {success_count} 句對話。")
        
        # --- BGM 混音處理區塊 ---
        bgm_file = "bgm.mp3"
        if os.path.exists(bgm_file):
            print("🎵 找到 bgm.mp3，正在進行背景音樂混音處理...")
            try:
                bgm = AudioSegment.from_mp3(bgm_file)
                # 降低背景音量 (-22 分貝)，確保不會蓋過人聲
                bgm = bgm - 22
                # 將 BGM 延長循環，直到能覆蓋整段人聲長度
                bgm_looped = bgm * (len(final_audio) // len(bgm) + 1)
                # 裁切至與人聲剛好等長
                bgm_looped = bgm_looped[:len(final_audio)]
                # 將人聲與背景音疊加
                final_audio = final_audio.overlay(bgm_looped)
                print("✅ 混音完美達成！")
            except Exception as e:
                print(f"⚠️ 背景音樂混音失敗，將輸出純人聲版本: {e}")
        else:
            print("⚠️ 未偵測到 bgm.mp3，將直接輸出純人聲版本。")
        # ------------------------

        final_audio.export(output_file, format="mp3", bitrate="128k")
        return output_file
    else:
        raise Exception("所有語音段落皆生成失敗，無法產出 MP3。")

# ==========================================
# 5. API 實作：Google Drive 上傳
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
    r = requests.post(token_url, data=token_data, timeout=30)
    r.raise_for_status()
    access_token = r.json().get("access_token")

    metadata = {"name": os.path.basename(file_path), "parents": [GDRIVE_FOLDER_ID]}
    files = {'data': ('metadata', json.dumps(metadata), 'application/json'), 'file': open(file_path, 'rb')}
    upload_url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    res = requests.post(upload_url, headers=headers, files=files, timeout=60)
    res.raise_for_status()
    file_id = res.json().get("id")

    perm_url = f"https://www.googleapis.com/drive/v3/files/{file_id}/permissions"
    requests.post(perm_url, headers=headers, json={"role": "reader", "type": "anyone"}, timeout=30)
    
    return f"https://docs.google.com/uc?export=download&id={file_id}"

# ==========================================
# 6. API 實作：LINE 廣播群發
# ==========================================
def send_line_podcast_broadcast(audio_url):
    print("💬 正在向所有好友發送 LINE 群發訊息...")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"
    }
    
    payload = {
        "messages": [{
            "type": "flex",
            "altText": "您的晨間 AI 廣播節目已送到！",
            "contents": {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {"type": "text", "text": "📻 晨間 AI 廣播", "weight": "bold", "size": "xl"},
                        {"type": "text", "text": "氣象/國際/財經/科技/娛樂/金句", "size": "xs", "color": "#aaaaaa", "margin": "sm"},
                        {
                            "type": "button",
                            "action": {"type": "uri", "label": "▶️ 點擊收聽節目", "uri": audio_url},
                            "style": "primary",
                            "color": "#1DB446",
                            "margin": "xl"
                        }
                    ]
                }
            }
        }]
    }
    
    res = requests.post("https://api.line.me/v2/bot/message/broadcast", headers=headers, json=payload, timeout=15)
    res.raise_for_status()
    print("✅ 群發廣播成功！")

# ==========================================
# 主程式
# ==========================================
def main():
    try:
        print("🚀 開始執行【晨間 AI 廣播節目】任務...")
        news_content = fetch_real_time_news()
        script = generate_podcast_script(news_content)
        
        output_file = "morning_radio_podcast.mp3"
        asyncio.run(generate_audio(script, output_file))
        
        audio_link = upload_to_gdrive(output_file)
        send_line_podcast_broadcast(audio_link)
        
        print("🎉 節目製作與推播已完美達成！")
    except Exception as e:
        print(f"\n❌ 錯誤: {e}")

if __name__ == "__main__":
    main()
