import randopt as ro

def loss(x):
    return x**2

e = ro.Experiment('myexp', {
        'alpha': ro.Gaussian(mean=0.0, std=1.0, dtype='float'),
    })

# Sampling parameters
for i in range(100):
    e.sample('alpha')
    res = loss(e.alpha)
    print('Result: ', res)
    e.add_result(res)

# Manually setting parameters
e.alpha = 0.00001
res = loss(e.alpha)
e.add_result(res)

# Search over all experiments results, including ones from previous runs
opt = e.minimum()
print('Best result: ', opt.result, ' with params: ', opt.params)