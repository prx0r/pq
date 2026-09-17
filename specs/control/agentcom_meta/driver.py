from __future__ import annotations
import json,os,shlex,subprocess,urllib.request
from dataclasses import dataclass

class DriverError(RuntimeError):pass

@dataclass
class CommandLLMDriver:
    command:str
    model:str="command-driver"
    name:str="command"
    timeout_s:float=180.0
    def call(self,prompt:str)->dict:
        r=subprocess.run(shlex.split(self.command),input=prompt,text=True,capture_output=True,timeout=self.timeout_s)
        if r.returncode!=0:raise DriverError((r.stderr or r.stdout)[-1000:])
        try:return json.loads(r.stdout)
        except Exception as e:raise DriverError(f"invalid-json:{e}")

@dataclass
class OpenAICompatibleDriver:
    base_url:str
    api_key:str
    model:str
    name:str="openai-compatible"
    timeout_s:float=180.0
    def call(self,prompt:str)->dict:
        body=json.dumps({"model":self.model,"messages":[{"role":"user","content":prompt}],"response_format":{"type":"json_object"}}).encode()
        req=urllib.request.Request(self.base_url.rstrip("/")+"/chat/completions",data=body,headers={"Authorization":"Bearer "+self.api_key,"Content-Type":"application/json"})
        with urllib.request.urlopen(req,timeout=self.timeout_s) as resp:d=json.loads(resp.read())
        content=d["choices"][0]["message"]["content"]
        return json.loads(content)
