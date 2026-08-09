import base64, json, urllib.request, urllib.error, os
env={}
for line in open("/home/workloft/larry-tier-routing/.env.tier-keys"):
    line=line.strip()
    if line and not line.startswith("#") and "=" in line:
        k,v=line.split("=",1); env[k]=v.strip().strip('"')
key=env["OPENAI_API_KEY"]
prompt=("Cinematic photorealistic 3D render, deep near-black background (#0a0a0a), moody low-key lighting, "
"lots of negative space. A row of five dark matte monolithic cubes recedes across a dark polished floor. "
"A single glowing warm orange-red (#FA3E33) molten thread runs through the first four cubes, then curls back "
"on itself in a tight U-turn and flows in reverse, unwinding, its glow retreating from the fifth cube, which "
"stands dark, cold and slightly cracked, clearly the failed step. The orange thread rim-lights the near edges "
"of the cubes and reflects on the floor, molten filaments trailing where it reverses. Strictly monochrome: "
"only deep blacks, dark greys, and glowing orange-red. FORBIDDEN: white or light background, any other colour "
"(no teal, cyan, blue, yellow, green, purple), flat vector or wireframe or line-art, glossy multicolour, "
"clipart, and any text, words, letters, numbers, logos, animals, creatures or people. Centred composition "
"with room for overlay text.")
body=json.dumps({"model":"gpt-image-2","prompt":prompt,"size":"1536x1024","quality":"high","n":1}).encode()
req=urllib.request.Request("https://api.openai.com/v1/images/generations",data=body,
    headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"})
out="/home/workloft/workloft-site/ships/assets/agent-tool-call-saga-2026-08-09-hero.png"
try:
    resp=json.load(urllib.request.urlopen(req,timeout=240))
    open(out,"wb").write(base64.b64decode(resp["data"][0]["b64_json"]))
    print("HERO_OK",out,os.path.getsize(out))
except urllib.error.HTTPError as e:
    print("HTTP_ERR",e.code,e.read().decode()[:400])
