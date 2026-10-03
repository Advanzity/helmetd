from PIL import Image, ImageDraw
import numpy as np,pathlib
p=pathlib.Path('outputs/shelby-ride/public/assets');rng=np.random.default_rng(15)
# PBR microgeometry maps for tire, fabric and material roughness.
n=512;noise=rng.normal(0,1,(n,n));yy,xx=np.mgrid[:n,:n];weave=(np.sin(xx*np.pi/2)*np.sin(yy*np.pi/2));h=noise*.09+weave*.15
for name,field in [('fabric',h),('rubber',noise*.11)]:
 gy,gx=np.gradient(field);norm=np.stack([-gx,-gy,np.ones_like(gx)],-1);norm/=np.linalg.norm(norm,axis=-1,keepdims=True);Image.fromarray(np.uint8((norm*.5+.5)*255)).save(p/(name+'-normal.png'))
 rough=np.clip(.74+noise*.04,0,1);Image.fromarray(np.uint8(rough*255)).save(p/(name+'-roughness.png'))
# architectural atlas with mortar, panels, lower glass storefront and rooftop membrane
im=Image.new('RGB',(1024,1024),(119,111,99));dr=ImageDraw.Draw(im)
for y in range(0,1024,32):
 for x in range(-64,1024,128):
  off=64 if y//32%2 else 0;c=int(rng.integers(-13,13));dr.rectangle((x+off+2,y+2,x+off+125,y+29),fill=(131+c,113+c,92+c))
im.save(p/'brick.jpg',quality=92)
im=Image.new('RGB',(512,512),(44,47,47));a=np.array(im).astype(float)+rng.normal(0,4,(512,512,1));Image.fromarray(np.uint8(np.clip(a,0,255))).save(p/'roof.jpg',quality=90)
