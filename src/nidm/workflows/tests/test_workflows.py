# from .. import ProcessSpecification, ProcessExecution
#
#
# def test_processspec(tmpdir):
#     #create new nidm-experiment document with project
#     proc = ProcessSpecification()
#
#     tmpdir.chdir()
#     #save a turtle file
#     with open("test.ttl",'w') as f:
#         f.write(proc.serializeTurtle())
#
#     #save a DOT graph as PDF
#     proc.save_DotGraph("test.png", format="png")
#
#
# def test_processexec(tmpdir):
#     #create new nidm-experiment document with project
#     proc = ProcessExecution()
#
#     tmpdir.chdir()
#     #save a turtle file
#     with open("test.ttl", 'w') as f:
#         f.write(proc.serializeTurtle())
#
#     #save a DOT graph as PDF
#     proc.save_DotGraph("test.png", format="png")
#
#
