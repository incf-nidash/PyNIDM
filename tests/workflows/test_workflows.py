# from nidm.workflows import ProcessSpecification, ProcessExecution
#
#
# def test_processspec(monkeypatch, tmp_path):
#     #create new nidm-experiment document with project
#     proc = ProcessSpecification()
#
#     monkeypatch.chdir(tmp_path)
#     #save a turtle file
#     with open("test.ttl",'w', encoding="utf-8") as f:
#         f.write(proc.serializeTurtle())
#
#     #save a DOT graph as PDF
#     proc.save_DotGraph("test.png", format="png")
#
#
# def test_processexec(monkeypatch, tmp_path):
#     #create new nidm-experiment document with project
#     proc = ProcessExecution()
#
#     monkeypatch.chdir(tmp_path)
#     #save a turtle file
#     with open("test.ttl", 'w', encoding="utf-8") as f:
#         f.write(proc.serializeTurtle())
#
#     #save a DOT graph as PDF
#     proc.save_DotGraph("test.png", format="png")
