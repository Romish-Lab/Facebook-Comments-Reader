
# Facebook Live Comment Reader

An interactive, web-based application built with Python and Flask that reads new Facebook Page comments aloud in real-time. This tool is designed to bridge the gap between digital audience participation and live events, making streams and broadcasts more interactive.

---

## 🚀 Key Features

*   **Web-Based GUI:** Easy-to-use interface built with Flask. No command-line needed for normal operation.
*   **Dynamic Post Selection:** Automatically fetches recent posts from your page so you can choose which one to monitor, eliminating the need to manually find Post IDs.
*   **Real-Time Monitoring:** Polls the Facebook Graph API every 15 seconds for new comments.
*   **Text-to-Speech:** Uses Google Text-to-Speech (gTTS) to provide clear, audible feedback through your computer's speakers.
*   **Responsive UI:** A multi-threaded backend ensures the web interface never freezes while the comment-checking task runs in the background.

---

## 🛠️ Technology Stack

*   **Backend:** Python 3 & Flask
*   **Frontend:** HTML & CSS (rendered via Jinja templates)
*   **API Communication:** `requests` library
*   **Speech Synthesis:** `gTTS` library

---

## ⚙️ Setup and Installation Guide

Follow these steps to get the application running on your local machine.

### 1. Prerequisites

*   **Python 3:** Make sure you have Python 3 installed. During installation on Windows, it is **crucial** to check the box that says **"Add Python to PATH"**. You can download it from [python.org](https://www.python.org/).
*   **Facebook Developer Account:** You need a Facebook account with developer access.
*   **Facebook Page:** You must be an admin of the Facebook Page you want to monitor.

### 2. Clone the Repository

Clone this repository to your local machine using Git:
```bash
git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name
