def use_logging(func):

    def wrapper():
        while True:
            print("ssssss")
    return wrapper

@use_logging
def foo():
    print("i am foo")

foo()