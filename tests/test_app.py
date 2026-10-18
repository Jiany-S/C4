from app import build_demo


def test_interface_builds():
    app=build_demo()
    assert app.config['title']=='CedarBridge | C4 Personas'
    assert any(c['type']=='chatbot' for c in app.config['components'])
    assert any(c['type']=='radio' for c in app.config['components'])
    app.close()
