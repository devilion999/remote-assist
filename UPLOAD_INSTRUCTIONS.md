# How to Upload to GitHub

## Step 1: Download This Folder

Download the entire **remote-access-system** folder to your computer.

## Step 2: Upload to GitHub

You have two options:

### Option A: Drag and Drop (Easiest)

1. Go to https://github.com/devilion999/remote-assist
2. Click "Add file" → "Upload files"
3. Drag ALL the folders and files into the upload area:
   - `server/` folder (with main.py inside)
   - `web-admin/` folder (with index.html inside)
   - `windows-client/` folder (with .cs and .csproj files)
   - `docs/` folder (with all .md files)
   - `deploy.sh`
   - `install.sh`
   - `README.md`
   - `LICENSE`
   - `.gitignore`
4. Add commit message: "Initial commit"
5. Click "Commit changes"

### Option B: Use Git Command Line

```bash
cd /path/to/remote-access-system

git init
git add .
git commit -m "Initial commit: Complete remote access system"
git branch -M main
git remote add origin https://github.com/devilion999/remote-assist.git
git push -u origin main
```

## Step 3: Verify Upload

Go to https://github.com/devilion999/remote-assist

You should see:
- ✅ server/ (folder)
- ✅ web-admin/ (folder)
- ✅ windows-client/ (folder)
- ✅ docs/ (folder)
- ✅ deploy.sh
- ✅ install.sh
- ✅ README.md
- ✅ LICENSE
- ✅ .gitignore

## Step 4: Deploy on Server

Once uploaded to GitHub, SSH into your Linux server and run:

```bash
curl -sSL https://raw.githubusercontent.com/devilion999/remote-assist/main/install.sh | sudo bash
```

This will:
- Clone from GitHub
- Install all dependencies
- Configure everything
- Start the service

## Step 5: Access Admin Portal

Open browser: `http://your-server-ip`

Login:
- Email: `admin@localhost`
- Password: `admin123`

**Change password immediately!**

---

## Folder Structure

Make sure your GitHub repository looks like this:

```
remote-assist/
├── server/
│   ├── main.py
│   └── requirements.txt
├── web-admin/
│   └── index.html
├── windows-client/
│   ├── RemoteAccessClient.cs
│   └── RemoteAccessClient.csproj
├── docs/
│   ├── INSTALLATION.md
│   ├── QUICK_START.md
│   └── API.md
├── deploy.sh
├── install.sh
├── README.md
├── LICENSE
└── .gitignore
```

If it looks like this, you're good to go! 🚀
