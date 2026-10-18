"""Build the C4 walkthrough from the runtime modules and saved experiment report."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def md(text):
    return {"cell_type":"markdown","source":text.splitlines(True),"metadata":{}}


def code(text):
    return {"cell_type":"code","source":text.splitlines(True),"metadata":{},"execution_count":None,"outputs":[]}


def build():
    cells=[
        md('''# CedarBridge Learning Studio
## C4 Custom ReAct Agent with Configurable Personas
EECE 503P/798S · Agentic Systems · Fall 2026

This project extends [C3](https://github.com/Jiany-S/C3) with a manually written LangGraph loop, two role-specific personas, and controlled live API experiments. The business PDF and summary are reused unchanged. The C3 submission remains separate.

Run from the complete C4 project folder with Python 3.11+ and `requirements-dev.txt` installed. The notebook imports and displays the same code used by the app. Its default execution reads saved real API evidence and runs offline tests; it does not make paid requests or launch a server. Live requests and UI launch are opt-in.

## 1 Use case
**Goal:** help students choose coaching, estimate published-price costs, and request staff follow-up or record feedback. **Audience:** university students working on their own software projects.

**Tools:** `lookup_service`, `calculate_quote`, `record_customer_interest`, and `record_feedback`. The first two add read/calculation actions to C3's recording tools. Quotes are planning estimates, not availability or booking confirmations.

**Constraints:** only published business facts; no calendar, email sender, payments, university authority, grade guarantees, or ghostwriting. Records are local JSONL. Conversation memory covers recent messages within one session.'''),
        code('''from pathlib import Path
import inspect, json, os, subprocess, sys
from dataclasses import asdict
from IPython.display import display, Markdown, Code
from dotenv import load_dotenv
import pandas as pd
load_dotenv('.env', override=False)
from personas import PERSONAS, PromptOptions
from prompts import INSTRUCTIONS, EXAMPLES, build_messages
from tools import load_business, Tools, TOOL_SCHEMAS
from model import OpenAIModel
from react_agent import ReActAgent, parse_final
knowledge=load_business()
display(Markdown(Path('me/business_summary.txt').read_text(encoding='utf-8')))'''),
        md('''## 2 Persona design and matching configuration
Mira guides service selection; Sami reviews a technical blocker and preparation needs. Both use the same factual sources, permissions, and tools. Tone and task emphasis change through the persona prompt. Temperature and penalties tune generation but do not create expertise or guarantee a particular tone.'''),
        code('''for key,p in PERSONAS.items():
    display(Markdown(f"### {p.name} — {p.role}\\n" + p.traits.replace('\\n','  \\n')))
    print(json.dumps(p.generation.options(),indent=2))'''),
        md('''## 3 Dedicated instructions and worked examples
Persona describes who the assistant is. These instructions define the input, output, workflow, quantities, missing fields, and action boundaries. Each numbered instruction has one operational purpose. The examples are illustrative formats, not claimed executions.'''),
        code('''print(INSTRUCTIONS)
print(EXAMPLES)
display(Code(inspect.getsource(build_messages),language='python'))'''),
        md('''## 4 Manual ReAct graph
Only LangGraph's `StateGraph`, nodes, edges, and conditional routing are used. There is no prebuilt executor, `create_react_agent`, `ToolNode`, or built-in agent runner.

`model → act → observe → model` repeats when native tool calls are present. A response without calls goes to `finalize`, which parses the required JSON. Invalid final formatting goes through `repair`; the step budget bounds the entire turn. The model decides which action to request; Python validates and executes it. Brief public decision summaries explain results without exposing or claiming access to private chain-of-thought.'''),
        code('''class NoNetworkModel:
    mode='mock'
    def complete(self,*args):
        raise RuntimeError('Graph inspection does not call a model.')
graph_agent=ReActAgent(NoNetworkModel(),log_dir=Path('tmp/notebook_graph'))
print(graph_agent.graph.get_graph().draw_mermaid())
for method in [ReActAgent.build_graph,ReActAgent.model_node,ReActAgent.next_node,
               ReActAgent.action_node,ReActAgent.observation_node,parse_final]:
    display(Code(inspect.getsource(method),language='python'))'''),
        md('''## 5 Tools and returned observations
The function schemas are supplied both in the system prompt and the model's tool declarations. Tool results use the original `tool_call_id`. Contact provenance, argument types, sizes, and storage errors are checked in Python. Success is taken from the returned observation, not inferred from a requested call.'''),
        code('''print(json.dumps(TOOL_SCHEMAS,indent=2))
display(Code(inspect.getsource(Tools.execute),language='python'))
display(Code(inspect.getsource(Tools.calculate_quote),language='python'))'''),
        md('''## 6 Actual multi-action example
The following is a saved real API trial, not an offline simulation. It shows the actual requested arguments, successful observations, and final reply. `trials/` contains the other conditions and repetitions, including failures.'''),
        code('''example=json.loads(Path('evidence/experiments/trials/mira_default__team_quote__1.json').read_text(encoding='utf-8'))
for trace in example['traces']:
    for event in trace['events']:
        print(event['tool'],event['arguments'])
        print(json.dumps(event['observation'],indent=2))
    print('Final answer:',trace['answer'])
    print('Model calls:',trace['steps'],'| Error:',trace['error'] or 'none')'''),
        md('''## 7 Experiment design
The final matrix has 12 setups × 8 fixed scenarios × 2 repetitions = 192 live trials. A lead scenario contains two turns. All setups use the same base model and factual sources. Scenario order is shuffled with a recorded seed.

The study compares both persona bundles, private CoT-style prompting versus the direct condition, worked examples versus zero-shot, system versus in-message operational instructions, detailed versus reduced instructions, and changes to temperature, frequency penalty, presence penalty, token limit, and top-p. The top-p pair holds temperature at 1; other parameter ablations change one setting relative to Mira.

The protocol and safety constraints remain system-level in every condition. Top-k is unsupported by Chat Completions and is not sent. CoT-style prompting is a wording ablation; public logs do not prove internal reasoning. The recorded source snapshot and exact settings make the conditions inspectable.'''),
        code('''from experiments import setups,CASES
display(pd.DataFrame([{'setup':s.name,'persona':s.persona,**s.generation.options(),
                      **asdict(s.prompt),'changed':s.changed} for s in setups()]))
print('Scenarios:',', '.join(c['id'] for c in CASES))'''),
        md('''## 8 Results and limitations
The analysis uses saved real executions. It separates functional checks from subjective naturalness. The original runs and scores remain unchanged; a separate scoring revision corrects a typographic-apostrophe false failure. The first development run is retained for comparison.'''),
        code('''display(Markdown(Path('docs/experiment_results.md').read_text(encoding='utf-8')))
display(pd.read_csv('evidence/comparison.csv'))
display(Markdown(Path('docs/new_scenarios.md').read_text(encoding='utf-8')))'''),
        md('''## 9 Automated verification
These tests exercise actual LangGraph transitions and local functions with scripted model outputs, including tool errors, memory, exact observations, deduplication, limits, and final-answer parsing. They establish orchestration behavior, not live model quality.'''),
        code('''result=subprocess.run([sys.executable,'-m','pytest','tests','-q'],capture_output=True,text=True)
print(result.stdout)
if result.returncode: print(result.stderr)
assert result.returncode==0'''),
        md('''## 10 Optional live execution
Configure a key locally in `.env`. Set `RUN_LIVE=true` to run this one example with real API calls. Repeating the full matrix is a separate CLI command so Run All does not silently repeat paid experiments. The fresh-kernel verification disables these flags.'''),
        code('''if os.getenv('RUN_LIVE','false').lower()=='true':
    live=ReActAgent(OpenAIModel(),persona='mira')
    reply,trace=live.respond('What does Prototype Clinic cost and how long is it?',return_trace=True)
    print(reply)
    display(trace['events'])
else:
    print('Live calls disabled. Saved real API trials are shown above.')'''),
        md('''## 11 Gradio interface
The interface lets the user choose a persona, adjust generation/prompt settings, chat, and inspect actual actions and observations. Switching personas clears the conversation and restores that persona's defaults. Each callback receives only its session's history.'''),
        code('''from app import build_demo,THEME,CSS
if os.getenv('RUN_UI','false').lower()=='true':
    demo=build_demo()
    demo.queue().launch(server_name='127.0.0.1',server_port=7861,share=False,
                        prevent_thread_lock=True,theme=THEME,css=CSS)
else:
    print('Notebook server launch disabled. Run python app.py for the local interface.')'''),
        md('## 12 Reflection\n\n' + (ROOT/'docs/reflection.md').read_text(encoding='utf-8').replace('# Reflection\n\n','')),
        md('''## 13 References
- C4 assignment, chapter notes, and lecture deck supplied with the course.
- [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api).
- [OpenAI Chat Completions parameters](https://developers.openai.com/api/reference/python/resources/chat/subresources/completions/methods/create).
- [GPT 4.1 mini model documentation](https://developers.openai.com/api/docs/models/gpt-4.1-mini).

The complete requirement mapping, strict self-assessment, and remaining limits are in `docs/self_assessment.md`.'''),
    ]
    for i,cell in enumerate(cells):cell['id']=f'c4-{i:02d}'
    nb={'cells':cells,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},
        'language_info':{'name':'python','version':'3.11'}},'nbformat':4,'nbformat_minor':5}
    (ROOT/'react_agent.ipynb').write_text(json.dumps(nb,indent=1),encoding='utf-8')
    print('Built C4 notebook.')


if __name__=='__main__':build()
