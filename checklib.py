
import subprocess
import sys
import time
from os import name

def CHECK_OK():
    pass

pip_download_ = [] # array für die libs die installiert werden müssen
try:
    import websockets
except ImportError:
    print("websockets not found")
    pip_download_.append('websockets')

try:
    import psutil
except ImportError:
    print("psutil not found")
    pip_download_.append('psutil')

if not pip_download_ == []:
    ## installiert alle libs mit pip
    if name == 'nt':
        # Windows
        try:
            for package in pip_download_:
                print("Installing "+ package+" in Global mode")
                subprocess.call([sys.executable.replace('pythonw.exe', 'python.exe')
                                    , '-m', 'pip', 'install', package])
                __import__(package)
        except:
            print("Global mode faild")
            for package in pip_download_:
                print("Installing "+ package+" in User mode")
                subprocess.call([sys.executable.replace('pythonw.exe', 'python.exe')
                                    , '-m', 'pip', 'install', package, '--user'])
    else:
        # Linux und Mac
        try:
            for package in pip_download_:
                print("Installing "+ package)
                subprocess.call([sys.executable, "-m", "pip", "install", package])
                __import__(package)
        except:
            print("Installation faild")
            for package in pip_download_:
                print("Installing "+ package)
                subprocess.call([sys.executable, "-m", "pip", "install", package, '--user'])

    # Restart Script
    print("Trying to Restart Script")
    time.sleep(10)
    subprocess.call([sys.executable,sys.argv[0]])
    sys.exit(0)