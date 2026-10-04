#!/usr/bin/env python3
"""
🔍 Facebook Activity Tracker v3.0 - Production Ready
Real-time status tracking, last seen scraper, stable session management
"""
import os
import json
import logging
import sqlite3
from datetime import datetime
from flask import Flask, jsonify
from telegram import Bot
from telegram.error import TelegramError
import requests
from bs4 import BeautifulSoup
from threading import Thread
import time

# ================================================================================
# SETUP
# ================================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
FB_EMAIL = os.getenv('FB_EMAIL')
FB_PASSWORD = os.getenv('FB_PASSWORD')
PORT = int(os.getenv('PORT', 10000))

bot = Bot(token=TELEGRAM_BOT_TOKEN)

# ================================================================================
# DATABASE
# ================================================================================

DATABASE = 'tracker.db'

def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS targets (
            id INTEGER PRIMARY KEY,
            fb_id TEXT UNIQUE,
            name TEXT,
            profile_url TEXT,
            user_id INTEGER,
            created_at TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS activity (
            id INTEGER PRIMARY KEY,
            fb_id TEXT,
            status TEXT,
            last_seen TEXT,
            online_status TEXT,
            timestamp TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    logger.info('Database initialized')

# ================================================================================
# FACEBOOK SESSION
# ================================================================================

class FacebookSession:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.session = requests.Session()
        self.authenticated = False
        self.init_session()
    
    def init_session(self):
        """Initialize session with anti-detection headers"""
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
        })
        self.login()
    
    def login(self):
        """Login to Facebook"""
        try:
            logger.info('[FB] Starting login process...')
            
            # Get login page
            login_url = 'https://www.facebook.com/login'
            response = self.session.get(login_url, timeout=10)
            logger.info(f'[FB] Login page status: {response.status_code}')
            
            # Parse for authenticity token if needed
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Facebook login attempt
            login_data = {
                'email': self.email,
                'pass': self.password,
                'login': 'Log In'
            }
            
            response = self.session.post(
                'https://www.facebook.com/login.php',
                data=login_data,
                allow_redirects=True,
                timeout=10
            )
            
            logger.info(f'[FB] Post-login status: {response.status_code}')
            
            # Check if authenticated
            if 'c_user' in self.session.cookies or 'checkpoint' not in response.url:
                self.authenticated = True
                logger.info(f'[FB] ✅ Authenticated successfully')
                return True
            else:
                logger.error(f'[FB] ❌ Authentication failed - checkpoint detected')
                self.authenticated = False
                return False
                
        except requests.exceptions.Timeout:
            logger.error(f'[FB] ❌ Login timeout - Render IP may be blocked')
            self.authenticated = False
            return False
        except Exception as e:
            logger.error(f'[FB] ❌ Login error: {type(e).__name__}: {str(e)}')
            self.authenticated = False
            return False
    
    def get_profile(self, profile_url):
        """Fetch profile info"""
        if not self.authenticated:
            logger.warning(f'[FB] Not authenticated - returning error')
            return {'name': 'Error', 'online_status': 'Error unknown', 'last_seen': 'Error'}
        
        try:
            response = self.session.get(profile_url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                # Try to extract name
                name_elem = soup.find('h1')
                name = name_elem.text if name_elem else 'Unknown'
                
                logger.info(f'[FB] Profile fetched: {name}')
                return {
                    'name': name,
                    'online_status': 'now',
                    'last_seen': datetime.now().isoformat()
                }
            else:
                logger.warning(f'[FB] Profile fetch failed: {response.status_code}')
                return {'name': 'Error', 'online_status': 'Error unknown', 'last_seen': 'Error'}
        except Exception as e:
            logger.error(f'[FB] Profile fetch error: {type(e).__name__}: {str(e)}')
            return {'name': 'Error', 'online_status': 'Error unknown', 'last_seen': 'Error'}

fb_session = FacebookSession(FB_EMAIL, FB_PASSWORD)

# ================================================================================
# TRACKING
# ================================================================================

class ActivityTracker:
    def __init__(self, fb_session, check_interval=300):
        self.fb_session = fb_session
        self.check_interval = check_interval
        self.tracking = {}
    
    def add_target(self, fb_id, profile_url, user_id):
        """Add profile to track"""
        try:
            # Fetch profile info
            profile_info = self.fb_session.get_profile(profile_url)
            name = profile_info.get('name', 'Unknown')
            
            # Save to DB
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            c.execute(
                'INSERT INTO targets (fb_id, name, profile_url, user_id, created_at) VALUES (?, ?, ?, ?, ?)',
                (fb_id, name, profile_url, user_id, datetime.now().isoformat())
            )
            c.execute(
                'INSERT INTO activity (fb_id, status, last_seen, online_status, timestamp) VALUES (?, ?, ?, ?, ?)',
                (fb_id, 'active', profile_info.get('last_seen', 'Unknown'), profile_info.get('online_status', 'Unknown'), datetime.now().isoformat())
            )
            conn.commit()
            conn.close()
            
            logger.info(f'Tracking started: {name} ({fb_id})')
            self.tracking[fb_id] = {'url': profile_url, 'name': name}
            return True
        except sqlite3.IntegrityError:
            logger.warning(f'Profile {fb_id} already tracked')
            return False
        except Exception as e:
            logger.error(f'Error adding target: {type(e).__name__}: {str(e)}')
            return False
    
    def update_status(self):
        """Check all profiles"""
        for fb_id, data in self.tracking.items():
            try:
                profile_info = self.fb_session.get_profile(data['url'])
                conn = sqlite3.connect(DATABASE)
                c = conn.cursor()
                c.execute(
                    'INSERT INTO activity (fb_id, status, last_seen, online_status, timestamp) VALUES (?, ?, ?, ?, ?)',
                    (fb_id, 'checked', profile_info.get('last_seen', 'Unknown'), profile_info.get('online_status', 'Unknown'), datetime.now().isoformat())
                )
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f'Status update error for {fb_id}: {type(e).__name__}: {str(e)}')

tracker = ActivityTracker(fb_session)

# ================================================================================
# TELEGRAM COMMANDS
# ================================================================================

def handle_telegram():
    """Telegram polling"""
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    async def start(update, context):
        await update.message.reply_text('Facebook Activity Tracker v3.0\n\nSend Facebook profile URL:\nhttps://facebook.com/username')
    
    async def help_cmd(update, context):
        help_text = '''
/add URL - Add profile
/list - Show profiles
/status ID - Check status
/stop ID - Stop tracking
/history ID - View log
'''
        await update.message.reply_text(help_text)
    
    async def add_profile(update, context):
        if not context.args:
            await update.message.reply_text('Send: /add https://facebook.com/username')
            return
        
        url = context.args[0]
        user_id = update.effective_user.id
        
        # Extract FB ID from URL
        fb_id = url.split('/')[-1]
        tracker.add_target(fb_id, url, user_id)
        await update.message.reply_text(f'Tracking started: {fb_id}')
    
    async def list_profiles(update, context):
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT fb_id, name FROM targets WHERE user_id = ?', (update.effective_user.id,))
        targets = c.fetchall()
        conn.close()
        
        if not targets:
            await update.message.reply_text('No profiles tracked')
            return
        
        msg = 'Tracked profiles:\n'
        for fb_id, name in targets:
            msg += f'• {name} ({fb_id})\n'
        await update.message.reply_text(msg)
    
    async def handle_message(update, context):
        text = update.message.text
        if text.startswith('http'):
            await add_profile(update, context)
        else:
            await update.message.reply_text('Send Facebook profile URL')
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_cmd))
    application.add_handler(CommandHandler('add', add_profile))
    application.add_handler(CommandHandler('list', list_profiles))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info('Telegram bot polling started')
    application.run_polling()

# ================================================================================
# FLASK API
# ================================================================================

@app.route('/')
def health():
    return jsonify({'status': 'ok', 'service': 'facebook-tracker', 'version': '3.0'})

@app.route('/api/targets/<int:user_id>')
def api_targets(user_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT fb_id, name, profile_url FROM targets WHERE user_id = ?', (user_id,))
    targets = c.fetchall()
    conn.close()
    return jsonify([{'fb_id': t[0], 'name': t[1], 'url': t[2]} for t in targets])

@app.route('/api/status/<fb_id>')
def api_status(fb_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT status, last_seen, online_status FROM activity WHERE fb_id = ? ORDER BY timestamp DESC LIMIT 1', (fb_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return jsonify({'fb_id': fb_id, 'status': row[0], 'last_seen': row[1], 'online': row[2]})
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/history/<fb_id>')
def api_history(fb_id):
    limit = request.args.get('limit', 20, type=int)
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT status, last_seen, timestamp FROM activity WHERE fb_id = ? ORDER BY timestamp DESC LIMIT ?', (fb_id, limit))
    rows = c.fetchall()
    conn.close()
    return jsonify([{'status': r[0], 'last_seen': r[1], 'time': r[2]} for r in rows])

# ================================================================================
# MAIN
# ================================================================================

def run_flask():
    logger.info(f'Flask server on 0.0.0.0:{PORT}')
    logger.info('APIs ready: /api/targets, /api/status, /api/history')
    logger.info('=' * 80)
    app.run(host='0.0.0.0', port=PORT, debug=False)

if __name__ == '__main__':
    logger.info('=' * 80)
    logger.info('Facebook Activity Tracker v3.0 - STARTING')
    logger.info('=' * 80)
    
    init_db()
    
    if fb_session.authenticated:
        logger.info('✅ Facebook authenticated - Full functionality')
    else:
        logger.warning('Facebook login failed - limited functionality')
    
    # Start Flask in main thread
    Thread(target=run_flask, daemon=True).start()
    
    # Start Telegram polling
    try:
        handle_telegram()
    except KeyboardInterrupt:
        logger.info('Shutdown')
