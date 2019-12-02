from eventlet import event
import eventlet
import time
evt = event.Event()
def baz(b):
    time.sleep(2)
    evt.send()
    print("sss")

_ = eventlet.spawn_n(baz, 3)
print(evt.wait())