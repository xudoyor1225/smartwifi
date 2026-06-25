# 🚀 Smart WiFi Dashboard

This project is a high-performance, real-time dashboard for managing MikroTik routers. It uses FastAPI for the backend and React (Vite) for the frontend, bundled in a Dockerized environment for extremely easy deployment.

## 🛠️ Deploy to Server (VPS/VDS)

Deploying this project to any Linux server is incredibly simple. All you need is Docker installed on the server.

### 1. Prerequisites
Make sure `git`, `docker`, and `docker-compose` are installed on your server:
```bash
sudo apt update
sudo apt install git docker.io docker-compose -y
```

### 2. Clone the Repository
```bash
git clone https://github.com/yourusername/mainproject2.git
cd mainproject2
```

### 3. Start the Application
Run the following command to build and start the application in the background:
```bash
sudo docker-compose up -d --build
```

That's it! 🎉 The dashboard is now running.
- **Web UI:** Open `http://<your-server-ip>` in your browser.
- **Backend API Docs:** Open `http://<your-server-ip>:8000/docs`.

### 4. Updating the App
If you push new changes to GitHub and want to update the server:
```bash
git pull
sudo docker-compose up -d --build
```

---

## 💻 Local Development
If you want to run the project locally without Docker:

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```
