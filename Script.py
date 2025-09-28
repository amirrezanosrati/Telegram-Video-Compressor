# Script.py
import threading
import subprocess

def run_server():
    subprocess.run(["python", "server.py"])

def run_bot():
    subprocess.run(["python", "bot.py"])

t1 = threading.Thread(target=run_server)
t2 = threading.Thread(target=run_bot)
t1.start()
t2.start()
t1.join()
t2.join()
