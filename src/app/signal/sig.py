import signal
# Define signal handler function
def myHandler(signum, frame):
    print("Now, it's the time")
    exit()

# register signal.SIGALRM's handler 
 
signal.alarm(5)
signal.pause()
 