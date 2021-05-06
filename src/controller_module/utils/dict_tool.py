#python
from collections import defaultdict

#Author:Shabbyrobe
#https://stackoverflow.com/a/1118038/9441803
def class2dict(obj, classkey=None):
    if isinstance(obj, dict):
        data = {}
        for (k, v) in obj.items():
            data[k] = class2dict(v, classkey)
        return data
    if isinstance(obj, str):
        return obj
    elif hasattr(obj, "_ast"):
        return class2dict(obj._ast())
    elif hasattr(obj, "__iter__"):
        return [class2dict(v, classkey) for v in obj]
    elif hasattr(obj, "__dict__"):
        data = dict([(key, class2dict(value, classkey))
                     for key, value in obj.__dict__.items()
                     if not callable(value) and not key.startswith('_') and key not in ['name']])
        if classkey is not None and hasattr(obj, "__class__"):
            data[classkey] = obj.__class__.__name__
        return data
    else:
        return obj


def nested_dict(n, type):
    if n == 1:
        return defaultdict(type)
    else:
        return defaultdict(lambda: nested_dict(n-1, type))
