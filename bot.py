import os
import json
import requests
from flask import Flask, request

app = Flask(__name__)

TOKEN = os.environ.get("TELEGRAM_TOKEN")  # حتما در Render اضافه کن
API = f"https://api.telegram.org/bot{TOKEN}"

# --- داده‌های نمونه (می‌تونی تغییر بدی) ---
links = {
    "groups": [("گروه ۱", "https://t.me/example_group1")],
    "channels": [("کانال ۱", "https://t.me/example_channel1")],
}
videos = [("ویدیو نمونه", "https://file-examples.com/storage/.../sample.mp4")]
contacts = [{"name":"علی","phone":"09120000000","email":"ali@example.com"}]
pdfs = [("فرم ثبت‌نام", "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf")]
bosses_text = "توضیحات دربارهٔ رئیسا..."
info_text = "اطلاعات بیشتر دربارهٔ ربات..."

# حالت ساده برای جست‌وجو (in-memory). در production از دیتابیس استفاده کن
search_mode = {}

# --- توابع کمکی ---
def tg_post(method, payload):
    url = f"{API}/{method}"
    return requests.post(url, json=payload, timeout=10)

def send_message(chat_id, text, reply_markup=None, parse_mode=None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
    if parse_mode:
        payload["parse_mode"] = parse_mode
    return tg_post("sendMessage", payload)

def answer_callback(cb_id, text=None):
    payload = {"callback_query_id": cb_id}
    if text: payload["text"] = text
    return tg_post("answerCallbackQuery", payload)

# کیبورد اصلی
def main_menu_kb():
    return {"inline_keyboard": [
        [{"text":"🔗 لینک‌های مفید","callback_data":"links"}],
        [{"text":"🎥 ویدیوهای مفید","callback_data":"videos"}],
        [{"text":"📧 ایمیل‌ها","callback_data":"emails"}],
        [{"text":"🔎 جست‌وجو در ایمیل‌ها","callback_data":"search"}],
        [{"text":"👔 توضیحات رئیسا","callback_data":"bosses"}],
        [{"text":"📄 فرم‌ها","callback_data":"forms"}],
        [{"text":"ℹ️ اطلاعات بیشتر","callback_data":"info"}],
    ]}

@app.route("/")
def index():
    return "OK", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json(force=True)

    # ---------- پیام متنی ----------
    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        user_id = msg["from"]["id"]
        text = msg.get("text","")

        if text == "/start":
            send_message(chat_id, "سلام! یکی از گزینه‌ها را انتخاب کن:", reply_markup=main_menu_kb())
            return "ok", 200

        # حالت جست‌وجو (پس از زدن دکمه search)
        if search_mode.get(user_id):
            q = text.strip().lower()
            results = [c for c in contacts if q in c["name"].lower()]
            if not results:
                send_message(chat_id, f"کسی با نامِ '{text}' پیدا نشد.", reply_markup=main_menu_kb())
            else:
                for r in results:
                    send_message(chat_id, f"نام: {r['name']}\nشماره: {r['phone']}\nایمیل: {r['email']}")
            search_mode.pop(user_id, None)
            return "ok", 200

        # هر پیام دیگه -> راهنمایی
        send_message(chat_id, "لطفاً از منو استفاده کن یا /start را بزن.", reply_markup=main_menu_kb())
        return "ok", 200

    # ---------- callback_query (دکمه‌های اینلاین) ----------
    if "callback_query" in update:
        cq = update["callback_query"]
        data = cq.get("data")
        cb_id = cq.get("id")
        chat = cq["message"]["chat"]
        chat_id = chat["id"]

        answer_callback(cb_id)  # تایید کلیک

        if data == "links":
            kb = [
                [{"text":"گروه‌ها","callback_data":"links_groups"}],
                [{"text":"کانال‌ها","callback_data":"links_channels"}],
                [{"text":"بازگشت","callback_data":"back"}],
            ]
            send_message(chat_id, "کدوم دسته؟", reply_markup={"inline_keyboard": kb})
            return "ok",200

        if data == "links_groups":
            text = "گروه‌ها:\n" + "\n".join([f"{n} — {u}" for n,u in links["groups"]])
            send_message(chat_id, text, reply_markup={"inline_keyboard":[[{"text":"بازگشت","callback_data":"links"}]]})
            return "ok",200

        if data == "links_channels":
            text = "کانال‌ها:\n" + "\n".join([f"{n} — {u}" for n,u in links["channels"]])
            send_message(chat_id, text, reply_markup={"inline_keyboard":[[{"text":"بازگشت","callback_data":"links"}]]})
            return "ok",200

        if data == "videos":
            kb = [[{"text":v[0],"callback_data":f"video_{i}"}] for i,v in enumerate(videos)]
            kb.append([{"text":"بازگشت","callback_data":"back"}])
            send_message(chat_id, "لیست ویدیوها:", reply_markup={"inline_keyboard": kb})
            return "ok",200

        if data and data.startswith("video_"):
            i = int(data.split("_",1)[1])
            # ارسال ویدئو از url (تلگرام از url پشتیبانی می‌کند)
            url = videos[i][1]
            # sendVideo:
            requests.post(f"{API}/sendVideo", json={"chat_id":chat_id, "video":url, "caption": videos[i][0]})
            return "ok",200

        if data == "emails":
            text = "\n\n".join([f"👤 {c['name']}\n📞 {c['phone']}\n✉️ {c['email']}" for c in contacts])
            send_message(chat_id, text, reply_markup={"inline_keyboard":[[{"text":"بازگشت","callback_data":"back"}]]})
            return "ok",200

        if data == "search":
            # علامت می‌زنیم که کاربر در حالت جست‌وجوست
            uid = cq["from"]["id"]
            search_mode[uid] = True
            send_message(chat_id, "نام فرد را تایپ کن و ارسال کن:")
            return "ok",200

        if data == "forms":
            kb = [[{"text":p[0],"callback_data":f"pdf_{i}"}] for i,p in enumerate(pdfs)]
            kb.append([{"text":"بازگشت","callback_data":"back"}])
            send_message(chat_id, "فرم‌ها:", reply_markup={"inline_keyboard": kb})
            return "ok",200

        if data and data.startswith("pdf_"):
            i = int(data.split("_",1)[1])
            url = pdfs[i][1]
            requests.post(f"{API}/sendDocument", json={"chat_id":chat_id, "document":url, "caption": pdfs[i][0]})
            return "ok",200

        if data == "bosses":
            send_message(chat_id, bosses_text, reply_markup={"inline_keyboard":[[{"text":"بازگشت","callback_data":"back"}]]})
            return "ok",200

        if data == "info":
            send_message(chat_id, info_text, reply_markup={"inline_keyboard":[[{"text":"بازگشت","callback_data":"back"}]]})
            return "ok",200

        if data == "back":
            send_message(chat_id, "یکی از گزینه‌ها را انتخاب کن:", reply_markup=main_menu_kb())
            return "ok",200

    return "ok", 200

if __name__ == "__main__":
    app.run(debug=True)
