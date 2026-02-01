# Remote Assist

A comprehensive TeamViewer-like remote access solution with Linux server backend, web-based administration, and Windows client application.

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows-lightgrey)

## 🚀 Quick Deploy

Deploy on your Linux server in one command:

```bash
curl -sSL https://raw.githubusercontent.com/devilion999/remote-assist/main/install.sh | sudo bash
```

Or clone and deploy manually:

```bash
git clone https://github.com/devilion999/remote-assist.git
cd remote-assist
sudo bash deploy.sh
```

## 🎯 Features

### Server (Linux)
- ✅ RESTful API with FastAPI
- ✅ SQLite database for data persistence
- ✅ UDP-based real-time screen streaming (ports 50000-60000)
- ✅ WebSocket support for session control
- ✅ JWT authentication
- ✅ Session management with automatic cleanup
- ✅ Email notifications via SMTP
- ✅ Multi-user support with role-based access

### Web Admin Portal
- ✅ Modern, responsive interface
- ✅ User management (create, view IT members)
- ✅ Session management (create, monitor, close)
- ✅ SMTP configuration with Microsoft 365 support
- ✅ Real-time session monitoring
- ✅ Statistics dashboard
- ✅ Admin and technician roles

### Windows Client
- ✅ Lightweight standalone executable
- ✅ UDP-based screen capture and streaming
- ✅ 15 FPS real-time transmission
- ✅ JPEG compression for efficient bandwidth
- ✅ Remote mouse and keyboard control
- ✅ Simple 9-digit session code connection
- ✅ Automatic reconnection handling

## 📋 Requirements

### Server
- Ubuntu 20.04+ or Debian 11+
- Python 3.10+
- 2GB+ RAM (4GB recommended)
- 2+ CPU cores
- Static IP or domain name

### Client
- Windows 10/11 (64-bit)
- .NET 6.0 Runtime
- Network: Outbound UDP access

## 📖 Documentation

- [Installation Guide](docs/INSTALLATION.md) - Complete deployment instructions
- [Quick Start Guide](docs/QUICK_START.md) - How to use the system
- [API Documentation](docs/API.md) - REST API reference

## 🏗️ Architecture

```
┌──────────────────┐
│  Windows Client  │ (Customer)
│  - Screen Share  │
│  - UDP Sender    │
└────────┬─────────┘
         │ UDP (50000+)
         ▼
┌──────────────────┐
│  Linux Server    │
│  - FastAPI       │
│  - SQLite DB     │
│  - UDP Handler   │
│  - SMTP          │
└────────┬─────────┘
         │ REST API
         ▼
┌──────────────────┐
│  Web Admin       │ (IT Members)
│  - HTML/CSS/JS   │
│  - Session Mgmt  │
│  - User Mgmt     │
└──────────────────┘
```

## 🔐 Security Features

- JWT-based authentication
- Role-based access control (Admin/Technician)
- Session expiration and automatic cleanup
- HTTPS support (with Nginx/SSL)
- Configurable session limits per user
- Password hashing (SHA-256)
- SMTP authentication for email notifications

## 🚀 Getting Started

### 1. Deploy Server

```bash
# Quick install
curl -sSL https://raw.githubusercontent.com/devilion999/remote-assist/main/install.sh | sudo bash
```

### 2. Access Admin Portal

Open browser: `http://your-server-ip`

Login:
- Email: `admin@localhost`
- Password: `admin123`

**⚠️ Change password immediately!**

### 3. Configure SMTP

Navigate to "SMTP Config" tab and enter your email server details.

For Microsoft 365:
```
SMTP Host: smtp.office365.com
SMTP Port: 587
Security: TLS
Username: your-email@company.com
Password: your-password
```

### 4. Create IT Members

1. Click "Users" tab
2. Click "+ Add User"
3. Fill in details
4. User receives invitation email

### 5. Build Windows Client

```powershell
git clone https://github.com/devilion999/remote-assist.git
cd remote-assist/windows-client
dotnet publish -c Release -r win-x64 --self-contained -p:PublishSingleFile=true
```

Executable will be in: `bin\Release\net6.0-windows\win-x64\publish\RemoteAccessClient.exe`

## 💼 Use Cases

- Remote IT Support
- Customer Onboarding
- Technical Troubleshooting
- Training Sessions
- Remote Maintenance

## 📞 Support

- Issues: https://github.com/devilion999/remote-assist/issues
- Documentation: See [docs/](docs/) directory

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- FastAPI for the excellent web framework
- .NET for cross-platform development
- The open-source community

---

**Made with ❤️ for IT teams worldwide**
