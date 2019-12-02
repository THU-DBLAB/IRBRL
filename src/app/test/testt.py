#python
class aa(object):
    def __init__(self):
        self.a=2
    def a1(self):
        c=self.a
        c=c+1
        return self.a
    def a2(self):
        self.a=self.a+1
        return self.a

a=aa()

print(a.a2())