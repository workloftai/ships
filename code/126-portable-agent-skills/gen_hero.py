import os, base64, json, urllib.request, urllib.error
env={}
for line in open("/home/workloft/larry-tier-routing/.env.tier-keys"):
    line=line.strip()
    if line and not line.startswith("#") and "=" in line:
        k,v=line.split("=",1); env[k]=v.strip().strip('"')
key=env["OPENAI_API_KEY"]
prompt=("Cinematic photorealistic 3D render, deep near-black background (#0a0a0a), moody low-key lighting, "
"lots of negative space. A single glowing warm orange-red (#FA3E33) modular cube, edges molten and luminous, "
"hovers at the centre. Fine glowing orange filaments fan out from it to a row of five identical dark matte "
"monolithic gateways receding into the black, each gateway lit only where a filament meets it, so the one "
"bright module is clearly being received by many dark portals at once. The orange glow rim-lights the near "
"edges of the gateways and reflects on a dark polished floor. Strictly monochrome: only deep blacks, dark "
"greys, and glowing orange-red. FORBIDDEN: white or light background, any other colour (no teal, cyan, blue, "
"yellow, green, purple), flat vector or wireframe or line-art, glossy multicolour, clipart, and any text, "
"words, letters, logos, animals, creatures or people. Centred composition with room for overlay text.")
body=json.dumps({"model":"gpt-image-2","prompt":prompt,"size":"1536x1024","quality":"high","n":1}).encode()
req=urllib.request.Request("https://api.openai.com/v1/images/generations",data=body,
    headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"})
out="/home/workloft/workloft-site/ships/assets/portable-agent-skills-2026-08-09-hero.png"
try:
    resp=json.load(urllib.request.urlopen(req,timeout=240))
    open(out,"wb").write(base64.b64decode(resp["data"][0]["b64_json"]))
    print("HERO_OK",out,os.path.getsize(out))
except urllib.error.HTTPError as e:
    print("HTTP_ERR",e.code,e.read().decode()[:400])
