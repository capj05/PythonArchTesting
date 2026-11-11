from .inventory import Inventory
def sell(i,it,q): i.remove(it,q)
def restock(i,d):
  for k in d: i.add(k,d[k])
def clear_out(i,it):
  q=i.quantity(it)
  if q>0: i.remove(it,q)
  return q
def report(i):
  s=""
  t=0
  for k in sorted(i.items()):
    s=s+k+": "+str(i.items()[k])+" ks\n"; t=t+i.items()[k]
  return s+"Celkem: "+str(t)+" ks"
