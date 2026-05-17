import time
def log(msg, timestamp=time.time()):
    print(f"[{timestamp}] {msg}")

log("hallo")
log("welt")
