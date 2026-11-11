MAXZ=5
def parse_grades(t):
  r=[]
  for w in t.split():
    if not w.isdigit() or int(w)<1 or int(w)>MAXZ: raise ValueError("neplatná známka: "+w)
    r+=[int(w)]
  return r
def average(g):
  if len(g)==0: raise ValueError("žádné známky")
  s=0
  for x in g: s=s+x
  return s/len(g)
def format_summary(g):
  return "Počet známek: "+str(len(g))+", průměr: "+str(round(average(g),2))+", nejlepší: "+str(min(g))+", nejhorší: "+str(max(g))
