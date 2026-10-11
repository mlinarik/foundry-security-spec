"""Named task-queue facade sharing one owner claim mechanism."""
class Tasks:
    def __init__(self,queues,name='work'):
        if not name or len(name)>100: raise ValueError('Bounded queue name required')
        self.queues,self.name=queues,name

    def add(self,actor,evaluation,payload,key):
        return self.queues.add(actor,evaluation,payload,key,queue=self.name)

    def claim(self,actor,key):
        return self.queues.claim(actor,'task',self.name,key)

    def edit(self,actor,evaluation,identity,payload,key):
        return self.queues.edit(actor,evaluation,identity,payload,key)
