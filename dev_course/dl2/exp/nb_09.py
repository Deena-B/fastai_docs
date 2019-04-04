
#################################################
### THIS FILE WAS AUTOGENERATED! DO NOT EDIT! ###
#################################################
# file to edit: dev_nb/09_optimizers.ipynb

from exp.nb_08 import *

class Optimizer(optim.Optimizer):
    def __init__(self, params, steppers, **defaults):
        self.steppers = listify(steppers)
        stepper_defaults = {}
        for stepper in self.steppers: stepper_defaults.update(getattr(stepper,'_defaults',{}))
        super().__init__(params, {**stepper_defaults, **defaults})

    def step(self):
        for pg in self.param_groups:
            for p in pg['params']:
                if p.grad is not None: compose(p, self.steppers, pg=pg)

class StatefulOptimizer(optim.Optimizer):
    def __init__(self, params, steppers, stats=None, **defaults):
        self.steppers,self.stats = listify(steppers),listify(stats)
        base_defaults = {}
        for stepper in self.steppers: base_defaults.update(getattr(stepper,'_defaults',{}))
        for stat in self.stats:       base_defaults.update(getattr(stat,'_defaults',{}))
        super().__init__(params, {**base_defaults, **defaults})

    def step(self):
        for pg in self.param_groups:
            for p in pg['params']:
                if p.grad is not None:
                    if p not in self.state:
                        init_state = {}
                        for stat in self.stats: init_state.update(stat.init_state(p))
                        self.state[p] = init_state
                    state = self.state[p]
                    for stat in self.stats: state = stat.update(p, pg, state)
                    compose(p, self.steppers, pg=pg, state=state)
                    self.state[p] = state

class Stat():
    _defaults = {}
    def init_state(self, p):        raise NotImplementedError
    def update(self, p, pg, state): raise NotImplementedError

class AverageGrad(Stat):
    _defaults = dict(mom=0.9)

    def init_state(self, p): return {'grad_avg': torch.zeros_like(p.grad.data)}
    def update(self, p, pg, state):
        state['grad_avg'].mul_(pg['mom']).add_(p.grad.data)
        return state

class WeightDecay():
    _defaults = dict(wd=0.)
    def __call__(self,p,pg,state):
        p.data.mul_(1 - pg['lr'] * pg['wd'])
        return p

class L2_Reg():
    _defaults = dict(wd=0.)
    def __call__(self,p,pg,state):
        p.grad.data.add_(pg['wd'], p.data)
        return p

def sgd_step(p, pg,state):
    p.data.add_(-pg['lr'], p.grad.data)
    return p

def momentum_step(p, pg, state):
    p.data.add_(-pg['lr'], state['grad_avg'])
    return p

class AverageGrad(Stat):
    _defaults = dict(mom=0.9)

    def __init__(self, dampening:bool=False): self.dampening=dampening
    def init_state(self, p): return {'grad_avg': torch.zeros_like(p.grad.data)}
    def update(self, p, pg, state):
        pg['mom_damp'] = 1 - pg['mom'] if self.dampening else 1.
        state['grad_avg'].mul_(pg['mom']).add_(pg['mom_damp'], p.grad.data)
        return state

class AverageSqrGrad(Stat):
    _defaults = dict(sqr_mom=0.99)

    def __init__(self, dampening:bool=True): self.dampening=dampening
    def init_state(self, p): return {'sqr_avg': torch.zeros_like(p.grad.data)}
    def update(self, p, pg, state):
        pg['sqr_damp'] = 1 - pg['sqr_mom'] if self.dampening else 1.
        state['sqr_avg'].mul_(pg['sqr_mom']).addcmul_(pg['sqr_damp'],p.grad.data,p.grad.data)
        return state

class StepCount(Stat):
    def init_state(self, p): return {'step': 0}
    def update(self, p, pg, state):
        state['step'] += 1
        return state

def debias(mom, damp, step): return damp * (1 - mom**step) / (1-mom)

class AdamStep():
    _defaults = dict(eps=1e-5)
    def __call__(self, p, pg, state):
        debias1 = debias(pg['mom'],     pg['mom_damp'], state['step'])
        debias2 = debias(pg['sqr_mom'], pg['sqr_damp'], state['step'])
        p.data.addcdiv_(-pg['lr'] / debias1, state['grad_avg'], (state['sqr_avg']/debias2 + pg['eps']).sqrt())
        return p