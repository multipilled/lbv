"""RenderDoc replay script (run with tools/lab/rdreplay.py): the colour target at the end of each group of draws.
env: RD_CAPTURE=<.rdc>, RD_OUT=<folder>. Writes <RD_OUT>/passes.txt (one line per group of consecutive draws with the
same outputs: events, draws, indices, targets) and g<NNN>-e<event>.png (the first colour target after the group's last
draw). Draws through shader interlock have no colour output (they write the target as a storage image)."""
import os
import traceback

OUT = os.environ['RD_OUT']
os.makedirs(OUT, exist_ok=True)
log = open(os.path.join(OUT, 'passes.txt'), 'w')
try:
    import renderdoc as rd
    cap = rd.OpenCaptureFile()
    cap.OpenFile(os.environ['RD_CAPTURE'], '', None)
    res, ctrl = cap.OpenCapture(rd.ReplayOptions(), None)
    tex = {t.resourceId: t for t in ctrl.GetTextures()}
    draws = []

    def walk(acts):
        for a in acts:
            if a.flags & rd.ActionFlags.Drawcall:
                draws.append(a)
            walk(a.children)
    walk(ctrl.GetRootActions())
    groups = []
    for d in draws:
        key = (tuple(str(o) for o in d.outputs if o != rd.ResourceId.Null()), str(d.depthOut))
        if groups and groups[-1][0] == key:
            groups[-1][1].append(d)
        else:
            groups.append((key, [d]))
    for gi, (key, ds) in enumerate(groups):
        last = ds[-1]
        outs = [o for o in last.outputs if o != rd.ResourceId.Null()]
        desc = ['%s %dx%d %s' % (o, tex[o].width, tex[o].height, tex[o].format.Name()) if o in tex else str(o)
                for o in outs]
        log.write('group %d: events %d-%d draws %d indices %d out %s depth %s\n' % (
            gi, ds[0].eventId, last.eventId, len(ds), sum(d.numIndices for d in ds), desc, last.depthOut))
        if outs:
            ctrl.SetFrameEvent(last.eventId, True)
            s = rd.TextureSave()
            s.resourceId = outs[0]
            s.destType = rd.FileType.PNG
            s.alpha = rd.AlphaMapping.Discard
            ctrl.SaveTexture(s, os.path.join(OUT, 'g%03d-e%d.png' % (gi, last.eventId)))
    ctrl.Shutdown()
    cap.Shutdown()
except Exception:
    log.write(traceback.format_exc())
log.close()
os._exit(0)
