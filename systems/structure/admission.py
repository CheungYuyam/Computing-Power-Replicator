"""Exact earliest-fitting ready task, grouped by resource request for efficiency."""
import heapq


class FirstFitQueue:
    def __init__(self): self.groups={}
    def push(self,time,stream,resources):
        key=tuple(resources)
        heapq.heappush(self.groups.setdefault(key,[]),(time,stream))
    def pop_fitting(self,free):
        candidate=None;chosen=None
        for resources,q in self.groups.items():
            if all(r<=f+1e-8 for r,f in zip(resources,free)):
                if candidate is None or q[0]<candidate:candidate=q[0];chosen=resources
        if chosen is None:return None
        heapq.heappop(self.groups[chosen])
        if not self.groups[chosen]:del self.groups[chosen]
        return candidate
