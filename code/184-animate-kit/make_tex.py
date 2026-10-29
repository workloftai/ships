from PIL import Image, ImageDraw, ImageFont
import os
F=os.environ.get("ANIMATE_FONT", "Figtree.ttf")  # any TTF with bold/medium weights
def font(sz,w="Bold"):
    f=ImageFont.truetype(F,sz)
    try: f.set_variation_by_name(w)
    except Exception: pass
    return f
INK=(4,20,26);SUB=(19,52,64);MUT=(70,92,100);RED=(214,48,39);AMB=(180,83,9);TEAL=(0,151,153)
W,H=1024,560
def label(name,desc,out,ncol=INK,dcol=MUT,missing=False):
    im=Image.new("RGBA",(W,H),(0,0,0,0));d=ImageDraw.Draw(im)
    if missing:
        d.rounded_rectangle((24,24,W-24,H-24),40,fill=(255,255,255,90))
        # dashed border
        for x in range(60,W-60,44): d.line((x,26,x+24,26),fill=(95,115,122,255),width=7);d.line((x,H-26,x+24,H-26),fill=(95,115,122,255),width=7)
        for y in range(60,H-60,44): d.line((26,y,26,y+24),fill=(95,115,122,255),width=7);d.line((W-26,y,W-26,y+24),fill=(95,115,122,255),width=7)
        f=font(92,"Medium");t="no label";w=d.textlength(t,font=f)
        d.text(((W-w)/2,H/2-58),t,font=f,fill=(80,100,108,255))
    else:
        d.rounded_rectangle((24,24,W-24,H-24),40,fill=(255,255,255,255),outline=(225,235,238,255),width=6)
        f=font(112 if len(name)<14 else 96,"Bold");w=d.textlength(name,font=f)
        d.text(((W-w)/2,150),name,font=f,fill=ncol)
        f2=font(64,"Medium");w=d.textlength(desc,font=f2)
        d.text(((W-w)/2,320),desc,font=f2,fill=dcol)
    im.save("tex/"+out)
label("get_customer","Look up a customer","l_get_customer.png")
label("","","l_missing.png",missing=True)
label("update_address","Change a customer address","l_update_address.png",ncol=(0,120,122))
label("create_ticket","Open a support ticket","l_create_ticket.png")
label("send_email","Email a customer","l_send_email.png")
label("read_records","Read records","l_read_records.png")
label("delete_records","Deletes · needs approval","l_delete_records.png",ncol=RED,dcol=RED)
label("InvoiceUpdate","Updates stuff","l_invoiceupdate.png")
label("update_invoice","Writes to finance · flagged","l_update_invoice.png",ncol=AMB,dcol=AMB)
# DELETES stencil
im=Image.new("RGBA",(1024,256),(0,0,0,0));d=ImageDraw.Draw(im);f=font(150,"Black");t="DELETES";w=d.textlength(t,font=f)
d.text(((1024-w)/2,40),t,font=f,fill=(255,255,255,255));im.save("tex/deletes.png")
print("ok")
# badges
def badge(kind,col,out):
    S=512;im=Image.new("RGBA",(S,S),(0,0,0,0));d=ImageDraw.Draw(im)
    d.ellipse((16,16,S-16,S-16),fill=col+(255,),outline=(255,255,255,255),width=28)
    if kind=="tick": d.line((150,270,225,345),fill="white",width=52);d.line((215,350,365,180),fill="white",width=52)
    elif kind=="shield":
        d.polygon([(256,120),(370,165),(355,300),(256,390),(157,300),(142,165)],fill="white")
        d.line((215,262,248,295),fill=col,width=26);d.line((242,300,300,222),fill=col,width=26)
    else:
        f=font(300,"Black");w=d.textlength(kind,font=f);d.text(((S-w)/2,78),kind,font=f,fill="white")
    im.save("tex/"+out)
badge("tick",TEAL,"b_tick.png");badge("?",(217,140,22),"b_q.png");badge("!",RED,"b_warn.png");badge("shield",(217,140,22),"b_shield.png")
print("badges ok")
