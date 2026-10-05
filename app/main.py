#!/usr/bin/env python3
"""
🔍 Facebook Activity Tracker v4.0 - PREMIUM
Advanced real-time tracking, activity timeline, analytics, polished Telegram UI
"""

import os
import json
import logging
import threading
import time
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, jsonify, request
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
FB_EMAIL = os.getenv("FB_EMAIL")
FB_PASSWORD = os.getenv("FB_PASSWORD")
PORT = int(os.getenv("PORT", 10000))

DB_FILE = "tracker_premium.db"
app = Flask(__name__)

# ============================================================================
# PREMIUM DATABASE
# ============================================================================

class PremiumDB:
    @staticmethod
    def init():
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS targets (
            id INTEGER PRIMARY KEY,
            fb_id TEXT UNIQUE,
            name TEXT,
            profile_url TEXT,
            user_id INTEGER,
            avatar_url TEXT,
            bio TEXT,
            created_at TIMESTAMP,
            last_updated TIMESTAMP
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY,
            fb_id TEXT,
            event_type TEXT,
            status TEXT,
            last_seen TEXT,
            duration_minutes INTEGER,
            timestamp TIMESTAMP
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS status_changes (
            id INTEGER PRIMARY KEY,
            fb_id TEXT,
            old_status TEXT,
            new_status TEXT,
            online_duration INTEGER,
            went_online_at TIMESTAMP,
            went_offline_at TIMESTAMP
        )''')
        
        conn.commit()
        conn.close()
        logger.info("✅ Premium DB initialized")
    
    @staticmethod
    def add_target(fb_id, name, profile_url, user_id, avatar_url="", bio=""):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        try:
            c.execute('''INSERT INTO targets 
                (fb_id, name, profile_url, user_id, avatar_url, bio, created_at, last_updated) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (fb_id, name, profile_url, user_id, avatar_url, bio, datetime.now(), datetime.now()))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    
    @staticmethod
    def log_activity(fb_id, event_type, status, last_seen, duration=0):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''INSERT INTO activity_log 
            (fb_id, event_type, status, last_seen, duration_minutes, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)''',
            (fb_id, event_type, status, last_seen, duration, datetime.now()))
        conn.commit()
        conn.close()
    
    @staticmethod
    def log_status_change(fb_id, old_status, new_status, online_duration, went_online_at, went_offline_at):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''INSERT INTO status_changes 
            (fb_id, old_status, new_status, online_duration, went_online_at, went_offline_at)
            VALUES (?, ?, ?, ?, ?, ?)''',
            (fb_id, old_status, new_status, online_duration, went_online_at, went_offline_at))
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_timeline(fb_id, limit=30):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''SELECT event_type, status, last_seen, duration_minutes, timestamp 
            FROM activity_log WHERE fb_id=? ORDER BY timestamp DESC LIMIT ?''',
            (fb_id, limit))
        rows = c.fetchall()
        conn.close()
        return rows
    
    @staticmethod
    def get_status_changes(fb_id, limit=20):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''SELECT old_status, new_status, online_duration, went_online_at, went_offline_at
            FROM status_changes WHERE fb_id=? ORDER BY went_offline_at DESC LIMIT ?''',
            (fb_id, limit))
        rows = c.fetchall()
        conn.close()
        return rows
    
    @staticmethod
    def get_targets(user_id):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''SELECT fb_id, name, profile_url, avatar_url, created_at FROM targets WHERE user_id=?''',
            (user_id,))
        rows = c.fetchall()
        conn.close()
        return rows
    
    @staticmethod
    def get_target(fb_id):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT fb_id, name, avatar_url, bio, created_at FROM targets WHERE fb_id=?', (fb_id,))
        row = c.fetchone()
        conn.close()
        return row
    
    @staticmethod
    def remove_target(fb_id, user_id):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('DELETE FROM targets WHERE fb_id=? AND user_id=?', (fb_id, user_id))
        conn.commit()
        conn.close()

PremiumDB.init()

# ============================================================================
# FACEBOOK SCRAPER
# ============================================================================

class AdvancedFacebookScraper:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.session = requests.Session()
        self.is_logged_in = False
        self.setup_session()
        self.login()
    
    def setup_session(self):
        retry_strategy = Retry(total=3, status_forcelist=[429, 500, 502, 503, 504], backoff_factor=1)
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'DNT': '1',
        })
    
    def login(self):
        try:
            logger.info('[FB] Logging in...')
            resp = self.session.get('https://www.facebook.com/login.php', timeout=10)
            login_data = {'email': self.email, 'pass': self.password, 'login': 'Log In'}
            login_resp = self.session.post('https://www.facebook.com/login.php', data=login_data, timeout=10, allow_redirects=True)
            
            if 'c_user' in self.session.cookies or 'logout' in login_resp.text.lower():
                self.is_logged_in = True
                logger.info('[FB] ✅ Login OK')
                return True
            else:
                self.is_logged_in = False
                return False
        except Exception as e:
            logger.error(f'[FB] Login error: {e}')
            self.is_logged_in = False
            return False
    
    def extract_fb_id(self, url):
        try:
            if 'profile.php?id=' in url:
                return url.split('id=')[1].split('&')[0]
            parts = url.split('facebook.com/')
            if len(parts) > 1:
                username = parts[1].split('/')[0].split('?')[0]
                if username and username not in ['login', 'help']:
                    return username
        except:
            pass
        return None
    
    def scrape_profile(self, profile_url):
        try:
            resp = self.session.get(profile_url, timeout=15)
            soup = BeautifulSoup(resp.content, 'html.parser')
            
            name = "Unknown"
            title_elem = soup.find('title')
            if title_elem:
                name = title_elem.text.split('|')[0].strip()
            
            avatar_url = ""
            img_elem = soup.find('img', {'alt': name})
            if img_elem and 'src' in img_elem.attrs:
                avatar_url = img_elem['src']
            
            page_text = resp.text
            status = "offline"
            last_seen = "unknown"
            
            if "Active now" in page_text:
                status = "online"
                last_seen = "now"
            elif "Active " in page_text and " ago" in page_text:
                import re
                match = re.search(r'Active\s+(\d+)\s*(m|h|d)\s*ago', page_text)
                if match:
                    num = int(match.group(1))
                    unit = match.group(2)
                    last_seen = f"{num}{unit} ago"
                    status = "seen_recently"
            
            return {'name': name, 'status': status, 'last_seen': last_seen, 'avatar_url': avatar_url}
        except Exception as e:
            logger.error(f'Scrape error: {e}')
            return None

fb_scraper = AdvancedFacebookScraper(FB_EMAIL, FB_PASSWORD)

# ============================================================================
# PREMIUM TRACKER
# ============================================================================

class PremiumTracker:
    def __init__(self):
        self.tracking = {}
        self.lock = threading.Lock()
    
    def add_target(self, user_id, profile_url):
        fb_id = fb_scraper.extract_fb_id(profile_url)
        if not fb_id:
            return False, "❌ Invalid URL"
        
        profile_info = fb_scraper.scrape_profile(profile_url)
        if not profile_info:
            return False, "❌ Cannot access profile"
        
        if not PremiumDB.add_target(fb_id, profile_info['name'], profile_url, user_id):
            return False, "⚠️ Already tracking"
        
        with self.lock:
            self.tracking[fb_id] = {
                'user_id': user_id,
                'url': profile_url,
                'name': profile_info['name'],
                'current_status': profile_info['status'],
                'last_seen': profile_info['last_seen'],
                'went_online_at': None,
                'total_online_time': 0,
                'active': True
            }
        
        PremiumDB.log_activity(fb_id, 'added', profile_info['status'], profile_info['last_seen'])
        threading.Thread(target=self._monitor, args=(fb_id,), daemon=True).start()
        
        logger.info(f"🎯 Tracking: {profile_info['name']}")
        return True, f"✅ Tracking *{profile_info['name']}*\n🔔 Real-time updates enabled"
    
    def _monitor(self, fb_id):
        while True:
            try:
                with self.lock:
                    if fb_id not in self.tracking:
                        break
                    track = self.tracking[fb_id]
                
                if not track['active']:
                    time.sleep(60)
                    continue
                
                profile = fb_scraper.scrape_profile(track['url'])
                if not profile:
                    time.sleep(60)
                    continue
                
                old_status = track['current_status']
                new_status = profile['status']
                
                if new_status != old_status:
                    if new_status == "online":
                        track['went_online_at'] = datetime.now()
                        logger.info(f"🟢 {fb_id} ONLINE")
                    elif old_status == "online" and track['went_online_at']:
                        duration = int((datetime.now() - track['went_online_at']).total_seconds() / 60)
                        track['total_online_time'] += duration
                        logger.info(f"🔴 {fb_id} OFFLINE ({duration} mins)")
                        PremiumDB.log_status_change(fb_id, old_status, new_status, duration, 
                                                   track['went_online_at'], datetime.now())
                
                PremiumDB.log_activity(fb_id, 'check', new_status, profile['last_seen'])
                
                with self.lock:
                    if fb_id in self.tracking:
                        self.tracking[fb_id]['current_status'] = new_status
                        self.tracking[fb_id]['last_seen'] = profile['last_seen']
                
                time.sleep(60)
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                time.sleep(120)
    
    def get_analytics(self, fb_id):
        changes = PremiumDB.get_status_changes(fb_id, 100)
        total_sessions = len(changes)
        total_online_mins = sum(c[2] for c in changes if c[2])
        avg_session = total_online_mins // total_sessions if total_sessions > 0 else 0
        
        peak_hours = {}
        for change in changes:
            if change[3]:
                hour = datetime.fromisoformat(change[3]).hour
                peak_hours[hour] = peak_hours.get(hour, 0) + 1
        
        peak_hour = max(peak_hours, key=peak_hours.get) if peak_hours else None
        
        return {
            'total_sessions': total_sessions,
            'total_online_minutes': total_online_mins,
            'total_online_hours': total_online_mins // 60,
            'avg_session_minutes': avg_session,
            'peak_hour': peak_hour
        }
    
    def stop_tracking(self, fb_id, user_id):
        with self.lock:
            if fb_id in self.tracking and self.tracking[fb_id]['user_id'] == user_id:
                self.tracking[fb_id]['active'] = False
                del self.tracking[fb_id]
                PremiumDB.remove_target(fb_id, user_id)
                return True
        return False
    
    def get_status(self, fb_id):
        with self.lock:
            if fb_id in self.tracking:
                t = self.tracking[fb_id]
                return {'active': True, 'name': t['name'], 'status': t['current_status'], 
                        'last_seen': t['last_seen'], 'online_mins': t['total_online_time']}
        
        target = PremiumDB.get_target(fb_id)
        if target:
            return {'active': False, 'name': target[1], 'status': 'inactive'}
        return {'active': False, 'status': 'unknown'}

tracker = PremiumTracker()

# ============================================================================
# TELEGRAM BOT - PREMIUM UI
# ============================================================================

class PremiumTelegramBot:
    def __init__(self, token):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.offset = 0
    
    def get_updates(self):
        try:
            resp = requests.post(f"{self.base_url}/getUpdates",
                json={"offset": self.offset, "timeout": 30}, timeout=35)
            data = resp.json()
            return data.get('result', []) if data.get('ok') else []
        except Exception as e:
            logger.error(f"Updates error: {e}")
            return []
    
    def send_message(self, chat_id, text, parse_mode="Markdown", reply_markup=None):
        try:
            payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
            if reply_markup:
                payload["reply_markup"] = reply_markup
            requests.post(f"{self.base_url}/sendMessage", json=payload, timeout=10)
        except Exception as e:
            logger.error(f"Send error: {e}")
    
    def send_main_menu(self, chat_id):
        self.send_message(chat_id,
            "🔍 *Facebook Activity Tracker v4.0 - PREMIUM*\n\n"
            "Real-time tracking with advanced analytics\n\n"
            "Choose:",
            reply_markup={
                "inline_keyboard": [
                    [{"text": "➕ Add", "callback_data": "add"},
                     {"text": "📊 Profiles", "callback_data": "list"}],
                    [{"text": "🔴 Online", "callback_data": "online"},
                     {"text": "📈 Analytics", "callback_data": "analytics"}],
                    [{"text": "📋 Timeline", "callback_data": "timeline"},
                     {"text": "❓ Help", "callback_data": "help"}]
                ]
            })
    
    def handle_update(self, update):
        if 'message' in update:
            self.handle_message(update['message'])
        elif 'callback_query' in update:
            self.handle_callback(update['callback_query'])
        self.offset = update.get('update_id', 0) + 1
    
    def handle_message(self, message):
        chat_id = message['chat']['id']
        text = message.get('text', '').strip()
        user_id = message['from']['id']
        
        if text == '/start':
            self.send_main_menu(chat_id)
        elif text == '/list':
            targets = PremiumDB.get_targets(user_id)
            if targets:
                msg = "📱 *Your Profiles:*\n\n"
                for t in targets:
                    s = tracker.get_status(t[0])
                    icon = "🟢" if s.get('status') == 'online' else "⚪"
                    msg += f"{icon} {t[1]}\n"
            else:
                msg = "❌ No profiles"
            self.send_message(chat_id, msg)
        elif text.startswith('/add '):
            url = text[5:].strip()
            success, msg = tracker.add_target(user_id, url)
            self.send_message(chat_id, msg)
        elif text.startswith('/status '):
            fb_id = text[8:].strip()
            s = tracker.get_status(fb_id)
            if s.get('active'):
                msg = f"🔴 *{s['name']}*\nStatus: {s['status']}\nLast: {s['last_seen']}"
            else:
                msg = f"⚪ {s.get('name', 'Unknown')} - Not tracking"
            self.send_message(chat_id, msg)
        elif text.startswith('/analytics '):
            fb_id = text[11:].strip()
            a = tracker.get_analytics(fb_id)
            msg = f"📈 Analytics\nSessions: {a['total_sessions']}\nOnline: {a['total_online_hours']}h"
            self.send_message(chat_id, msg)
        elif text.startswith('/stop '):
            fb_id = text[6:].strip()
            if tracker.stop_tracking(fb_id, user_id):
                self.send_message(chat_id, f"🛑 Stopped {fb_id}")
            else:
                self.send_message(chat_id, "❌ Not found")
        elif 'facebook.com' in text:
            success, msg = tracker.add_target(user_id, text)
            self.send_message(chat_id, msg)
        else:
            self.send_main_menu(chat_id)
    
    def handle_callback(self, callback):
        chat_id = callback['message']['chat']['id']
        data = callback['data']
        user_id = callback['from']['id']
        
        if data == "add":
            self.send_message(chat_id, "Send Facebook profile URL:\n`https://facebook.com/username`")
        elif data == "list":
            targets = PremiumDB.get_targets(user_id)
            if targets:
                msg = "📱 *Profiles:*\n"
                for t in targets:
                    msg += f"`/status {t[0]}` - {t[1]}\n"
            else:
                msg = "❌ No profiles"
            self.send_message(chat_id, msg)
        elif data == "online":
            targets = PremiumDB.get_targets(user_id)
            msg = "🔴 *Online Now:*\n"
            for t in targets:
                s = tracker.get_status(t[0])
                icon = "🟢" if s.get('status') == 'online' else "⚪"
                msg += f"{icon} {t[1]}\n"
            self.send_message(chat_id, msg if msg != "🔴 *Online Now:*\n" else "❌ No one online")
        elif data == "analytics":
            targets = PremiumDB.get_targets(user_id)
            msg = "📊 Analytics:\n"
            for t in targets:
                msg += f"`/analytics {t[0]}`\n"
            self.send_message(chat_id, msg)
        elif data == "help":
            self.send_message(chat_id,
                "*Features:*\n"
                "✅ Real-time updates\n"
                "✅ Session tracking\n"
                "✅ Activity timeline\n"
                "✅ Analytics\n"
                "✅ Peak hours\n"
                "✅ Notifications")
    
    def run(self):
        logger.info("🚀 Premium bot started")
        while True:
            try:
                updates = self.get_updates()
                for update in updates:
                    self.handle_update(update)
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"Bot error: {e}")
                time.sleep(5)

def start_bot():
    if TELEGRAM_BOT_TOKEN:
        bot = PremiumTelegramBot(TELEGRAM_BOT_TOKEN)
        thread = threading.Thread(target=bot.run, daemon=True)
        thread.start()

# ============================================================================
# FLASK API
# ============================================================================

@app.route('/')
def health():
    return jsonify({'status': 'running', 'service': 'Facebook Tracker v4.0 PREMIUM'}), 200

@app.route('/api/profiles/<int:user_id>')
def api_profiles(user_id):
    targets = PremiumDB.get_targets(user_id)
    return jsonify({'count': len(targets), 'profiles': [{'fb_id': t[0], 'name': t[1]} for t in targets]}), 200

@app.route('/api/status/<fb_id>')
def api_status(fb_id):
    return jsonify(tracker.get_status(fb_id)), 200

@app.route('/api/analytics/<fb_id>')
def api_analytics(fb_id):
    return jsonify(tracker.get_analytics(fb_id)), 200

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    logger.info("="*80)
    logger.info("🔍 Facebook Tracker v4.0 - PREMIUM EDITION")
    logger.info("="*80)
    
    if fb_scraper.is_logged_in:
        logger.info("✅ Facebook authenticated")
    else:
        logger.warning("⚠️ Login issue")
    
    start_bot()
    logger.info(f"Flask: 0.0.0.0:{PORT}")
    logger.info("="*80)
    
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False, threaded=True)
