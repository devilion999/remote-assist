# Quick Start Guide

## For IT Administrators

### 1. Initial Setup (One-time)

#### Deploy the Server

**Option A: Automated Deployment (Recommended)**
```bash
sudo bash deploy.sh
```

**Option B: Manual Deployment**
See [INSTALLATION.md](INSTALLATION.md) for detailed instructions.

#### First Login
1. Open web browser
2. Navigate to your server address (e.g., `https://your-domain.com`)
3. Login with default credentials:
   - Email: `admin@localhost`
   - Password: `admin123`
4. **IMMEDIATELY** change your password:
   - This is a security requirement
   - Use a strong password

#### Configure SMTP
1. Click **SMTP Config** tab
2. Enter your email server details:
   
   **For Microsoft 365:**
   ```
   SMTP Host: smtp.office365.com
   SMTP Port: 587
   Security: TLS
   Username: your-email@company.com
   Password: your-password
   From Email: noreply@company.com
   ```
   
   **For Gmail:**
   ```
   SMTP Host: smtp.gmail.com
   SMTP Port: 587
   Security: TLS
   Username: your-email@gmail.com
   Password: [App Password]
   From Email: your-email@gmail.com
   ```
   
3. Click **Save SMTP Configuration**
4. Test by creating a user (they should receive an email)

### 2. Adding IT Team Members

1. Click **Users** tab
2. Click **+ Add User**
3. Fill in the form:
   - Full Name: `John Doe`
   - Email: `john@company.com`
   - Password: `TempPass123!` (they should change this)
   - Role: `IT Technician` or `Administrator`
   - Max Sessions: `10` (concurrent sessions allowed)
4. Click **Create User**
5. User receives invitation email with login credentials

### 3. Distribute Windows Client

1. Build the client:
   ```powershell
   cd windows-client
   dotnet publish -c Release -r win-x64 --self-contained -p:PublishSingleFile=true
   ```

2. Find executable at:
   ```
   bin\Release\net6.0-windows\win-x64\publish\RemoteAccessClient.exe
   ```

3. Distribute via:
   - Email to IT team
   - Company file share
   - Internal software repository
   - Create installer with Inno Setup or similar

---

## For IT Technicians

### Creating a Support Session

1. **Login to Admin Portal**
   - Use your email and password
   - URL provided by administrator

2. **Create New Session**
   - Click **+ New Session** button
   - Fill in customer details (optional):
     - Customer Name
     - Customer Email (if provided, code is auto-sent)
   - Click **Create Session**

3. **Share Session Code**
   - 9-digit code is displayed (e.g., `482-916-573`)
   - Share with customer via:
     - Phone call
     - Email (auto-sent if you entered customer email)
     - Chat/messaging
     - Video call

4. **Guide Customer to Connect**
   - Customer runs `RemoteAccessClient.exe`
   - Customer enters the 9-digit session code
   - Customer clicks "Connect"
   - Wait for "Connected" status

5. **Provide Support**
   - You can now see customer's screen
   - Control their mouse and keyboard
   - Walk them through troubleshooting steps

6. **Close Session**
   - When done, click **Close** button
   - Or session auto-closes when customer disconnects

### Managing Multiple Sessions

- Monitor all active sessions in the **Sessions** tab
- Each session shows:
  - Session code
  - Customer name
  - Status (Pending/Active/Closed)
  - Connection time
  - UDP port
- You can have up to your configured limit (default: 10) concurrent sessions

### Tips for Best Experience

- **Stable Network**: Ensure customer has stable internet
- **Bandwidth**: ~500KB/s - 2MB/s per session
- **Latency**: Works best with <200ms latency
- **Firewall**: Customer's firewall should allow UDP outbound
- **Clear Instructions**: Walk customer through connection step-by-step

---

## For Customers (End Users)

### Connecting to Support Session

1. **Receive Session Code**
   - IT support will provide a 9-digit code
   - Example: `482-916-573`
   - May be sent via email or given over phone

2. **Download Client** (if not already installed)
   - Download link in email OR
   - IT support will provide download link

3. **Run the Client**
   - Double-click `RemoteAccessClient.exe`
   - No installation required

4. **Enter Session Code**
   - Type the 9-digit code
   - Or paste if received via email
   - Click **Connect**

5. **Allow Screen Sharing**
   - Your screen will be shared with IT support
   - They can control your mouse and keyboard
   - You can see everything they do

6. **Get Help**
   - IT support will diagnose and fix issues
   - Ask questions anytime
   - Support will guide you through steps

7. **End Session**
   - Click **Disconnect** when done
   - Or simply close the application
   - Session ends automatically

### Security & Privacy

✅ **Safe to Use:**
- Only works with valid session code
- Sessions expire automatically
- IT support can only access during active session
- No permanent access to your computer

✅ **What IT Support Can See:**
- Your screen (everything visible on display)
- Your running applications
- Your files (only what's on screen)

✅ **What IT Support Cannot See:**
- Files not opened during session
- Other screens/monitors (only primary display)
- Webcam or microphone
- Anything after session ends

### Troubleshooting

**Can't Connect?**
- Verify session code is correct (9 digits)
- Check internet connection
- Disable VPN temporarily
- Allow UDP connections in firewall
- Contact IT support for new session code

**Slow or Laggy?**
- Close unnecessary applications
- Check internet speed (need >1 Mbps upload)
- Move closer to WiFi router
- Use wired connection if possible

**Connection Drops?**
- Check internet stability
- Ask IT to create new session
- Reconnect with same code if session still active

---

## Common Scenarios

### Scenario 1: Quick Troubleshooting

**IT Tech:**
1. Login to admin portal
2. Click **+ New Session**
3. Enter customer name
4. Get session code: `482916573`
5. Call customer and read out code
6. Wait for customer to connect
7. Diagnose and fix issue (5-10 minutes)
8. Click **Close** when done

**Customer:**
1. Run RemoteAccessClient.exe
2. Enter code: `482916573`
3. Click Connect
4. Wait for IT to fix
5. Close application when done

---

### Scenario 2: Software Installation

**IT Tech:**
1. Create session with customer email
2. Customer receives email with:
   - Download link for client
   - Session code
3. Customer connects
4. Walk through installation remotely
5. Verify installation works
6. Close session

---

### Scenario 3: Training Session

**IT Tech:**
1. Schedule session with customer
2. Create session in advance
3. Email session code to customer
4. At scheduled time:
   - Customer connects
   - Demonstrate software features
   - Customer follows along
   - Answer questions in real-time
5. Session can last as long as needed
6. Close when training complete

---

## Best Practices

### For IT Teams

1. **Always verify customer identity** before sharing sensitive info
2. **Close sessions immediately** when support is complete
3. **Document session details** for records
4. **Use customer email** feature to auto-send codes
5. **Monitor concurrent sessions** to stay under limit
6. **Change default passwords** for all accounts
7. **Regular backups** of session database
8. **Review logs** for security monitoring

### For Security

1. **Never share session codes publicly**
2. **Use HTTPS** for admin portal (SSL required in production)
3. **Rotate admin passwords** regularly
4. **Limit user permissions** appropriately
5. **Monitor failed login attempts**
6. **Enable firewall** on server
7. **Keep software updated**

---

## Getting Help

### For Administrators
- Installation issues: See [INSTALLATION.md](INSTALLATION.md)
- API integration: See [API.md](API.md)
- System errors: Check logs with `sudo journalctl -u remote-access -f`

### For IT Technicians
- Contact your system administrator
- Check internal documentation
- Review this guide

### For Customers
- Contact your IT support team
- Provide session code and error message
- Describe the issue you're experiencing

---

## Appendix: Keyboard Shortcuts

### Windows Client

- **Tab** after entering 8 digits: Auto-triggers connection
- **Alt+F4**: Close application and disconnect
- **Escape** (when connected): Show disconnect confirmation

### Web Admin

- **Ctrl+R**: Refresh session list
- **Ctrl+N**: Create new session (when in Sessions tab)

---

**Need more help?** Contact your system administrator or refer to the full documentation.
