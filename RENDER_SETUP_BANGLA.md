# 🚀 RENDER এ DEPLOY করার সম্পূর্ণ গাইড

## পর্যায় ০: প্রস্তুতি

### আপনার কাছে থাকা উচিত:

1. **GitHub Account** - https://github.com
2. **Render Account** - https://render.com (GitHub দিয়ে signup করতে পারবেন)
3. **Telegram Bot Token** - @BotFather থেকে
4. **Facebook Email & Password** - লগিন করার জন্য

---

## পর্যায় ১: GitHub এ Repository তৈরি করুন

### Step 1: GitHub তে নতুন Repository বানান

1. https://github.com নিতে যান
2. লগিন করুন
3. উপরে ডানদিকে **"+"** আইকন ক্লিক করুন
4. **"New repository"** ক্লিক করুন
5. নাম দিন: `facebook-tracker-bot`
6. Description: "Facebook profile activity tracker"
7. **"Create repository"** ক্লিক করুন

### Step 2: আপনার কম্পিউটারে Repository ক্লোন করুন

```bash
git clone https://github.com/YOUR_USERNAME/facebook-tracker-bot.git
cd facebook-tracker-bot
```

`YOUR_USERNAME` আপনার GitHub username দিয়ে বদলাবেন।

### Step 3: ডাউনলোড করা ফাইলগুলি কপি করুন

এই ফাইলগুলি `facebook-tracker-bot` ফোল্ডারে রাখুন:

```
facebook-tracker-bot/
├── app/
│   └── main.py
├── .env.example
├── .gitignore
├── Procfile
├── requirements.txt
├── README.md
└── RENDER_SETUP_BANGLA.md
```

### Step 4: Git এ কমিট এবং পুশ করুন

```bash
# সব ফাইল add করুন
git add .

# কমিট করুন
git commit -m "Facebook tracker bot - initial upload"

# পুশ করুন (GitHub এ আপলোড করুন)
git push origin main
```

---

## পর্যায় ২: Render এ সাইন আপ করুন

1. https://render.com এ যান
2. **"Sign up"** ক্লিক করুন
3. **"Continue with GitHub"** বেছে নিন
4. GitHub দিয়ে অথেন্টিকেট করুন
5. Render সাইটে নতুন অ্যাকাউন্ট তৈরি হবে

---

## পর্যায় ৩: Telegram Bot Token পান

### BotFather থেকে Token পান:

1. Telegram তে @BotFather এ যান
2. `/newbot` লাইখো এবং পাঠাও
3. Bot এর নাম লাইখো: `Facebook Activity Tracker`
4. Username লাইখো (ইউনিক হতে হবে): `my_fb_tracker_bot_123` 
   (আপনার নিজস্ব নাম দিন, শেষে নাম্বার যোগ করুন)
5. **Token কপি করো** - এটা দেখতে এমন হবে:
   ```
   1234567890:ABCdefGHIjklMNOpqrsTUvwxYZ-aBc1234567
   ```

---

## পর্যায় ৪: Render এ Web Service তৈরি করুন

### Step 1: নতুন Web Service তৈরি করুন

1. Render Dashboard এ যান: https://dashboard.render.com
2. উপরে ডানদিকে **"New +"** বাটন ক্লিক করুন
3. **"Web Service"** বেছে নিন

### Step 2: GitHub Repository কানেক্ট করুন

1. "Connect a repository" তে ক্লিক করুন
2. আপনার `facebook-tracker-bot` রেপোজিটরি খুঁজে বেছে নিন
3. **"Connect"** ক্লিক করুন

### Step 3: Service ডিটেইলস পূরণ করুন

ফর্মে এই মানগুলি পূরণ করুন:

| ফিল্ড | মান |
|------|-----|
| **Name** | `facebook-tracker-bot` |
| **Environment** | `Python 3` |
| **Region** | `Singapore` (বা কাছাকাছি) |
| **Branch** | `main` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `cd app && python main.py` |
| **Instance Type** | `Free` (বা Starter) |

### Step 4: Environment Variables যোগ করুন

**গুরুত্বপূর্ণ:** এই ভেরিয়েবলগুলি অবশ্যই যোগ করতে হবে!

নিচের বক্সে ক্লিক করুন: **"Advanced"** → **"Add Environment Variable"**

এই ৪টি ভেরিয়েবল যোগ করুন:

#### ১. TELEGRAM_BOT_TOKEN
- **Key:** `TELEGRAM_BOT_TOKEN`
- **Value:** `আপনার_বট_টোকেন_এখানে_পেস্ট_করুন`
  (BotFather থেকে কপি করা টোকেন)

#### ২. FB_EMAIL
- **Key:** `FB_EMAIL`
- **Value:** `আপনার_ফেসবুক_ইমেল@gmail.com`

#### ३. FB_PASSWORD
- **Key:** `FB_PASSWORD`
- **Value:** `আপনার_ফেসবুক_পাসওয়ার্ড`

#### ४. PORT
- **Key:** `PORT`
- **Value:** `10000`

### Step 5: Create Web Service ক্লিক করুন

নীল **"Create Web Service"** বাটন ক্লিক করুন।

---

## পর্যায় ৫: ডিপ্লয়মেন্ট অপেক্ষা করুন

এখন Render আপনার কোড বিল্ড করবে এবং স্টার্ট করবে।

### Logs দেখুন:

1. Render Dashboard এ আপনার service খুঁজুন
2. **"Logs"** ট্যাবে ক্লিক করুন
3. এই মেসেজ দেখুন:

```
2024-01-15 10:30:45 [INFO] 🔍 Facebook Activity Tracker v3.0 - STARTING
2024-01-15 10:30:46 [INFO] ✅ Facebook session authenticated
2024-01-15 10:30:47 [INFO] 🚀 Flask server on 0.0.0.0:10000
2024-01-15 10:30:48 [INFO] ================================================================================
```

যদি এই মেসেজ দেখেন, তাহলে **সফল** ✅

### আপনার Service URL খুঁজুন:

Render Dashboard এ, উপরে দেখবেন একটি URL:
```
https://facebook-tracker-bot.onrender.com/
```

এটি আপনার লাইভ সার্ভিসের ঠিকানা।

---

## পর্যায় ६: টেস্ট করুন

### Test 1: ওয়েব ব্রাউজার দিয়ে

ব্রাউজারে এই URL খুলুন:
```
https://facebook-tracker-bot.onrender.com/
```

আপনি একটি JSON দেখবেন:
```json
{
  "status": "running",
  "service": "Facebook Activity Tracker v3.0",
  "timestamp": "2024-01-15T10:30:48.123456",
  "fb_authenticated": true
}
```

### Test 2: Telegram Bot দিয়ে

1. Telegram খুলুন
2. আপনার বট খুঁজুন (username যা আপনি BotFather দিয়েছিলেন)
3. `/start` কমান্ড পাঠান
4. মেনু দেখতে পাবেন ✅

---

## পর্যায় ७: Telegram Bot ব্যবহার করুন

### প্রথম ফেসবুক প্রোফাইল যোগ করুন

#### অপশন ১: কমান্ড দিয়ে

Telegram চ্যাটে লাইখো:
```
/add https://facebook.com/username
```

(username এর জায়গায় সেই ব্যক্তির Facebook username দিন)

#### অপশন २: URL পাঠিয়ে

Telegram চ্যাটে সরাসরি Facebook URL পাঠান:
```
https://facebook.com/username
```

### কমান্ডগুলি জানুন:

```
/start        - মেনু দেখান
/list         - সব ট্র্যাক করা প্রোফাইল দেখান
/status ID    - প্রোফাইলের লাইভ স্ট্যাটাস দেখান
/stop ID      - ট্র্যাকিং বন্ধ করুন
/history ID   - কার্যকলাপের ইতিহাস দেখান
/help         - সাহায্য
```

---

## সম্ভাব্য সমস্যা এবং সমাধান

### সমস্যা ১: "ModuleNotFoundError"

**লক্ষণ:** Render logs এ `No module named 'flask'` দেখা যায়

**সমাধান:**
- `requirements.txt` ফাইল GitHub এ আছে কি চেক করুন
- GitHub এ পুশ করার সময় সব ফাইল যোগ করেছেন কি দেখুন
- `git add .` করে দোবারা পুশ করুন

### সমস্যা २: Facebook Login ব্যর্থ

**লক্ষণ:** Logs এ `❌ Login failed` দেখা যায়

**সমাধান:**
1. আপনার Facebook email এবং password সঠিক কি চেক করুন
2. আপনার Facebook account এ 2FA (Two-Factor Authentication) অন আছে কি?
   - যদি আছে, একটি দিনের জন্য অফ করুন
3. নতুন login attempt করার সময় Facebook এ email আসবে - "approve" করুন
4. Environment variables সঠিকভাবে set হয়েছে কি Render এ চেক করুন

### সমস্যা ३: Telegram Bot সাড়া দিচ্ছে না

**লক্ষণ:** /start পাঠালে কোনো প্রতিক্রিয়া নেই

**সমাধান:**
1. Token সঠিক কি চেক করুন (BotFather থেকে কপি করা)
2. Render logs এ "Telegram bot polling started" আছে কি দেখুন
3. কয়েক সেকেন্ড অপেক্ষা করে দোবারা চেষ্টা করুন
4. Bot কে /start এর পরিবর্তে সিম্পল মেসেজ পাঠান

### সমস্যা ४: Database error

**লক্ষণ:** "database disk image malformed" এর মত ত্রুটি

**সমাধান:**
- Render free plan এ database redeploy হলে reset হয়ে যায়
- এটি স্বাভাবিক, নতুন করে প্রোফাইল যোগ করুন

---

## Render Logs দেখার পদ্ধতি

### Live Logs দেখুন:

1. https://dashboard.render.com এ যান
2. আপনার `facebook-tracker-bot` service ক্লিক করুন
3. নিচে **"Logs"** ট্যাব দেখবেন - ক্লিক করুন
4. Real-time logs দেখা যাবে

### Errors খুঁজুন:

Logs এ কোনো লাল রঙের মেসেজ থাকলে সেটা error।

---

## সার্ভিস রিস্টার্ট করা

যদি সমস্যা হয় এবং সার্ভিস ঠিক না হয়:

1. Dashboard এ service ক্লিক করুন
2. উপরে ডানদিকে **"Manual Deploy"** → **"Deploy latest commit"** ক্লিক করুন
3. নতুন করে build এবং start হবে

---

## GitHub থেকে আপডেট করা

যদি আপনি কোড পরিবর্তন করেন:

```bash
# আপনার কম্পিউটারে
git add .
git commit -m "updated message"
git push origin main

# Render automatically redeploy করবে
# (Render dashboard এ logs দেখুন)
```

---

## দীর্ঘমেয়াদী টিপস

### সাপ্তাহিক Backup নিন:

```bash
cp facebook_tracker.db facebook_tracker.backup.db
```

এবং এই ফাইল safe জায়গায় রাখুন।

### Monitor Render Metrics:

Render Dashboard এ **"Metrics"** ট্যাব থেকে CPU এবং Memory দেখতে পারবেন।

### Logging চেক করুন:

নিয়মিত logs দেখুন যাতে errors ধরতে পারেন।

---

## ✅ চেকলিস্ট

- [ ] GitHub account তৈরি করেছি
- [ ] facebook-tracker-bot repository তৈরি করেছি
- [ ] সব ফাইল GitHub এ আপলোড করেছি
- [ ] Telegram Bot Token পেয়েছি
- [ ] Render account তৈরি করেছি
- [ ] Render এ Web Service তৈরি করেছি
- [ ] সব Environment Variables set করেছি
- [ ] Deployment সফল হয়েছে (logs দেখে নিশ্চিত)
- [ ] Telegram Bot কে /start পাঠিয়ে টেস্ট করেছি
- [ ] Web URL ব্রাউজারে open করে টেস্ট করেছি

---

## 🎉 সাফল্য!

যদি সব step অনুসরণ করেন, আপনার Facebook Tracker bot **24/7 লাইভ চলবে** Render এ!

**কোনো সমস্যা হলে logs দেখুন এবং সেই error message নিয়ে troubleshoot করুন।**

---

Last Updated: 2024

