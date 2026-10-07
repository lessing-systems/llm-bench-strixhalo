REF = {}
REF["merge_intervals"] = '''
def merge_intervals(intervals):
    out=[]
    for s,e in sorted(intervals):
        if out and s<=out[-1][1]: out[-1][1]=max(out[-1][1],e)
        else: out.append([s,e])
    return out
'''
REF["regex_match"] = '''
from functools import lru_cache
def is_match(s,p):
    @lru_cache(None)
    def d(i,j):
        if j==len(p): return i==len(s)
        f=i<len(s) and p[j] in (s[i],'.')
        if j+1<len(p) and p[j+1]=='*': return d(i,j+2) or (f and d(i+1,j))
        return f and d(i+1,j+1)
    return d(0,0)
'''
REF["parse_duration"] = '''
import re
def parse_duration(s):
    if not s or not s.strip(): raise ValueError
    toks=re.fullmatch(r"\\s*(\\d+[dhms]\\s*)+", s)
    if not toks: raise ValueError
    seen=set(); tot=0
    for n,u in re.findall(r"(\\d+)([dhms])", s):
        if u in seen: raise ValueError
        seen.add(u); tot+=int(n)*{'d':86400,'h':3600,'m':60,'s':1}[u]
    return tot
'''
REF["lru"] = '''
from collections import OrderedDict
class LRUCache:
    def __init__(self,c): self.c=c; self.d=OrderedDict()
    def get(self,k):
        if k not in self.d: return -1
        self.d.move_to_end(k); return self.d[k]
    def put(self,k,v):
        self.d[k]=v; self.d.move_to_end(k)
        if len(self.d)>self.c: self.d.popitem(last=False)
'''
REF["topo"] = '''
import heapq
def topo_order(n,edges):
    g=[[] for _ in range(n)]; ind=[0]*n
    for u,v in edges: g[u].append(v); ind[v]+=1
    h=[i for i in range(n) if ind[i]==0]; heapq.heapify(h); out=[]
    while h:
        u=heapq.heappop(h); out.append(u)
        for v in g[u]:
            ind[v]-=1
            if ind[v]==0: heapq.heappush(h,v)
    if len(out)<n: raise ValueError
    return out
'''
REF["spiral"] = '''
def spiral(m):
    out=[]
    m=[list(r) for r in m]
    while m:
        out+=m.pop(0)
        m=[list(r) for r in zip(*m)][::-1]
    return out
'''
REF["table_fmt"] = '''
def fmt_table(rows):
    w=len(rows[0]); rows=[r+['']*(w-len(r)) for r in rows]
    W=[max(len(r[i]) for r in rows) for i in range(w)]
    def num(x):
        try: float(x); return True
        except: return False
    b='+'+'+'.join('-'*(x+2) for x in W)+'+'
    def line(r,h):
        return '|'+'|'.join(' '+(c.rjust(W[i]) if (not h and num(c)) else c.ljust(W[i]))+' ' for i,c in enumerate(r))+'|'
    return '\\n'.join([b,line(rows[0],True),b]+[line(r,False) for r in rows[1:]]+[b])
'''
REF["multiply_str"] = '''
def multiply(a,b):
    a=a.lstrip('0') or '0'; b=b.lstrip('0') or '0'
    if a=='0' or b=='0': return '0'
    r=[0]*(len(a)+len(b))
    for i in range(len(a)-1,-1,-1):
        for j in range(len(b)-1,-1,-1):
            r[i+j+1]+= (ord(a[i])-48)*(ord(b[j])-48)
    for k in range(len(r)-1,0,-1):
        r[k-1]+=r[k]//10; r[k]%=10
    return ''.join(map(str,r)).lstrip('0')
'''
REF["islands"] = '''
def count_islands(g):
    if not g: return 0
    H=len(g); W=len(g[0]); seen=[[False]*W for _ in range(H)]; c=0
    for i in range(H):
        for j in range(W):
            if g[i][j]=='#' and not seen[i][j]:
                c+=1; st=[(i,j)]; seen[i][j]=True
                while st:
                    x,y=st.pop()
                    for dx in (-1,0,1):
                        for dy in (-1,0,1):
                            a,b=x+dx,y+dy
                            if 0<=a<H and 0<=b<W and g[a][b]=='#' and not seen[a][b]:
                                seen[a][b]=True; st.append((a,b))
    return c
'''
REF["interval_sched"] = '''
import bisect
def max_weight_schedule(jobs):
    jobs=sorted(jobs,key=lambda j:j[1]); ends=[j[1] for j in jobs]; dp=[0]*(len(jobs)+1)
    for i,(s,e,w) in enumerate(jobs):
        k=bisect.bisect_right(ends,s,0,i)
        dp[i+1]=max(dp[i],dp[k]+w)
    return dp[-1]
'''
