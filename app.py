"""Local Gradio demonstration for CedarBridge's two configurable agents."""
from dataclasses import replace
import os
import gradio as gr
from dotenv import load_dotenv
from model import ModelError, OpenAIModel
from personas import PERSONAS, PromptOptions
from react_agent import ReActAgent
from tools import ROOT

CSS = """
.gradio-container {max-width:1180px !important; margin:auto;}
#intro {padding:8px 0 12px; margin-bottom:8px;}
#intro h1 {font-size:32px; letter-spacing:-1px; margin:4px 0 8px;}
#intro p {max-width:720px; line-height:1.4; opacity:.8;}
.studio-label {font-size:11px; letter-spacing:2px; color:#17634b; font-weight:700;}
.dark .studio-label {color:#9fcbb8;}
#role-info {min-height:120px; padding:12px 0;}
#chat-panel {border-radius:14px;}
footer {display:none !important;}
"""
THEME = gr.themes.Soft(primary_hue="emerald", neutral_hue="slate", font=["Segoe UI", "Arial", "sans-serif"])


def role_description(persona):
    p = PERSONAS[persona]
    text = ("Choose a coaching service and find a manageable next step." if persona == "mira" else
            "Clarify your blocker, scope, and testing needs before choosing coaching.")
    return f"### {p.name} · {p.role}\n{text}"


def build_demo(model=None, log_dir=None):
    load_dotenv(ROOT / ".env")
    def chat(message, history, persona, temperature, top_p, frequency, presence, tokens, cot, few_shot, placement):
        history = history or []
        if not message or not message.strip():
            return "", history, {}
        try:
            generation = replace(PERSONAS[persona].generation, model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
                temperature=temperature, top_p=top_p, frequency_penalty=frequency,
                presence_penalty=presence, max_completion_tokens=int(tokens))
            agent = ReActAgent(model if model is not None else OpenAIModel(), persona=persona, generation=generation,
                options=PromptOptions(cot=cot, few_shot=few_shot, instruction_role=placement), log_dir=log_dir)
            answer, trace = agent.respond(message, history, return_trace=True)
            visible = {k:v for k,v in trace.items() if k not in {"requests", "history"}}
        except ModelError as exc:
            answer = str(exc)
            visible = {"error": answer}
        except (OSError, ValueError):
            answer = "The assistant could not start. Check the local API key, business files, and settings."
            visible = {"error": answer}
        return "", [*history, {"role":"user","content":message},{"role":"assistant","content":answer}], visible

    with gr.Blocks(title="CedarBridge | C4 Personas", analytics_enabled=False) as demo:
        gr.HTML('<header id="intro"><div class="studio-label">CEDARBRIDGE LEARNING STUDIO</div>'
                '<h1>Find your next step.</h1><p>Two perspectives on your project. Choose a service guide '
                'for a welcoming introduction, or a project reviewer for a focused assessment.</p></header>')
        with gr.Tab("Conversation"):
            with gr.Row():
                with gr.Column(scale=1,min_width=260):
                    persona = gr.Radio([("Mira · Service guide","mira"),("Sami · Project reviewer","sami")], value="mira", label="Your advisor")
                    info = gr.Markdown(role_description("mira"), elem_id="role-info")
                    gr.Markdown("**Coaching services**\n\nProject Clarity · scope an idea\n\nPrototype Clinic · debug and test\n\nTeam Sprint · plan together")
                    gr.DownloadButton("Business profile",value=str(ROOT/"me/about_business.pdf"),size="sm")
                    with gr.Accordion("Model and prompt settings",open=False):
                        temperature=gr.Slider(0,1.5,value=.6,step=.1,label="Temperature")
                        top_p=gr.Slider(.1,1,value=1,step=.1,label="Top p")
                        frequency=gr.Slider(0,1.5,value=0,step=.1,label="Frequency penalty")
                        presence=gr.Slider(0,1.5,value=.2,step=.1,label="Presence penalty")
                        tokens=gr.Slider(100,1200,value=650,step=10,label="Completion token limit")
                        cot=gr.Checkbox(value=False,label="Private step-by-step prompt")
                        few=gr.Checkbox(value=True,label="Worked examples")
                        placement=gr.Radio(["system","user"],value="system",label="Operational instruction placement")
                        gr.Markdown("Start a new conversation for a clean comparison. Top-k is not supported by this API.")
                with gr.Column(scale=3,min_width=350):
                    chatbot=gr.Chatbot(label="Conversation",height=350,elem_id="chat-panel",
                        placeholder="Tell your advisor where you’re stuck, or choose an example below.")
                    message=gr.Textbox(label="Message",placeholder="Tell us about your project, or ask about a service.",lines=2,max_lines=5)
                    with gr.Row():
                        send=gr.Button("Send",variant="primary")
                        clear=gr.Button("New conversation")
                    gr.Examples([["My API tests fail intermittently. Which service fits, and what should I prepare?"],
                        ["Compare Team Sprint with Prototype Clinic for five students, then quote two Team Sprint sessions."],
                        ["Please ask staff to contact me about Prototype Clinic."],
                        ["Feedback: please add evening sessions."]],inputs=message)
                    with gr.Accordion("Actions and observations",open=False):
                        trace=gr.JSON(label="Actual result for the latest turn")
                    gr.Markdown("Fictional classroom business. Follow-up requests and feedback are saved locally. "
                                "No appointment or email is sent. Use invented contact details; messages go to OpenAI.")
            inputs=[message,chatbot,persona,temperature,top_p,frequency,presence,tokens,cot,few,placement]
            message.submit(chat,inputs,[message,chatbot,trace],api_name="chat",concurrency_limit=4)
            send.click(chat,inputs,[message,chatbot,trace],api_name=False,concurrency_limit=4)
            clear.click(lambda:("",[],{}),outputs=[message,chatbot,trace],api_name=False)
            def change_persona(key):
                g=PERSONAS[key].generation
                return "",[],{},role_description(key),g.temperature,g.top_p,g.frequency_penalty,g.presence_penalty,g.max_completion_tokens,False,True,"system"
            persona.change(change_persona,persona,[message,chatbot,trace,info,temperature,top_p,frequency,presence,tokens,cot,few,placement],api_name=False)
        with gr.Tab("Experiment results"):
            path=ROOT/"docs/experiment_results.md"
            gr.Markdown(path.read_text(encoding="utf-8") if path.exists() else "Results will appear after the controlled experiment run is complete.")
    return demo


if __name__ == "__main__":
    build_demo().queue().launch(server_name="127.0.0.1",server_port=7861,share=False,theme=THEME,css=CSS)
