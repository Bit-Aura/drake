from simpleeval import simple_eval

class Obj:
    def __init__(self, d):
        self.__dict__.update(d)

names = {'workflow': Obj({'risk_level': 'high', 'is_bulk': True})}
res = simple_eval('workflow.risk_level == "high"', names=names)
print(res)
