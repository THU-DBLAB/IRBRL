#python

class ssdds():
    def __init__(self):
        self.af=2
        self.fg="3"

class sss():
    def __init__(self):
        self.af=ssdds()
        self.fg="3"

class A(object):
 
    def __init__(self):
        self.a = sss()
        self.b = 5
        self.c = 6

def return_class_variables(A):
    return(A.__dict__)

def class2dict(obj, classkey=None):
    print(obj ,classkey)
    if hasattr(obj, "__dict__"):
        data = dict(
                        [(key, class2dict(value, classkey))
                            for key, value in obj.__dict__.items()
                            if not callable(value)  
                        ]
                     
                    )
        print(data)
        if classkey is not None and hasattr(obj, "__class__"):
            data[classkey] = obj.__class__.__name__
        return data
    else:
         
        return obj
if __name__ == "__main__":
 
  
    a=A()
   
    print(class2dict(a))
     


    