#python
def batch(iterable, n=1):
    l = len(iterable)
    for ndx in range(0, l, n):
        yield iterable[ndx:min(ndx + n, l)]
        print(ndx)
a=[1,2,3,4,5,6,7,8,9,7,5,4,3]
exit(1)
for x in batch(a, 3):
    print (x)