# 🎵 Telegram Music Player Bot

မြန်မာဘာသာဖြင့် အလုပ်လုပ်သော Telegram Music Player Bot — MongoDB Atlas နှင့် Render.com တွင် run နိုင်ရန် ပြုလုပ်ထားပါသည်။

## ✨ Features
- 📀 Album / Category အလိုက် သီချင်းများ ကြည့်ရှုနိုင်ခြင်း
- 🎵 သီချင်းကို chat ထဲ ပို့ပေးခြင်း (Audio file)
- 🔍 သီချင်းအမည်ဖြင့် ရှာဖွေနိုင်ခြင်း
- 🔥 လူကြိုက်များသော သီချင်း စာရင်း (Downloads အလိုက်)
- 👑 Admin Panel: အမျိုးအစား / Album / သီချင်းများ စီမံခန့်ခွဲခြင်း
- 📢 Channel Bot: channel ထဲ သီချင်းတင်တိုင်း bot က file_id သိမ်းပြီး user များ ရယူနိုင်ခြင်း
- 🔔 New Release: သီချင်းအသစ်တင်တိုင်း channel တွင် အလိုအလျောက် ကြေညာပေးခြင်း
- 🇲🇲 မြန်မာဘာသာဖြင့် UI အပြည့်အစုံ

## 🚀 Setup

### 1. Clone & Install
```bash
git clone https://github.com/YOUR_USERNAME/telegram-music-bot.git
cd telegram-music-bot
pip install -r requirements.txt
```

### 2. Create `.env` file
```env
BOT_TOKEN=YOUR_BOT_TOKEN
MONGODB_URI=mongodb+srv://USER:Pass@cluster.mongodb.net/
DB_NAME=music_bot
ADMIN_IDS=YOUR_TELEGRAM_ID
CHANNEL_ID=@your_music_channel
```

> 💡 `CHANNEL_ID` — သီချင်းအသစ်တင်တိုင်း notification ပို့မည့် channel (username သို့မဟုတ် numeric ID, ဥပမာ `-1001234567890`)။ Bot ကို channel ထဲ **admin** အနေနဲ့ ထည့်ထားဖို့ လိုပါသည်။ မသုံးချင်ရင် ဗလာထားခဲ့ပါ။

### 3. Get BOT_TOKEN
1. Telegram တွင် `@BotFather` သို့ သွားပါ
2. `/newbot` ဟု ရိုက်ပြီး bot အမည် / username သတ်မှတ်ပါ
3. ရလာသော token ကို `.env` တွင် ထည့်ပါ

### 4. Setup MongoDB Atlas
1. https://www.mongodb.com/atlas တွင် Free account ဖန်တီးပါ
2. New Cluster ဖန်တီးပြီး Database User သတ်မှတ်ပါ
3. Connection string (`mongodb+srv://...`) ရယူပါ
4. Network Access တွင် `0.0.0.0/0` ထည့်ပါ (Any IP)

### 5. Run Locally
```bash
python bot.py
```

## ☁️ Deploy to Render.com

### Option A: Blueprint (render.yaml)
1. Render Dashboard → **New** → **Blueprint**
2. Repository ကို ချိတ်ဆက်ပါ
3. Env variables များကို ထည့်ပါ (BOT_TOKEN, MONGODB_URI, ADMIN_IDS, CHANNEL_ID)
4. **Apply** → Bot run ပါလိမ့်မည်

### Option B: Manual
1. Render Dashboard → **New** → **Web Service**
2. Repository ချိတ်ဆက်ပါ
3. **Build Command:** `pip install -r requirements.txt`
4. **Start Command:** `python bot.py`
5. Env variables: `BOT_TOKEN`, `MONGODB_URI`, `DB_NAME`, `ADMIN_IDS`, `CHANNEL_ID`
6. **Create Web Service**

## 👍 GitHub Push
```bash
git init
git add .
git commit -m "Add Telegram Music Player Bot"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/telegram-music-bot.git
git push -u origin main
```

## 📝 Usage
- `/start` — စတင်ခြင်း
- `/admin` — Admin menu (Admin များသာ)
- Admin များသည် bot chat ထဲ သီချင်းဖိုင်တင်ပြီး Album ထဲ ထည့်နိုင်သည်

## 📢 Channel Bot (နည်းလမ်း ၂ မျိုး)

### နည်း ၁ — Channel ထဲ သီချင်းတင်ရုံနဲ့ အလိုအလျောက် သိမ်းခြင်း
1. Bot ကို မင်း channel ထဲ **Admin** အဖြစ် ထည့်ပါ (post permissions ရှိရန် လိုပါသည်)
2. Channel ထဲ music file (.mp3) တင်ပါ
3. Bot က file_id ကို အလိုအလျောက် database ထဲ သိမ်းပြီး channel မှာ "✅ သီချင်းအသစ် ရောက်ရှိပါပြီ!" ဟု ပြန်ကြားမည်
4. User များ bot ဆီ /start သို့မဟုတ် /albums ဖြင့် ဝင်ပြီး သီချင်းရှာဖွေ ရယူနိုင်ပါသည်

**Caption format (album သတ်မှတ်ရန်):**
```
Album Name | Song Title
```
ဥပမာ: `ချစ်သူအတွက် | ချစ်တယ်` — ဒါဆိုရင် "ချစ်သူအတွက်" album ထဲ သိမ်းပေးမည်။ `|` မပါရင် "ချန်နယ် စုစည်းမှု" ဆိုတဲ့ album ထဲ အလိုအလျောက် သိမ်းပါမည်။

### နည်း ၂ — Admin Panel (/admin) ကနေ ထည့်ခြင်း
- Bot chat ထဲ album / song ထည့်ပြီး `CHANNEL_ID` ရှိရင် channel မှာ အလိုအလျောက် ကြေညာပေးပါမည်

## 🛠 Tech Stack
- Python 3.10+
- aiogram 3.x
- MongoDB Atlas (motor)
- Render.com

## ⚠️ Note
- Audio files များကို Telegram server တွင် သိမ်းဆည်းပြီး `file_id` ကို MongoDB တွင် သိမ်းထားပါသည်။
- သို့သော် Telegram `file_id` များသည် bot token နှင့် ချိတ်ဆက်ထားသဖြင့် token ပြောင်းပါက file_id အဟောင်းများ သုံးမရနိုင်ပါ။
