import json,sys,requests,time
T={t['id']:t for t in json.load(open(__import__('os').path.join(__import__('os').path.dirname(__file__),'tasks.json')))}
url=sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8091'
for tid in sys.argv[2:] or ['long_350']:
    p=T[tid]['prompt']+f" [{time.time()}]"
    t0=time.time(); r=requests.post(url+'/v1/chat/completions',json={"messages":[{"role":"user","content":p}],"max_tokens":1,"chat_template_kwargs":{"enable_thinking":False}}).json()
    tm=r['timings']; print(f"{tid}: prompt_n={tm['prompt_n']} pp={tm['prompt_per_second']:.0f} t/s wall={time.time()-t0:.1f}s")
