"""Bounded authenticated read load against a disposable loopback FTBI fixture."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from http.cookiejar import CookieJar
import json
import math
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError,URLError
from urllib.parse import urlencode,urlsplit
from urllib.request import HTTPCookieProcessor,HTTPRedirectHandler,Request,build_opener,ProxyHandler


class LocalRedirects(HTTPRedirectHandler):
    def __init__(self,origin):
        parsed=urlsplit(origin)
        if parsed.scheme!="http" or parsed.hostname!="127.0.0.1" or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment or not parsed.port or not 1024<=parsed.port<=65535:
            raise ValueError("Only a numeric loopback test server is permitted.")
        self.origin=origin
    def redirect_request(self,request,fp,code,msg,headers,newurl):
        parsed=urlsplit(newurl)
        if f"{parsed.scheme}://{parsed.netloc}"!=self.origin:
            raise ValueError("Redirect left the disposable loopback server.")
        return super().redirect_request(request,fp,code,msg,headers,newurl)


def percentile(values,fraction):
    ordered=sorted(values)
    return round(ordered[max(0,math.ceil(len(ordered)*fraction)-1)],2) if ordered else None


def validate(port,requests,limit):
    if os.environ.get("FTBI_LOAD_TESTING")!="1": raise ValueError("Explicit disposable load-test opt-in required.")
    if not 1024<=port<=65535 or not 12<=requests<=240 or not 1<=limit<=20000: raise ValueError("Load-test bounds exceeded.")
    if len(os.environ.get("FTBI_DEMO_PASSWORD",""))<16: raise ValueError("Synthetic fixture password is required.")


def prepare(origin):
    # Proxy use is disabled; every redirect is confined to the numeric loopback origin.
    jar=CookieJar();opener=build_opener(ProxyHandler({}),HTTPCookieProcessor(jar),LocalRedirects(origin))
    for attempt in range(45):
        try:
            with opener.open(origin+"/health/ready/",timeout=2) as response:  # nosec B310
                if response.status==200: break
        except (URLError,OSError):
            if attempt==44: raise RuntimeError("Disposable server did not become ready.") from None
            time.sleep(1)
    with opener.open(origin+"/login/",timeout=10) as response:  # nosec B310
        page=response.read(2*1024*1024)
    if b"FTBI Demonstration College" not in page: raise ValueError("Target is not the synthetic demonstration fixture.")
    token=next(cookie.value for cookie in jar if cookie.name=="csrftoken")
    body=urlencode({"username":"demo-chromium","password":os.environ["FTBI_DEMO_PASSWORD"],"csrfmiddlewaretoken":token}).encode()
    request=Request(origin+"/login/",data=body,headers={"Referer":origin+"/login/"})
    with opener.open(request,timeout=10) as response:  # nosec B310
        page=response.read(2*1024*1024)
    if b"Your academic workspace" not in page: raise RuntimeError("Synthetic login failed.")
    match=re.search(rb'href="/courses/([0-9]+)/"',page)
    if not match: raise RuntimeError("Synthetic enrolled course was not found.")
    return "; ".join(cookie.name+"="+cookie.value for cookie in jar),"/courses/"+match.group(1).decode()+"/"


def run(origin,cookie,course,requests,limit):
    routes=[("/",b"Your academic workspace"),(course,b"Learning demonstration"),("/catalog/",b"Course registration"),("/notifications/",b"Notification center")]
    stages=[]
    def probe(index):
        path,expected=routes[index%len(routes)];start=time.perf_counter();ok=False
        try:
            opener=build_opener(ProxyHandler({}),LocalRedirects(origin))
            request=Request(origin+path,headers={"Cookie":cookie,"User-Agent":"FTBI-disposable-load-check"})
            with opener.open(request,timeout=20) as response:  # nosec B310
                body=response.read(2*1024*1024+1)
                ok=response.status==200 and response.geturl()==origin+path and len(body)<=2*1024*1024 and expected in body
        except (HTTPError,URLError,OSError,ValueError): pass
        return (time.perf_counter()-start)*1000,ok
    for workers in [1,4,12]:
        started=time.perf_counter()
        with ThreadPoolExecutor(max_workers=workers) as pool: outcomes=list(pool.map(probe,range(requests)))
        seconds=time.perf_counter()-started;durations=[duration for duration,ok in outcomes];failures=sum(not ok for duration,ok in outcomes)
        stages.append({"concurrent_workers":workers,"requests":requests,"failures":failures,"elapsed_seconds":round(seconds,3),"requests_per_second":round(requests/seconds,2),"p50_ms":percentile(durations,.5),"p95_ms":percentile(durations,.95),"p99_ms":percentile(durations,.99),"max_ms":round(max(durations),2)})
    return {"format":"ftbi-synthetic-load-v1","scope":"One synthetic student; four authenticated read workflows; disposable loopback server; not production capacity acceptance.","p95_limit_ms":limit,"stages":stages,"accepted":all(stage["failures"]==0 and stage["p95_ms"]<=limit for stage in stages)}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--port",type=int,default=8766)
    parser.add_argument("--requests",type=int,default=120)
    parser.add_argument("--p95-limit-ms",type=int,default=10000)
    parser.add_argument("--output",default="load-report.json")
    args=parser.parse_args()
    try:
        validate(args.port,args.requests,args.p95_limit_ms)
        origin=f"http://127.0.0.1:{args.port}"
        cookie,course=prepare(origin)
        result=run(origin,cookie,course,args.requests,args.p95_limit_ms)
    except (ValueError,RuntimeError,URLError,OSError,StopIteration): result={"accepted":False,"error":"Disposable load setup failed; check the fixture and private server logs."}
    Path(args.output).write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,sort_keys=True))
    return 0 if result["accepted"] else 1


if __name__=="__main__": raise SystemExit(main())
