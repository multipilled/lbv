"""RenderDoc replay script (run with tools/lab/rdreplay.py): every action in an event range, with each draw's state.
env: RD_CAPTURE=<.rdc>, RD_OUT=<folder>, RD_EVENTS=<first>-<last>, optional RD_SAVE=<id>,<id> (resource numbers, e.g.
11829,11831: saved after each draw as e<event>-<id>.png). Writes <RD_OUT>/events.txt: per draw the indices, fragment
shader, pipeline, read-only and read-write resources (size, format), depth/stencil and blend state, and the post-VS
x/w, y/w, z/w ranges; and each texture a draw reads, once, as tex-<id>-rgb.png and tex-<id>-a.png (alpha kept)."""
import os
import struct
import traceback

OUT = os.environ['RD_OUT']
os.makedirs(OUT, exist_ok=True)
log = open(os.path.join(OUT, 'events.txt'), 'w')
try:
    import renderdoc as rd
    first, last = (int(x) for x in os.environ['RD_EVENTS'].split('-'))
    save_ids = [x for x in os.environ.get('RD_SAVE', '').split(',') if x]
    cap = rd.OpenCaptureFile()
    cap.OpenFile(os.environ['RD_CAPTURE'], '', None)
    res, ctrl = cap.OpenCapture(rd.ReplayOptions(), None)
    sf = ctrl.GetStructuredFile()
    tex = {t.resourceId: t for t in ctrl.GetTextures()}
    by_num = {str(t).split('::')[-1]: t for t in tex}
    acts = {}

    def walk(a):
        for x in a:
            acts[x.eventId] = x
            walk(x.children)
    walk(ctrl.GetRootActions())

    def num(rid):
        return str(rid).split('::')[-1]

    def name(rid):
        t = tex.get(rid)
        return '%s(%dx%d %s)' % (num(rid), t.width, t.height, t.format.Name()) if t else num(rid)

    def save(rid, path, alpha):
        s = rd.TextureSave()
        s.resourceId = rid
        s.destType = rd.FileType.PNG
        s.alpha = alpha
        ctrl.SaveTexture(s, path)

    saved = set()
    for e in sorted(x for x in acts if first <= x <= last):
        a = acts[e]
        line = 'event %d: %s' % (e, a.GetName(sf))
        if a.flags & rd.ActionFlags.Drawcall:
            ctrl.SetFrameEvent(e, True)
            st = ctrl.GetPipelineState()
            v = ctrl.GetVulkanPipelineState()
            null = rd.ResourceId.Null()
            ro = [b.descriptor.resource for b in st.GetReadOnlyResources(rd.ShaderStage.Fragment) if b.descriptor.resource != null]
            rw = [b.descriptor.resource for b in st.GetReadWriteResources(rd.ShaderStage.Fragment) if b.descriptor.resource != null]
            ds = v.depthStencil
            b0 = v.colorBlend.blends[0] if len(v.colorBlend.blends) else None
            m = ctrl.GetPostVSData(0, 0, rd.MeshDataStage.VSOut)
            data = ctrl.GetBufferData(m.vertexResourceId, m.vertexByteOffset, 0)
            n = min(len(data) // max(m.vertexByteStride, 1), 4000)
            pos = [struct.unpack_from('<4f', data, i * m.vertexByteStride) for i in range(n)]
            pos = [(x / w, y / w, z / w) for x, y, z, w in pos if w]
            rng = ' '.join('%.4f..%.4f' % (min(p[k] for p in pos), max(p[k] for p in pos)) for k in range(3)) if pos else '-'
            line += ' idx %d fs %s pipe %s ro %s rw %s depth %s/%s/%s stencil %s blend %s xyz/w %s' % (
                a.numIndices, num(st.GetShader(rd.ShaderStage.Fragment)), num(v.graphics.pipelineResourceId),
                [name(r) for r in ro], [name(r) for r in rw], ds.depthTestEnable, ds.depthWriteEnable,
                str(ds.depthFunction).split('.')[-1], ds.stencilTestEnable, b0.enabled if b0 else '-', rng)
            for r in ro:
                if r in tex and r not in saved and tex[r].width > 1:
                    saved.add(r)
                    save(r, os.path.join(OUT, 'tex-%s-rgb.png' % num(r)), rd.AlphaMapping.Discard)
                    save(r, os.path.join(OUT, 'tex-%s-a.png' % num(r)), rd.AlphaMapping.Preserve)
            for n in save_ids:
                if n in by_num:
                    save(by_num[n], os.path.join(OUT, 'e%05d-%s.png' % (e, n)), rd.AlphaMapping.Discard)
        log.write(line + '\n')
    ctrl.Shutdown()
    cap.Shutdown()
except Exception:
    log.write(traceback.format_exc())
log.close()
os._exit(0)
