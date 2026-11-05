from __future__ import annotations
import base64, hmac, io, json, math, os, re, shutil, struct, subprocess, threading, time, wave, zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from flask import Flask, Response, abort, jsonify, request, send_file
from PIL import Image, ImageOps, ImageDraw, ImageFont, ImageEnhance
import imageio_ffmpeg

app=Flask(__name__)
DATA=Path('/tmp/automoto')
PHOTOS=DATA/'photos'
OUT=DATA/'output'
for d in (PHOTOS,OUT): d.mkdir(parents=True,exist_ok=True)
KEY=os.environ.get('STUDIO_ACCESS_KEY','')
if len(KEY)<20:raise RuntimeError('Missing secure STUDIO_ACCESS_KEY')
NAMES=('hero','headlights','profile','wheel','rear')
LOCK=threading.Lock()
JOB={'status':'idle','message':'Upload a ZIP of five original BMW photos.','lines':[],'video':None}
PLAN={
16:[('text','AFTER HOURS'),('shot','hero'),('text','BUILT'),('shot','headlights'),('text','FOR THE'),('shot','profile'),('text','NIGHT'),('text','THE NIGHT IS YOURS')],
28:[('text','A STUDY IN'),('text','SHADOW'),('text','AND SPEED'),('shot','hero'),('text','BUILT'),('shot','headlights'),('text','FOR'),('shot','profile'),('text','THE'),('shot','wheel'),('text','NIGHT'),('shot','rear'),('text','NOIR'),('text','THE NIGHT IS YOURS')]
}
def authentication():
    header=request.headers.get('Authorization','')
    if not header.startswith('Basic '):return False
    try:user,password=base64.b64decode(header[6:],validate=True).decode().split(':',1)
    except Exception:return False
    return hmac.compare_digest(user,'studio') and hmac.compare_digest(password,KEY)
@app.before_request
def protect():
    if request.path=='/healthz':return
    if not authentication():
        r=Response('Private AutoMoto studio',401)
        r.headers['WWW-Authenticate']='Basic realm="AutoMoto Studio"'
        return r
    if request.method=='POST':
        if request.headers.get('X-AutoMoto-Request')!='1':abort(403)
        origin=request.headers.get('Origin')
        if origin and urlparse(origin).netloc!=request.host:abort(403)
@app.after_request
def headers(resp):
    resp.headers['X-Content-Type-Options']='nosniff'
    resp.headers['X-Frame-Options']='DENY'
    resp.headers['Cache-Control']='no-store'
    return resp
@app.get('/healthz')
def health():return jsonify(ok=True,app='automoto-cloud')
@app.get('/api/status')
def status():
    with LOCK:j={**JOB,'lines':list(JOB['lines'])}
    return jsonify(job=j,photos=[n for n in NAMES if (PHOTOS/(n+'.jpg')).is_file()])
@app.post('/api/upload')
def upload():
    if not 0<(request.content_length or 0)<=25_000_000:return jsonify(error='ZIP must be under 25 MB'),413
    try:
        with zipfile.ZipFile(io.BytesIO(request.get_data(cache=False))) as z:
            selected={}
            for name in NAMES:
                matches=[i for i in z.infolist() if not i.is_dir() and i.filename.replace('\\','/').split('/')[-1]==name+'.jpg']
                if len(matches)!=1:raise ValueError('Expected exactly one '+name+'.jpg')
                entry=matches[0]
                if entry.file_size>7_000_000:raise ValueError('Image too large: '+name)
                raw=z.read(entry)
                if len(raw)>7_000_000:raise ValueError('Image too large: '+name)
                with Image.open(io.BytesIO(raw)) as photo:
                    if photo.width*photo.height>24_000_000:raise ValueError('Image dimensions too large')
                    p=ImageOps.exif_transpose(photo).convert('RGB')
                    p.thumbnail((1400,2400))
                    b=io.BytesIO();p.save(b,'JPEG',quality=88)
                    selected[name]=b.getvalue()
        with LOCK:
            if JOB['status']=='running':return jsonify(error='Render in progress'),409
            for name,data in selected.items():(PHOTOS/(name+'.jpg')).write_bytes(data)
        return jsonify(ok=True,imported=len(selected),note='Render free storage is temporary')
    except (ValueError,zipfile.BadZipFile,OSError,Image.DecompressionBombError) as exc:
        return jsonify(error=str(exc)[:180]),400
def log(line):
    with LOCK:
        JOB['lines'].append(str(line)[:200])
        JOB['lines']=JOB['lines'][-45:]
def make_frame(kind,value,size,out):
    w,h=size
    if kind=='shot':
        with Image.open(PHOTOS/(value+'.jpg')) as src:
            src=ImageOps.fit(src.convert('RGB'),(w,h),method=Image.Resampling.LANCZOS)
            src=ImageEnhance.Color(src).enhance(.75)
            src.save(out,'JPEG',quality=89)
    else:
        img=Image.new('RGB',(w,h),(5,5,7))
        draw=ImageDraw.Draw(img)
        fontpath='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
        size0=int(w*.15)
        while size0>14:
            font=ImageFont.truetype(fontpath,size0) if Path(fontpath).exists() else ImageFont.load_default()
            bb=draw.textbbox((0,0),value,font=font)
            if bb[2]-bb[0]<w*.86:break
            size0-=3
        draw.text((w//2,h//2),value,font=font,anchor='mm',fill=(190,190,190))
        img.save(out,'JPEG',quality=90)
def make_audio(path,seconds):
    sr=16000
    with wave.open(str(path),'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(sr)
        for s in range(seconds):
            data=bytearray()
            for j in range(sr):
                t=s+j/sr
                drop=6 if seconds==28 else 2
                if t<drop:v=.013*math.sin(2*math.pi*55*t)
                else:
                    phase=(t-drop)%.5
                    v=.22*math.sin(2*math.pi*(74-28*phase)*phase)*math.exp(-16*phase)+.08*math.sin(2*math.pi*55*t)
                envelope=min(1,t/.2,max(0,(seconds-t)/.5))
                data+=struct.pack('<h',int(max(-.9,min(.9,v*envelope))*32767))
            wav.writeframes(data)
def run_render(seconds,preview):
    ff=imageio_ffmpeg.get_ffmpeg_exe()
    w,h,fps=(360,640,24) if preview else (1080,1920,30)
    folder=DATA/('working_'+str(int(time.time())))
    folder.mkdir(exist_ok=True)
    try:
        cuts=[]
        for i,(kind,value) in enumerate(PLAN[seconds]):
            still=folder/('frame%02d.jpg'%i)
            make_frame(kind,value,(w,h),still)
            clip=folder/('clip%02d.mp4'%i)
            zoom="min(zoom+0.0004,1.04)" if kind=='shot' else '1.0'
            vf="zoompan=z='%s':d=%d:s=%dx%d:fps=%d,format=yuv420p"%(zoom,2*fps,w,h,fps)
            subprocess.run([ff,'-loglevel','error','-y','-loop','1','-i',str(still),'-vf',vf,'-frames:v',str(2*fps),'-an','-c:v','libx264','-preset','ultrafast' if preview else 'veryfast','-crf','24','-pix_fmt','yuv420p',str(clip)],check=True,timeout=150)
            cuts.append(clip);log('Cut %d/%d: %s'%(i+1,len(PLAN[seconds]),value))
        playlist=folder/'segments.txt'
        playlist.write_text(''.join("file '%s'\n"%p for p in cuts))
        wav=folder/'beat.wav';make_audio(wav,seconds)
        stamp=datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        output=OUT/('AutoMoto_NOIR_%ds_%s%s.mp4'%(seconds,stamp,'_PREVIEW' if preview else ''))
        subprocess.run([ff,'-loglevel','error','-y','-f','concat','-safe','0','-i',str(playlist),'-i',str(wav),'-c:v','copy','-c:a','aac','-t',str(seconds),'-movflags','+faststart',str(output)],check=True,timeout=150)
        if output.stat().st_size<70000:raise RuntimeError('MP4 output unexpectedly small')
        for stale in sorted(OUT.glob('*.mp4'),key=lambda p:p.stat().st_mtime,reverse=True)[3:]:stale.unlink(missing_ok=True)
        with LOCK:JOB.update(status='done',video=output.name,message='MP4 ready. Download before this free instance sleeps.')
    except Exception as exc:
        log('ERROR '+str(exc))
        with LOCK:JOB.update(status='failed',video=None,message='Render failed: '+str(exc)[:160])
    finally:shutil.rmtree(folder,ignore_errors=True)
@app.post('/api/render')
def start():
    body=request.get_json(silent=True) or {}
    seconds=body.get('seconds',28);preview=body.get('preview',True)
    if type(seconds)!=int or seconds not in PLAN or type(preview)!=bool:return jsonify(error='Bad settings'),400
    if any(not (PHOTOS/(n+'.jpg')).is_file() for n in NAMES):return jsonify(error='Import all five BMW photos first. No fake demo fallback.'),400
    with LOCK:
        if JOB['status']=='running':return jsonify(error='A job is already running'),409
        JOB.update(status='running',message='Rendering...',lines=[],video=None)
    threading.Thread(target=run_render,args=(seconds,preview),daemon=True).start()
    return jsonify(ok=True),202
@app.get('/video/<name>')
def get_video(name):
    if not re.fullmatch(r'AutoMoto_NOIR_(16|28)s_\d{8}_\d{6}(_PREVIEW)?\.mp4',name):abort(404)
    file=OUT/name
    if not file.is_file():abort(404)
    return send_file(file,conditional=True,mimetype='video/mp4')
HTML='''<!doctype html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AutoMoto Cloud Studio</title><style>
*{box-sizing:border-box}body{background:#080a0e;color:#fafafa;font:15px system-ui;margin:0;line-height:1.5}.shell{max-width:960px;padding:30px 20px 90px;margin:auto}.top{display:flex;justify-content:space-between;border-bottom:1px solid #282b31;padding-bottom:18px}.eyebrow{color:#99a2b0;font:11px system-ui;letter-spacing:.22em;text-transform:uppercase}h1{font-size:clamp(38px,7vw,74px);line-height:1.05;letter-spacing:-.06em;margin:38px 0 12px}.muted{color:#adb4bd}.grid{display:grid;grid-template-columns:1.3fr 1fr;gap:17px;margin-top:34px}.card{padding:22px;background:#12141b;border:1px solid #30343d;border-radius:16px;margin-bottom:16px}h2{margin:0 0 12px}label{display:block;margin:13px 0 5px}.ctl{display:block;width:100%;padding:13px;background:#1c2029;color:white;border:1px solid #454955;border-radius:8px}button{background:#eceef2;color:#101216;font-weight:800;border:0;border-radius:8px;padding:12px 16px;cursor:pointer;margin:13px 0}button:disabled{opacity:.5}pre{white-space:pre-wrap;background:#08090d;color:#d1d9e4;padding:12px;border-radius:8px;max-height:240px;overflow:auto;font-size:12px}a{color:#d5e4fb}video{max-width:200px;width:100%;border-radius:9px}@media(max-width:680px){.grid{grid-template-columns:1fr}}</style></head><body><div class="shell"><div class="top"><div><div class="eyebrow">AUTOMOTO / CINEMATIC PRODUCTION</div><strong>STUDIO.</strong></div><div class="eyebrow">PRIVATE BETA</div></div><h1>AFTER DARK.<br>BEFORE VIRAL.</h1><p class="muted">One BMW. Five original angles. Deliberate edits aligned to a 120 BPM soundtrack. Reference-inspired rather than re-uploaded.</p><div class="grid"><main><div class="card"><div class="eyebrow">01 / PHOTOGRAPHS</div><h2>Import BMW kit</h2><p class="muted">ZIP exactly five JPGs from your local V6 <code>runway_photos</code>: hero, headlights, profile, wheel, rear.</p><input class="ctl" type="file" id="file" accept=".zip"><button id="upload">IMPORT ZIP</button><div id="uploadNote" class="muted"></div></div><div class="card"><div class="eyebrow">02 / CREATE</div><h2>Render original Reel</h2><label>Duration</label><select id="seconds" class="ctl"><option value="28">28 seconds</option><option value="16">16 seconds</option></select><label>Quality</label><select id="quality" class="ctl"><option value="preview">360 × 640 test — recommended</option><option value="full">1080 × 1920 — resource intensive</option></select><button id="create">GENERATE REEL</button><p class="muted">Animated photographs, not physically moving cars. Render Free storage is temporary.</p></div><div class="card"><div class="eyebrow">03 / PROGRESS</div><div id="status">Ready.</div><pre id="log"></pre></div></main><aside><div class="card"><div class="eyebrow">MEDIA STATUS</div><h2 id="photoCount">0 / 5</h2><p class="muted">matching BMW photos uploaded for this session</p></div><div class="card"><div class="eyebrow">MP4 OUTPUT</div><div id="output">No Reel generated yet.</div></div><div class="card"><div class="eyebrow">SAFETY</div><p class="muted">Password protected. Download output before Render sleeps. Original music only; no copyrighted Instagram content, and no unverified trend claims.</p></div></aside></div></div><script>
const $=id=>document.getElementById(id);
async function api(path,opts={}){let r=await fetch(path,{...opts,headers:{'X-AutoMoto-Request':'1',...(opts.headers||{})}});let j=await r.json();if(!r.ok)throw Error(j.error||'Request failed');return j}
$('upload').onclick=async()=>{let f=$('file').files[0];if(!f)return;$('upload').disabled=true;try{let v=await api('/api/upload',{method:'POST',headers:{'Content-Type':'application/zip'},body:f});$('uploadNote').textContent='Imported '+v.imported+' photos';poll()}catch(e){$('uploadNote').textContent=e.message}finally{$('upload').disabled=false}};
$('create').onclick=async()=>{try{await api('/api/render',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({seconds:+$('seconds').value,preview:$('quality').value==='preview'})});poll()}catch(e){$('status').textContent=e.message}};
async function poll(){try{let s=await api('/api/status');$('photoCount').textContent=s.photos.length+' / 5';$('status').textContent=s.job.message;$('log').textContent=s.job.lines.join('\n');$('create').disabled=s.job.status==='running';if(s.job.video){let v=s.job.video,u='/video/'+encodeURIComponent(v);$('output').innerHTML='';let video=document.createElement('video');video.src=u;video.controls=true;$('output').append(video);let a=document.createElement('a');a.href=u;a.download=v;a.textContent=' DOWNLOAD MP4';a.style.display='block';$('output').append(a)}}catch(e){$('status').textContent=e.message}}
poll();setInterval(poll,4000);
</script></body></html>'''
@app.get('/')
def home():return Response(HTML,mimetype='text/html')
if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.environ.get('PORT','10000')),threaded=True)
