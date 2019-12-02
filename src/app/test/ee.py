# an example of python decorator
def deco1(func):
    print(1)
    def wrapper1():
        print(2)
        func()
        print(3)
    print(4)
    return wrapper1

def deco2(func):
    print(5)
    def wrapper2():
        print(6)
        func()
        print(7)
    print(8)
    return wrapper2

@deco1
@deco2
def foo():
    print('foo')


if __name__ == '__main__':
    foo()