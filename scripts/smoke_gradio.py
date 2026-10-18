"""Real local HTTP and queue checks with a clearly scripted model boundary."""
from pathlib import Path
import sys
import tempfile
import urllib.request
import json

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import build_demo


def run():
    class Probe:
        mode="mock"
        def complete(self,messages,generation):
            return {"message":{"role":"assistant","content":json.dumps({
                "decision_summary":"Scripted startup probe.","answer":"MOCK HTTP probe completed."})},"usage":{}}
    with tempfile.TemporaryDirectory(prefix="c4-smoke-") as temp:
        demo=build_demo(Probe(),log_dir=temp)
        try:
            _,url,_=demo.queue().launch(server_name="127.0.0.1",server_port=7862,share=False,
                prevent_thread_lock=True,quiet=True)
            with urllib.request.urlopen(url,timeout=20) as response:
                assert response.status==200
            from gradio_client import Client
            output=Client(url,verbose=False).predict("Startup probe",[],"mira",.6,1,0,.2,650,False,True,"system",api_name="/chat")
            assert "MOCK HTTP probe completed." in str(output)
            report={"mode":"real Gradio HTTP/queue with scripted model", "http":"PASS", "queued_callback":"PASS",
                    "output":output}
            (ROOT/'evidence/gradio_smoke.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
            print('PASS: Gradio HTTP and queue; callback used a mock model.')
        finally:
            demo.close()


if __name__=='__main__':run()
