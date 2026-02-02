#!/usr/bin/env python3
"""
Remote Access Server - Enhanced with auto-removal of temporary admin
"""

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials  
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict
import asyncio
import uvicorn
import hashlib
import secrets
import jwt
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import sqlite3
import socket
import struct
import json
from contextlib import asynccontextmanager

# Configuration
SECRET_KEY = secrets.token_urlsafe(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440

# Database initialization with is_temporary field
def init_db():
    conn = sqlite3.connect('remote_access.db')
    cursor = conn.cursor()
    
    # Add is_temporary column if upgrading existing database
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN is_temporary BOOLEAN DEFAULT 0')
    except:
        pass
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'tech',
            is_active BOOLEAN DEFAULT 1,
            max_sessions INTEGER DEFAULT 10,
            is_temporary BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_code TEXT UNIQUE NOT NULL,
            tech_user_id INTEGER NOT NULL,
            customer_name TEXT,
            customer_email TEXT,
            status TEXT DEFAULT 'pending',
            udp_port INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            connected_at TIMESTAMP,
            disconnected_at TIMESTAMP,
            FOREIGN KEY (tech_user_id) REFERENCES users(id)
        )
    ''')
    
    # SMTP Configuration table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS smtp_config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            smtp_host TEXT NOT NULL,
            smtp_port INTEGER NOT NULL,
            security_type TEXT NOT NULL,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            from_email TEXT NOT NULL,
            require_auth BOOLEAN DEFAULT 1,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Check if we need to create default admin
    cursor.execute('SELECT COUNT(*) FROM users WHERE is_temporary = 0')
    real_admin_count = cursor.fetchone()[0]
    
    if real_admin_count == 0:
        # Only create if no temporary admin exists either
        cursor.execute('SELECT COUNT(*) FROM users WHERE is_temporary = 1')
        if cursor.fetchone()[0] == 0:
            temp_password = 'Setup' + secrets.token_urlsafe(8)
            admin_hash = hashlib.sha256(temp_password.encode()).hexdigest()
            cursor.execute('''
                INSERT INTO users (email, password_hash, full_name, role, max_sessions, is_temporary)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', ('admin@example.com', admin_hash, 'Setup Admin', 'admin', 50, 1))
            
            print("\n" + "="*80)
            print("⚠️  FIRST TIME SETUP - TEMPORARY CREDENTIALS")
            print("="*80)
            print(f"Email:    admin@example.com")
            print(f"Password: {temp_password}")
            print("\n📌 These credentials will be automatically removed when you create")
            print("   your first permanent admin account!")
            print("="*80 + "\n")
    
    conn.commit()
    conn.close()

# Pydantic models (same as before, adding UserUpdate)
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str
    role: str = Field(default='tech', pattern='^(admin|tech)$')
    max_sessions: int = Field(default=10, ge=1, le=50)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    max_sessions: int
    is_active: bool
    is_temporary: bool
    created_at: str

class UserUpdate(BaseModel):
    is_active: Optional[bool] = None
    max_sessions: Optional[int] = Field(None, ge=1, le=50)

class SMTPConfig(BaseModel):
    smtp_host: str
    smtp_port: int = Field(..., ge=1, le=65535)
    security_type: str = Field(..., pattern='^(TLS|SSL|NONE)$')
    username: str
    password: str
    from_email: EmailStr
    require_auth: bool = True

class SessionCreate(BaseModel):
    customer_name: Optional[str] = None
    customer_email: Optional[EmailStr] = None

class SessionResponse(BaseModel):
    id: int
    session_code: str
    tech_user_id: int
    customer_name: Optional[str]
    customer_email: Optional[str]
    status: str
    udp_port: Optional[int]
    created_at: str

# UDP Session Manager
class UDPSessionManager:
    def __init__(self):
        self.sessions: Dict[str, socket.socket] = {}
        self.port_range_start = 50000
        self.port_range_end = 60000
        self.used_ports = set()
    
    def allocate_port(self) -> int:
        for port in range(self.port_range_start, self.port_range_end):
            if port not in self.used_ports:
                self.used_ports.add(port)
                return port
        raise Exception("No available UDP ports")
    
    def release_port(self, port: int):
        self.used_ports.discard(port)
    
    async def create_udp_socket(self, session_code: str) -> int:
        port = self.allocate_port()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('0.0.0.0', port))
        sock.setblocking(False)
        self.sessions[session_code] = sock
        return port
    
    def close_session(self, session_code: str, port: int):
        if session_code in self.sessions:
            self.sessions[session_code].close()
            del self.sessions[session_code]
        self.release_port(port)

udp_manager = UDPSessionManager()
security = HTTPBearer()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="Remote Access Server API",
    description="TeamViewer-like remote access system",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    conn = sqlite3.connect('remote_access.db')
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, password_hash: str) -> bool:
    return hash_password(password) == password_hash

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def generate_session_code() -> str:
    return ''.join([str(secrets.randbelow(10)) for _ in range(9)])

def send_email(to_email: str, subject: str, body: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM smtp_config WHERE id = 1')
    config = cursor.fetchone()
    conn.close()
    
    if not config:
        raise HTTPException(status_code=400, detail="SMTP not configured")
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = config['from_email']
    msg['To'] = to_email
    
    html_part = MIMEText(body, 'html')
    msg.attach(html_part)
    
    try:
        if config['security_type'] == 'SSL':
            server = smtplib.SMTP_SSL(config['smtp_host'], config['smtp_port'])
        else:
            server = smtplib.SMTP(config['smtp_host'], config['smtp_port'])
            if config['security_type'] == 'TLS':
                server.starttls()
        
        if config['require_auth']:
            server.login(config['username'], config['password'])
        
        server.send_message(msg)
        server.quit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

# API Endpoints

@app.post("/api/auth/login")
async def login(user_data: UserLogin):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE email = ? AND is_active = 1', (user_data.email,))
    user = cursor.fetchone()
    conn.close()
    
    if not user or not verify_password(user_data.password, user['password_hash']):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token({
        "user_id": user['id'],
        "email": user['email'],
        "role": user['role']
    })
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user['id'],
            "email": user['email'],
            "full_name": user['full_name'],
            "role": user['role'],
            "is_temporary": bool(user['is_temporary'])
        }
    }

@app.post("/api/users", response_model=UserResponse)
async def create_user(user: UserCreate, current_user: dict = Depends(verify_token)):
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        password_hash = hash_password(user.password)
        cursor.execute('''
            INSERT INTO users (email, password_hash, full_name, role, max_sessions, is_temporary)
            VALUES (?, ?, ?, ?, ?, 0)
        ''', (user.email, password_hash, user.full_name, user.role, user.max_sessions))
        conn.commit()
        user_id = cursor.lastrowid
        
        # If first real admin, remove temporary admin
        if user.role == 'admin':
            deleted = cursor.execute('DELETE FROM users WHERE is_temporary = 1')
            if deleted.rowcount > 0:
                conn.commit()
                print(f"\n✓ Temporary admin removed! Permanent admin created: {user.email}\n")
        
        try:
            email_body = f"""
            <html><body>
                <h2>Welcome to Remote Access System</h2>
                <p>Hello {user.full_name},</p>
                <p><strong>Email:</strong> {user.email}<br>
                <strong>Password:</strong> {user.password}</p>
                <p>Please login and change your password.</p>
            </body></html>
            """
            send_email(user.email, "Your Remote Access Account", email_body)
        except Exception as e:
            print(f"Warning: Email failed: {e}")
        
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        created_user = cursor.fetchone()
        conn.close()
        
        return UserResponse(
            id=created_user['id'],
            email=created_user['email'],
            full_name=created_user['full_name'],
            role=created_user['role'],
            max_sessions=created_user['max_sessions'],
            is_active=bool(created_user['is_active']),
            is_temporary=bool(created_user['is_temporary']),
            created_at=created_user['created_at']
        )
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="User already exists")

@app.get("/api/users", response_model=List[UserResponse])
async def list_users(current_user: dict = Depends(verify_token)):
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users ORDER BY created_at DESC')
    users = cursor.fetchall()
    conn.close()
    
    return [
        UserResponse(
            id=u['id'],
            email=u['email'],
            full_name=u['full_name'],
            role=u['role'],
            max_sessions=u['max_sessions'],
            is_active=bool(u['is_active']),
            is_temporary=bool(u.get('is_temporary', 0)),
            created_at=u['created_at']
        )
        for u in users
    ]

@app.patch("/api/users/{user_id}")
async def update_user(user_id: int, user_update: UserUpdate, current_user: dict = Depends(verify_token)):
    """Enable/disable users or change max sessions"""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
    
    if user_id == current_user['user_id'] and user_update.is_active is False:
        conn.close()
        raise HTTPException(status_code=400, detail="Cannot disable yourself")
    
    updates = []
    params = []
    
    if user_update.is_active is not None:
        updates.append("is_active = ?")
        params.append(int(user_update.is_active))
    
    if user_update.max_sessions is not None:
        updates.append("max_sessions = ?")
        params.append(user_update.max_sessions)
    
    if updates:
        params.append(user_id)
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, params)
        conn.commit()
    
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    updated = cursor.fetchone()
    conn.close()
    
    return UserResponse(
        id=updated['id'],
        email=updated['email'],
        full_name=updated['full_name'],
        role=updated['role'],
        max_sessions=updated['max_sessions'],
        is_active=bool(updated['is_active']),
        is_temporary=bool(updated.get('is_temporary', 0)),
        created_at=updated['created_at']
    )

# Continue with remaining endpoints (SMTP, sessions, etc.) - keeping them as they were

@app.post("/api/smtp/config")
async def configure_smtp(config: SMTPConfig, current_user: dict = Depends(verify_token)):
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM smtp_config')
    cursor.execute('''
        INSERT INTO smtp_config (id, smtp_host, smtp_port, security_type, username, password, from_email, require_auth)
        VALUES (1, ?, ?, ?, ?, ?, ?, ?)
    ''', (config.smtp_host, config.smtp_port, config.security_type, 
          config.username, config.password, config.from_email, config.require_auth))
    conn.commit()
    conn.close()
    return {"message": "SMTP configured successfully"}

@app.get("/api/smtp/config")
async def get_smtp_config(current_user: dict = Depends(verify_token)):
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM smtp_config WHERE id = 1')
    config = cursor.fetchone()
    conn.close()
    
    if not config:
        return {"configured": False}
    
    return {
        "configured": True,
        "smtp_host": config['smtp_host'],
        "smtp_port": config['smtp_port'],
        "security_type": config['security_type'],
        "username": config['username'],
        "from_email": config['from_email'],
        "require_auth": bool(config['require_auth'])
    }

@app.post("/api/sessions", response_model=SessionResponse)
async def create_session(session_data: SessionCreate, current_user: dict = Depends(verify_token)):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT COUNT(*) as count FROM sessions 
        WHERE tech_user_id = ? AND status IN ('pending', 'active')
    ''', (current_user['user_id'],))
    active_count = cursor.fetchone()['count']
    
    cursor.execute('SELECT max_sessions FROM users WHERE id = ?', (current_user['user_id'],))
    max_sessions = cursor.fetchone()['max_sessions']
    
    if active_count >= max_sessions:
        conn.close()
        raise HTTPException(status_code=429, detail=f"Maximum concurrent sessions ({max_sessions}) reached")
    
    while True:
        session_code = generate_session_code()
        cursor.execute('SELECT id FROM sessions WHERE session_code = ?', (session_code,))
        if not cursor.fetchone():
            break
    
    try:
        udp_port = await udp_manager.create_udp_socket(session_code)
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail="Failed to allocate UDP port")
    
    cursor.execute('''
        INSERT INTO sessions (session_code, tech_user_id, customer_name, customer_email, udp_port, status)
        VALUES (?, ?, ?, ?, ?, 'pending')
    ''', (session_code, current_user['user_id'], session_data.customer_name, 
          session_data.customer_email, udp_port))
    conn.commit()
    session_id = cursor.lastrowid
    
    if session_data.customer_email:
        try:
            email_body = f"""
            <html><body>
                <h2>Remote Support Session</h2>
                <p>Session Code: <strong>{session_code}</strong></p>
            </body></html>
            """
            send_email(session_data.customer_email, "Your Remote Support Session", email_body)
        except Exception as e:
            print(f"Email warning: {e}")
    
    cursor.execute('SELECT * FROM sessions WHERE id = ?', (session_id,))
    session = cursor.fetchone()
    conn.close()
    
    return SessionResponse(
        id=session['id'],
        session_code=session['session_code'],
        tech_user_id=session['tech_user_id'],
        customer_name=session['customer_name'],
        customer_email=session['customer_email'],
        status=session['status'],
        udp_port=session['udp_port'],
        created_at=session['created_at']
    )

@app.get("/api/sessions", response_model=List[SessionResponse])
async def list_sessions(current_user: dict = Depends(verify_token)):
    conn = get_db()
    cursor = conn.cursor()
    
    if current_user['role'] == 'admin':
        cursor.execute('SELECT * FROM sessions ORDER BY created_at DESC LIMIT 100')
    else:
        cursor.execute('''
            SELECT * FROM sessions 
            WHERE tech_user_id = ? 
            ORDER BY created_at DESC 
            LIMIT 100
        ''', (current_user['user_id'],))
    
    sessions = cursor.fetchall()
    conn.close()
    
    return [
        SessionResponse(
            id=s['id'],
            session_code=s['session_code'],
            tech_user_id=s['tech_user_id'],
            customer_name=s['customer_name'],
            customer_email=s['customer_email'],
            status=s['status'],
            udp_port=s['udp_port'],
            created_at=s['created_at']
        )
        for s in sessions
    ]

@app.delete("/api/sessions/{session_id}")
async def close_session(session_id: int, current_user: dict = Depends(verify_token)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM sessions WHERE id = ?', (session_id,))
    session = cursor.fetchone()
    
    if not session:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")
    
    if current_user['role'] != 'admin' and session['tech_user_id'] != current_user['user_id']:
        conn.close()
        raise HTTPException(status_code=403, detail="Access denied")
    
    if session['udp_port']:
        udp_manager.close_session(session['session_code'], session['udp_port'])
    
    cursor.execute('''
        UPDATE sessions 
        SET status = 'closed', disconnected_at = CURRENT_TIMESTAMP 
        WHERE id = ?
    ''', (session_id,))
    conn.commit()
    conn.close()
    return {"message": "Session closed successfully"}

@app.get("/api/sessions/{session_code}/info")
async def get_session_info(session_code: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM sessions WHERE session_code = ?', (session_code,))
    session = cursor.fetchone()
    conn.close()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session['status'] == 'closed':
        raise HTTPException(status_code=410, detail="Session closed")
    
    return {
        "session_code": session['session_code'],
        "udp_port": session['udp_port'],
        "status": session['status']
    }

@app.websocket("/ws/session/{session_code}")
async def websocket_session(websocket: WebSocket, session_code: str):
    await websocket.accept()
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM sessions WHERE session_code = ?', (session_code,))
    session = cursor.fetchone()
    
    if not session:
        await websocket.close(code=1008, reason="Session not found")
        return
    
    cursor.execute('''
        UPDATE sessions 
        SET status = 'active', connected_at = CURRENT_TIMESTAMP 
        WHERE session_code = ?
    ''', (session_code,))
    conn.commit()
    conn.close()
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            if message['type'] == 'ping':
                await websocket.send_json({"type": "pong"})
            elif message['type'] == 'disconnect':
                break
    except WebSocketDisconnect:
        pass
    finally:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE sessions 
            SET status = 'disconnected', disconnected_at = CURRENT_TIMESTAMP 
            WHERE session_code = ?
        ''', (session_code,))
        conn.commit()
        conn.close()

@app.get("/")
async def root():
    return {"service": "Remote Access Server", "version": "1.0.0", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    # Get server IP to display
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except:
        local_ip = "127.0.0.1"
    
    print("\n" + "="*80)
    print("🚀 REMOTE ACCESS SERVER STARTING")
    print("="*80)
    print(f"📍 Access admin portal: http://{local_ip}")
    print(f"🔌 API endpoint: http://{local_ip}:8000")
    print("="*80 + "\n")
    
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False, workers=4)
