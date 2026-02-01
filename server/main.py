#!/usr/bin/env python3
"""
Remote Access Server - Main Application
Linux-based server for managing remote desktop sessions via UDP
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
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

# Database initialization
def init_db():
    conn = sqlite3.connect('remote_access.db')
    cursor = conn.cursor()
    
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
    
    # Create default admin user if not exists
    cursor.execute('SELECT COUNT(*) FROM users WHERE email = ?', ('admin@localhost',))
    if cursor.fetchone()[0] == 0:
        admin_hash = hashlib.sha256('admin123'.encode()).hexdigest()
        cursor.execute('''
            INSERT INTO users (email, password_hash, full_name, role, max_sessions)
            VALUES (?, ?, ?, ?, ?)
        ''', ('admin@localhost', admin_hash, 'System Administrator', 'admin', 50))
    
    conn.commit()
    conn.close()

# Pydantic models
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
    created_at: str

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
        """Allocate a free UDP port for a new session"""
        for port in range(self.port_range_start, self.port_range_end):
            if port not in self.used_ports:
                self.used_ports.add(port)
                return port
        raise Exception("No available UDP ports")
    
    def release_port(self, port: int):
        """Release a UDP port"""
        self.used_ports.discard(port)
    
    async def create_udp_socket(self, session_code: str) -> int:
        """Create UDP socket for session"""
        port = self.allocate_port()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('0.0.0.0', port))
        sock.setblocking(False)
        self.sessions[session_code] = sock
        return port
    
    def close_session(self, session_code: str, port: int):
        """Close UDP session"""
        if session_code in self.sessions:
            self.sessions[session_code].close()
            del self.sessions[session_code]
        self.release_port(port)

# Global instances
udp_manager = UDPSessionManager()
security = HTTPBearer()

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    yield
    # Shutdown
    pass

# FastAPI app
app = FastAPI(
    title="Remote Access Server API",
    description="TeamViewer-like remote access system",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helper functions
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
    """Generate a unique 9-digit session code"""
    return ''.join([str(secrets.randbelow(10)) for _ in range(9)])

def send_email(to_email: str, subject: str, body: str):
    """Send email using configured SMTP settings"""
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
    """Authenticate user and return JWT token"""
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
            "role": user['role']
        }
    }

@app.post("/api/users", response_model=UserResponse)
async def create_user(user: UserCreate, current_user: dict = Depends(verify_token)):
    """Create a new IT member (admin only)"""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        password_hash = hash_password(user.password)
        cursor.execute('''
            INSERT INTO users (email, password_hash, full_name, role, max_sessions)
            VALUES (?, ?, ?, ?, ?)
        ''', (user.email, password_hash, user.full_name, user.role, user.max_sessions))
        conn.commit()
        user_id = cursor.lastrowid
        
        # Send invitation email
        try:
            email_body = f"""
            <html>
            <body>
                <h2>Welcome to Remote Access System</h2>
                <p>Hello {user.full_name},</p>
                <p>Your account has been created successfully.</p>
                <p><strong>Email:</strong> {user.email}<br>
                <strong>Temporary Password:</strong> {user.password}</p>
                <p>Please login and change your password immediately.</p>
                <p>Login URL: <a href="http://your-server-address/admin">Admin Portal</a></p>
            </body>
            </html>
            """
            send_email(user.email, "Your Remote Access Account", email_body)
        except Exception as e:
            print(f"Warning: Failed to send invitation email: {e}")
        
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
            created_at=created_user['created_at']
        )
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="User already exists")

@app.get("/api/users", response_model=List[UserResponse])
async def list_users(current_user: dict = Depends(verify_token)):
    """List all users (admin only)"""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users ORDER BY created_at DESC')
    users = cursor.fetchall()
    conn.close()
    
    return [
        UserResponse(
            id=user['id'],
            email=user['email'],
            full_name=user['full_name'],
            role=user['role'],
            max_sessions=user['max_sessions'],
            is_active=bool(user['is_active']),
            created_at=user['created_at']
        )
        for user in users
    ]

@app.post("/api/smtp/config")
async def configure_smtp(config: SMTPConfig, current_user: dict = Depends(verify_token)):
    """Configure SMTP settings (admin only)"""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Delete existing config and insert new one
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
    """Get SMTP configuration (admin only, password hidden)"""
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
    """Create a new remote session"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Check current active sessions for user
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
    
    # Generate unique session code
    while True:
        session_code = generate_session_code()
        cursor.execute('SELECT id FROM sessions WHERE session_code = ?', (session_code,))
        if not cursor.fetchone():
            break
    
    # Allocate UDP port
    try:
        udp_port = await udp_manager.create_udp_socket(session_code)
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail="Failed to allocate UDP port")
    
    # Create session
    cursor.execute('''
        INSERT INTO sessions (session_code, tech_user_id, customer_name, customer_email, udp_port, status)
        VALUES (?, ?, ?, ?, ?, 'pending')
    ''', (session_code, current_user['user_id'], session_data.customer_name, 
          session_data.customer_email, udp_port))
    conn.commit()
    session_id = cursor.lastrowid
    
    # Send email to customer if provided
    if session_data.customer_email:
        try:
            email_body = f"""
            <html>
            <body>
                <h2>Remote Support Session</h2>
                <p>Hello {session_data.customer_name or 'Customer'},</p>
                <p>A remote support session has been initiated for you.</p>
                <p><strong>Session Code:</strong> <span style="font-size: 24px; font-weight: bold; color: #007bff;">{session_code}</span></p>
                <p>Please download the client application and enter this code to connect.</p>
                <p>Download link: <a href="http://your-server-address/downloads/client.exe">Windows Client</a></p>
            </body>
            </html>
            """
            send_email(session_data.customer_email, "Your Remote Support Session", email_body)
        except Exception as e:
            print(f"Warning: Failed to send session email: {e}")
    
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
    """List sessions for current user"""
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
            id=session['id'],
            session_code=session['session_code'],
            tech_user_id=session['tech_user_id'],
            customer_name=session['customer_name'],
            customer_email=session['customer_email'],
            status=session['status'],
            udp_port=session['udp_port'],
            created_at=session['created_at']
        )
        for session in sessions
    ]

@app.delete("/api/sessions/{session_id}")
async def close_session(session_id: int, current_user: dict = Depends(verify_token)):
    """Close/terminate a session"""
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
    
    # Close UDP socket
    if session['udp_port']:
        udp_manager.close_session(session['session_code'], session['udp_port'])
    
    # Update session status
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
    """Get session info by code (for client connection)"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM sessions WHERE session_code = ?', (session_code,))
    session = cursor.fetchone()
    conn.close()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session['status'] == 'closed':
        raise HTTPException(status_code=410, detail="Session has been closed")
    
    return {
        "session_code": session['session_code'],
        "udp_port": session['udp_port'],
        "status": session['status']
    }

@app.websocket("/ws/session/{session_code}")
async def websocket_session(websocket: WebSocket, session_code: str):
    """WebSocket for session signaling and control"""
    await websocket.accept()
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM sessions WHERE session_code = ?', (session_code,))
    session = cursor.fetchone()
    
    if not session:
        await websocket.close(code=1008, reason="Session not found")
        return
    
    # Update session status to active
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
            
            # Handle signaling messages (ICE candidates, SDP offers, etc.)
            if message['type'] == 'ping':
                await websocket.send_json({"type": "pong"})
            elif message['type'] == 'disconnect':
                break
                
    except WebSocketDisconnect:
        pass
    finally:
        # Update session status
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
    return {
        "service": "Remote Access Server",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        workers=4
    )
