"""Render passes of a RenderDoc capture, from its XML export (renderdoccmd convert -c xml), one line each.

usage:
  python -I tools/lab/rdc_passes.py <capture.xml> [--draws]

Per render pass: its colour/depth images (id, size, format), clear values, draw count and index total, and the
images its draws sample (through the descriptor sets bound). --draws also lists each draw: pipeline, index count,
scissor, and the sampled images. Images are named by their RenderDoc ids; `img<id>` lines at the top give each
image's size and format. A frame drawn by Vita3K's Vulkan renderer: one pass per GXM scene (or part of one).
"""
import sys
import xml.etree.ElementTree as ET


def child(e, name):
    for c in e:
        if c.get('name') == name:
            return c
    return None


def rid(e, name):
    c = child(e, name)
    return c.text if c is not None else None


def ids_in(e, typename):
    return [c.text for c in e.iter('ResourceId') if c.get('typename') == typename]


def main():
    path = sys.argv[1]
    show_draws = '--draws' in sys.argv
    images, views, framebuffers, sets = {}, {}, {}, {}
    passes, cur = [], None
    bound_sets, pipeline, scissor = [], None, None
    for _, ch in ET.iterparse(path):
        if ch.tag != 'chunk':
            continue
        name = ch.get('name')
        if name == 'vkCreateImage':
            info = child(ch, 'CreateInfo')
            ext = child(info, 'extent')
            fmt = child(info, 'format')
            images[rid(ch, 'Image')] = (f'{child(ext, "width").text}x{child(ext, "height").text}',
                                        fmt.get('string', '').replace('VK_FORMAT_', ''))
        elif name == 'vkCreateImageView':
            info = child(ch, 'CreateInfo')
            views[rid(ch, 'View')] = (rid(info, 'image'), child(info, 'format').get('string', '').replace('VK_FORMAT_', ''))
        elif name == 'vkCreateFramebuffer':
            info = child(ch, 'CreateInfo')
            framebuffers[rid(ch, 'Framebuffer')] = ids_in(child(info, 'pAttachments'), 'VkImageView')
        elif name == 'vkUpdateDescriptorSets':
            for w in child(ch, 'pDescriptorWrites'):
                s = rid(w, 'dstSet')
                imgs = ids_in(w, 'VkImageView')
                if imgs:
                    sets.setdefault(s, {})[rid(w, 'dstBinding')] = imgs
        elif name == 'vkCmdBeginRenderPass':
            info = child(ch, 'RenderPassBegin')
            fb = rid(info, 'framebuffer')
            clears = [' '.join(f.text for f in list(c.iter('array'))[0]) for c in child(info, 'pClearValues')]
            area = child(child(info, 'renderArea'), 'extent')
            cur = {'fb': fb, 'atts': [views.get(v, (None, '?')) for v in framebuffers.get(fb, [])],
                   'area': f'{child(area, "width").text}x{child(area, "height").text}', 'clears': clears,
                   'draws': 0, 'indices': 0, 'sampled': set(), 'list': []}
            passes.append(cur)
        elif name == 'vkCmdEndRenderPass':
            cur = None
        elif name == 'vkCmdBindPipeline':
            pipeline = rid(ch, 'pipeline')
        elif name == 'vkCmdSetScissor':
            r = list(child(ch, 'pScissors'))[0]
            o, e = child(r, 'offset'), child(r, 'extent')
            scissor = f'{e[0].text}x{e[1].text}@{o[0].text},{o[1].text}'
        elif name == 'vkCmdBindDescriptorSets':
            bound_sets = ids_in(child(ch, 'pDescriptorSets'), 'VkDescriptorSet')
        elif name in ('vkCmdDrawIndexed', 'vkCmdDraw') and cur is not None:
            n = int(child(ch, 'indexCount' if name == 'vkCmdDrawIndexed' else 'vertexCount').text)
            sampled = set()
            for s in bound_sets:
                for imgs in sets.get(s, {}).values():
                    sampled.update(views.get(v, (None,))[0] for v in imgs)
            sampled.discard(None)
            cur['draws'] += 1
            cur['indices'] += n
            cur['sampled'] |= sampled
            cur['list'].append(f'pipe {pipeline} n {n} scissor {scissor} samples {" ".join(sorted(sampled))}')
        ch.clear()
    used = set()
    for p in passes:
        used.update(a[0] for a in p['atts'])
        used |= p['sampled']
    for i in sorted(used - {None}, key=int):
        print(f'img{i}: {" ".join(images.get(i, ("?", "?")))}')
    for k, p in enumerate(passes):
        atts = ', '.join(f'img{a[0]}' for a in p['atts'])
        print(f'pass {k}: [{atts}] area {p["area"]} clear {p["clears"][:1]} draws {p["draws"]} indices {p["indices"]}'
              f' samples {" ".join("img" + s for s in sorted(p["sampled"], key=int))}')
        if show_draws:
            for d in p['list']:
                print('    ' + d)


if __name__ == '__main__':
    main()
