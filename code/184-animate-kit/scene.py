# Chef & jars, 3D. Run: Blender -b -P scene.py -- MODE [args]
#   still <frame> <pct>   -> renders one frame to out/still_<frame>.png at pct% res
#   anim <pct> [start end] -> renders frames to out/f_####.png
import bpy, bmesh, math, sys, os
from mathutils import Vector

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ["still", "100", "60"]
MODE = ARGS[0]
HERE = os.path.dirname(os.path.abspath(__file__))  # kit example: the "chef jars" MCP explainer; replace the scene, keep the helpers
TEX = os.path.join(HERE, "tex")
OUT = os.path.join(HERE, "out")
FPS = 25
END_S = 20.0


def F(s):
    return int(round(s * FPS)) + 1


def hexrgb(h, a=1.0):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return (*c, a)


bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = FPS
sc.frame_start, sc.frame_end = 1, F(END_S)
enames = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
sc.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in enames else "BLENDER_EEVEE_NEXT"
ee = sc.eevee
for attr, val in (("use_raytracing", True), ("taa_render_samples", 48), ("use_shadows", True),
                  ("fast_gi_method", "GLOBAL_ILLUMINATION"), ("use_fast_gi", True)):
    try:
        setattr(ee, attr, val)
    except Exception:
        pass
try:
    ee.ray_tracing_options.resolution_scale = "2"
except Exception:
    pass
sc.view_settings.view_transform = "Standard"
sc.view_settings.exposure = -0.1
sc.render.resolution_x, sc.render.resolution_y = 1600, 950
sc.render.film_transparent = False

# ---------- world ----------
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
bg = w.node_tree.nodes["Background"]; bg.inputs[0].default_value = hexrgb("#e6fbfb"); bg.inputs[1].default_value = 0.4


# ---------- helpers ----------
def mat(name, col, rough=0.5, emit=None, estr=0.0, trans=0.0, alpha=None):
    m = bpy.data.materials.new(name); m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = col
    p.inputs["Roughness"].default_value = rough
    if trans:
        p.inputs["Transmission Weight"].default_value = trans
        p.inputs["IOR"].default_value = 1.45
        try:
            m.surface_render_method = "DITHERED"; m.use_raytrace_refraction = True
        except Exception:
            pass
    if emit is not None:
        p.inputs["Emission Color"].default_value = emit
        p.inputs["Emission Strength"].default_value = estr
    return m


def key(datapath_owner, path, frame, value, index=-1):
    setattr(datapath_owner, path, value) if index < 0 else None
    if index >= 0:
        getattr(datapath_owner, path)[index] = value
    datapath_owner.keyframe_insert(path, frame=frame, index=index)


def keyv(sock, frame, value):
    sock.default_value = value
    sock.keyframe_insert("default_value", frame=frame)


def smooth(o, ang=0.6):
    bpy.context.view_layer.objects.active = o
    for x in bpy.context.view_layer.objects:
        x.select_set(False)
    o.select_set(True)
    try:
        bpy.ops.object.shade_smooth_by_angle(angle=ang)
    except Exception:
        bpy.ops.object.shade_smooth()


def cyl(name, r, h, loc, m, verts=96, bevel=0.0, segs=4):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=h, location=(loc[0], loc[1], loc[2] + h / 2))
    o = bpy.context.object; o.name = name; o.data.materials.append(m)
    if bevel:
        b = o.modifiers.new("bev", "BEVEL"); b.width = bevel; b.segments = segs; b.limit_method = "ANGLE"
    smooth(o)
    return o


def box(name, size, loc, m, bevel=0.02):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object; o.name = name; o.scale = size; o.data.materials.append(m)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        b = o.modifiers.new("bev", "BEVEL"); b.width = bevel; b.segments = 3
    smooth(o)
    return o


def img_mat(name, path, emissive=False, estr=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; n = nt.nodes
    for x in list(n):
        n.remove(x)
    out = n.new("ShaderNodeOutputMaterial"); tx = n.new("ShaderNodeTexImage")
    tx.image = bpy.data.images.load(path); tx.interpolation = "Cubic"
    tr = n.new("ShaderNodeBsdfTransparent"); mix = n.new("ShaderNodeMixShader")
    if emissive:
        sh = n.new("ShaderNodeEmission"); sh.inputs[1].default_value = estr
        nt.links.new(tx.outputs[0], sh.inputs[0])
    else:
        sh = n.new("ShaderNodeBsdfPrincipled"); sh.inputs["Roughness"].default_value = 0.6
        nt.links.new(tx.outputs[0], sh.inputs["Base Color"])
    nt.links.new(tx.outputs[1], mix.inputs[0]); nt.links.new(tr.outputs[0], mix.inputs[1]); nt.links.new(sh.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    try:
        m.surface_render_method = "DITHERED"
    except Exception:
        pass
    return m


def swap_mat(name, pa, pb):
    """label that cross-fades texture A -> B; returns (mat, fac socket)"""
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; n = nt.nodes
    for x in list(n):
        n.remove(x)
    out = n.new("ShaderNodeOutputMaterial")
    ta = n.new("ShaderNodeTexImage"); ta.image = bpy.data.images.load(pa)
    tb = n.new("ShaderNodeTexImage"); tb.image = bpy.data.images.load(pb)
    fac = n.new("ShaderNodeValue"); fac.outputs[0].default_value = 0
    mc = n.new("ShaderNodeMix"); mc.data_type = "RGBA"
    ma = n.new("ShaderNodeMath"); ma.operation = "ADD"; ma.use_clamp = True
    # colour mix
    nt.links.new(fac.outputs[0], mc.inputs[0]); nt.links.new(ta.outputs[0], mc.inputs[6]); nt.links.new(tb.outputs[0], mc.inputs[7])
    am = n.new("ShaderNodeMix"); am.data_type = "FLOAT"
    nt.links.new(fac.outputs[0], am.inputs[0]); nt.links.new(ta.outputs[1], am.inputs[2]); nt.links.new(tb.outputs[1], am.inputs[3])
    p = n.new("ShaderNodeBsdfPrincipled"); p.inputs["Roughness"].default_value = 0.6
    nt.links.new(mc.outputs[2], p.inputs["Base Color"])
    tr = n.new("ShaderNodeBsdfTransparent"); mx = n.new("ShaderNodeMixShader")
    nt.links.new(am.outputs[0], mx.inputs[0]); nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(p.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs[0])
    try:
        m.surface_render_method = "DITHERED"
    except Exception:
        pass
    return m, fac.outputs[0]


def curved_label(name, r, ang_deg, h, loc, m, segs=48):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    a0 = math.radians(-90 - ang_deg / 2); a1 = math.radians(-90 + ang_deg / 2)
    rows = []
    for i in range(segs + 1):
        a = a0 + (a1 - a0) * i / segs
        x, y = r * math.cos(a), r * math.sin(a)
        rows.append((bm.verts.new((x, y, -h / 2)), bm.verts.new((x, y, h / 2)), i / segs))
    uv = bm.loops.layers.uv.new()
    for i in range(segs):
        (b0, t0, u0), (b1, t1, u1) = rows[i], rows[i + 1]
        f = bm.faces.new((b0, b1, t1, t0))
        for lp, co in zip(f.loops, ((u0, 0), (u1, 0), (u1, 1), (u0, 1))):
            lp[uv].uv = co
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(o)
    o.location = loc; me.materials.append(m)
    for p in me.polygons:
        p.use_smooth = True
    return o


def plane(name, w_, h_, loc, rot, m):
    bpy.ops.mesh.primitive_plane_add(size=1, location=loc, rotation=rot)
    o = bpy.context.object; o.name = name; o.scale = (w_, h_, 1); o.data.materials.append(m)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return o


def pop(o, s, base=1.0, over=1.12, dur=0.45):
    o.scale = (0, 0, 0); o.keyframe_insert("scale", frame=1)
    o.keyframe_insert("scale", frame=F(s))
    o.scale = (base * over,) * 3; o.keyframe_insert("scale", frame=F(s + dur * 0.65))
    o.scale = (base,) * 3; o.keyframe_insert("scale", frame=F(s + dur))


def unpop(o, s, base=1.0, dur=0.3):
    o.scale = (base,) * 3; o.keyframe_insert("scale", frame=F(s))
    o.scale = (0, 0, 0); o.keyframe_insert("scale", frame=F(s + dur))


# ---------- set: cyclorama ----------
def cyc():
    me = bpy.data.meshes.new("cyc"); bm = bmesh.new()
    prof = [(-20, -0.12)]
    R = 4.0; y0 = 5.0
    for i in range(17):
        a = math.radians(-90 + 90 * i / 16)
        prof.append((y0 + R * math.cos(a), -0.12 + R + R * math.sin(a)))
    prof.append((y0 + R, 18))
    ring = []
    for x in (-30, 30):
        ring.append([bm.verts.new((x, y, z)) for (y, z) in prof])
    for i in range(len(prof) - 1):
        bm.faces.new((ring[0][i], ring[1][i], ring[1][i + 1], ring[0][i + 1]))
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new("cyc", me); bpy.context.collection.objects.link(o)
    for p in me.polygons:
        p.use_smooth = True
    o.data.materials.append(mat("cycM", hexrgb("#e3fbfb"), 0.9))


cyc()

# ---------- cupboard ----------
CX = 1.7
wood = mat("shelf", hexrgb("#fbfcfc"), 0.45)
back = mat("back", hexrgb("#ffffff"), 0.7)
box("backpanel", (6.3, 0.16, 3.75), (CX, 1.05, 1.72), back, 0.06)
box("shelfB", (6.0, 1.7, 0.14), (CX, 0.15, -0.05), wood, 0.03)
box("shelfT", (6.0, 1.7, 0.14), (CX, 0.15, 1.85), wood, 0.03)
box("sideL", (0.14, 1.7, 3.75), (CX - 3.07, 0.15, 1.72), wood, 0.03)
box("sideR", (0.14, 1.7, 3.75), (CX + 3.07, 0.15, 1.72), wood, 0.03)
# LED strips (light up at the end)
led = mat("led", hexrgb("#e3eaea"), 0.3, emit=hexrgb("#19e6df"), estr=0.0)
box("ledT", (5.8, 0.05, 0.07), (CX, -0.68, 1.76), led, 0)
box("ledB", (5.8, 0.05, 0.07), (CX, -0.68, 0.04), led, 0)
ledE = led.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]

# ---------- jars ----------
glass = mat("glass", hexrgb("#eefcfc"), 0.04)
_gp = glass.node_tree.nodes["Principled BSDF"]; _gp.inputs["Alpha"].default_value = 0.16
try:
    _gp.inputs["Coat Weight"].default_value = 1.0; _gp.inputs["Coat Roughness"].default_value = 0.03
    _gp.inputs["Specular IOR Level"].default_value = 0.9
except Exception:
    pass
try:
    glass.surface_render_method = "BLENDED"; glass.use_backface_culling = False
except Exception:
    pass
lidm = mat("lid", hexrgb("#163440"), 0.32)
CONTENT = ["#f0c995", "#cde5ae", "#f5d677", "#cdb8f0", "#d9dfe1", "#b9d4f0"]
LABELS = ["l_get_customer", "l_missing", "l_create_ticket", "l_send_email", "l_read_records", "l_invoiceupdate"]
FIXED = {1: "l_update_address", 4: "l_delete_records", 5: "l_update_invoice"}
COLS = [CX - 1.85, CX, CX + 1.85]
ROWS = [1.92, 0.02]
JARS = []
for i in range(6):
    x = COLS[i % 3]; z = ROWS[i // 3]
    root = bpy.data.objects.new(f"jar{i}", None); bpy.context.collection.objects.link(root)
    root.location = (x, 0.0, z)
    parts = []
    g = cyl(f"glass{i}", 0.62, 1.32, (0, 0, 0), glass, bevel=0.1, segs=5); parts.append(g)
    s = g.modifiers.new("sol", "SOLIDIFY"); s.thickness = 0.035
    cm = mat(f"cont{i}", hexrgb(CONTENT[i]), 0.55, emit=hexrgb("#ff2a1f"), estr=0.0)
    c = cyl(f"cont{i}", 0.55, 0.86, (0, 0, 0.05), cm, bevel=0.12, segs=5); parts.append(c)
    l = cyl(f"lid{i}", 0.56, 0.2, (0, 0, 1.3), lidm, bevel=0.05); parts.append(l)
    if i in FIXED:
        lm, fac = swap_mat(f"lab{i}", f"{TEX}/{LABELS[i]}.png", f"{TEX}/{FIXED[i]}.png")
    else:
        lm, fac = img_mat(f"lab{i}", f"{TEX}/{LABELS[i]}.png"), None
    lab = curved_label(f"label{i}", 0.665, 124, 0.68, (0, 0, 0.8), lm); parts.append(lab)
    for p in parts:
        p.parent = root
    # base ring glow
    rm = mat(f"ring{i}", hexrgb("#d7ecec"), 0.3, emit=hexrgb("#0fbdb8"), estr=0.0)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.78, minor_radius=0.022, location=(0, 0, 0.03))
    ring = bpy.context.object; ring.name = f"ring{i}"; ring.data.materials.append(rm); ring.parent = root
    JARS.append(dict(root=root, cont=cm, ring=rm, fac=fac, x=x, z=z, lab=lab))

# DELETES stencil on jar4 contents
dm = img_mat("deletesM", f"{TEX}/deletes.png", emissive=True, estr=2.2)
dl = curved_label("deletes", 0.565, 80, 0.2, (0, 0, 0.3), dm)
dl.parent = JARS[4]["root"]

# badges
BADGE = {k: img_mat("b_" + k, f"{TEX}/b_{k}.png", emissive=True, estr=1.6) for k in ("tick", "q", "warn", "shield")}


def badge(i, kind, s):
    j = JARS[i]
    o = plane(f"badge{i}{kind}", 0.5, 0.5, (j["x"] + 0.58, -0.7, j["z"] + 1.46), (math.radians(90), 0, 0), BADGE[kind])
    pop(o, s, base=1.0, over=1.25, dur=0.4)
    return o


# ---------- chef ----------
ped_m = mat("ped", hexrgb("#ffffff"), 0.5)
cyl("pedestal", 1.05, 0.3, (-2.85, -0.3, -0.12), ped_m, bevel=0.12, segs=6)
hat_m = mat("hat", hexrgb("#ffffff"), 0.62)
try:
    hat_m.node_tree.nodes["Principled BSDF"].inputs["Subsurface Weight"].default_value = 0.15
except Exception:
    pass
puffs = [(0, 0, 1.38, 0.58), (-0.4, 0.0, 1.2, 0.42), (0.4, 0.0, 1.2, 0.42), (0, -0.38, 1.2, 0.4), (0, 0.38, 1.2, 0.4)]
objs = []
for (x, y, z, r) in puffs:
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=(x, y, z), segments=48, ring_count=24); objs.append(bpy.context.object)
bpy.ops.mesh.primitive_cylinder_add(radius=0.46, depth=0.95, location=(0, 0, 0.475), vertices=96); objs.append(bpy.context.object)
for o in bpy.context.view_layer.objects:
    o.select_set(False)
for o in objs:
    o.select_set(True)
bpy.context.view_layer.objects.active = objs[-1]
bpy.ops.object.join()
hat = bpy.context.object; hat.name = "hat"; hat.location = (0, 0, 0)
bpy.ops.object.transform_apply(location=True)
hat.location = (0, 0, 0)
rm_ = hat.modifiers.new("rem", "REMESH"); rm_.mode = "VOXEL"; rm_.voxel_size = 0.045
ss = hat.modifiers.new("sub", "SUBSURF"); ss.levels = 2; ss.render_levels = 3
hat.data.materials.append(hat_m); smooth(hat, 3.1)
hat_root = bpy.data.objects.new("chef", None); bpy.context.collection.objects.link(hat_root)
hat_root.location = (-2.85, -0.3, 0.18); hat.parent = hat_root
pleat_m = mat("pleat", hexrgb("#dfeced"), 0.6)
for k in range(9):
    a = math.radians(-90 - 64 + k * 16)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.03, depth=0.62, location=(0.445 * math.cos(a), 0.445 * math.sin(a), 0.42), vertices=16)
    pl = bpy.context.object; pl.data.materials.append(pleat_m); pl.parent = hat_root
# idle bob
hat_root.keyframe_insert("location", frame=1)
for k, s in enumerate([x * 1.6 for x in range(1, 13)]):
    hat_root.location = (-2.85, -0.3, 0.18 + (0.05 if k % 2 == 0 else 0.0)); hat_root.keyframe_insert("location", frame=F(s))
pop(hat_root, 0.0, base=1.3, dur=0.6)

# chef acting: lean towards each reach, nod / shake / recoil, happy hop at the end
def rot(s_, x=0.0, y=0.0, z=0.0):
    hat_root.rotation_euler = (x, y, z); hat_root.keyframe_insert("rotation_euler", frame=F(s_))
def sq(s_, sx, sz):
    hat.scale = (sx, sx, sz); hat.keyframe_insert("scale", frame=F(s_))
rot(0.0); rot(1.6)
rot(1.95, y=0.16); rot(2.6, y=0.16); rot(2.75, x=0.14, y=0.12); rot(2.95, y=0.1); rot(3.5)     # reach A, nod
rot(3.7, y=0.2); rot(4.3, y=0.2); rot(4.4, y=0.05); rot(4.6, y=0.22)                          # reach B, retry
rot(5.1, y=0.2, z=0.14); rot(5.25, y=0.2, z=-0.14); rot(5.4, y=0.2, z=0.1); rot(5.55, y=0.2, z=-0.06); rot(5.75, y=0.1)  # shake
rot(6.0, y=0.24); rot(6.6, y=0.24); rot(6.8, y=-0.22, x=-0.06); rot(7.4, y=-0.12); rot(8.2)  # reach C, recoil
sq(0.0, 1, 1); sq(6.6, 1, 1); sq(6.72, 1.1, 0.85); sq(6.95, 0.96, 1.05); sq(7.2, 1, 1)
rot(14.0); rot(14.2, x=0.1); rot(14.45, x=-0.05); rot(14.7)
sq(13.9, 1, 1); sq(14.05, 1.12, 0.84); sq(14.25, 0.94, 1.12); sq(14.5, 1.03, 0.97); sq(14.7, 1, 1)
hat.location = (0, 0, 0); hat.keyframe_insert("location", frame=F(14.05))
hat.location = (0, 0, 0.35); hat.keyframe_insert("location", frame=F(14.3))
hat.location = (0, 0, 0); hat.keyframe_insert("location", frame=F(14.6))

# ---------- reaches ----------
reach_m = mat("reach", hexrgb("#fe5e27"), 0.3, emit=hexrgb("#fe5e27"), estr=3.0)
reachE = reach_m.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
ORIGIN = Vector((-2.15, -0.55, 1.45))


def reach_curve(i):
    j = JARS[i]
    end = Vector((j["x"] - 0.64, -0.3, j["z"] + 0.24))
    cu = bpy.data.curves.new(f"reach{i}", "CURVE"); cu.dimensions = "3D"
    sp = cu.splines.new("BEZIER"); sp.bezier_points.add(1)
    p0, p1 = sp.bezier_points
    p0.co = ORIGIN; p1.co = end
    mid = (ORIGIN + end) / 2
    p0.handle_left = ORIGIN
    p0.handle_right = Vector((ORIGIN.x + 1.1, ORIGIN.y - 0.7, end.z - 0.15)) if end.z < 1 else Vector((mid.x, ORIGIN.y - 0.6, ORIGIN.z + 0.9))
    p1.handle_left = Vector((end.x - 1.0, end.y - 0.45, end.z - 0.05)); p1.handle_right = end
    cu.bevel_depth = 0.035; cu.bevel_resolution = 6; cu.resolution_u = 48
    o = bpy.data.objects.new(f"reach{i}", cu); bpy.context.collection.objects.link(o)
    o.data.materials.append(reach_m)
    cu.bevel_factor_end = 0.0
    cu.keyframe_insert("bevel_factor_end", frame=1)
    # packet
    bpy.ops.mesh.primitive_cube_add(size=0.16)
    pk = bpy.context.object; pk.name = f"pkt{i}"; pk.data.materials.append(reach_m)
    fp = pk.constraints.new("FOLLOW_PATH"); fp.target = o; fp.use_fixed_location = True
    pk.rotation_euler = (math.radians(45), math.radians(35), 0)
    pk.scale = (0, 0, 0); pk.keyframe_insert("scale", frame=1)
    return cu, pk, fp


def grow(cu, pk, fp, s0, s1, a=0.0, b=1.0):
    cu.bevel_factor_end = a; cu.keyframe_insert("bevel_factor_end", frame=F(s0))
    cu.bevel_factor_end = b; cu.keyframe_insert("bevel_factor_end", frame=F(s1))
    fp.offset_factor = a; fp.keyframe_insert("offset_factor", frame=F(s0))
    fp.offset_factor = b; fp.keyframe_insert("offset_factor", frame=F(s1))
    pk.scale = (1, 1, 1); pk.keyframe_insert("scale", frame=F(s0)); pk.keyframe_insert("scale", frame=F(s1) - 1)
    pk.scale = (0, 0, 0); pk.keyframe_insert("scale", frame=F(s0) - 1); pk.keyframe_insert("scale", frame=F(s1) + 1)


def ring_on(i, s, col, strength=4.0, off=None):
    rm = JARS[i]["ring"]; p = rm.node_tree.nodes["Principled BSDF"]
    p.inputs["Emission Color"].default_value = hexrgb(col)
    keyv(p.inputs["Emission Strength"], F(s) - 1, 0.0); keyv(p.inputs["Emission Strength"], F(s + 0.25), strength)
    if off:
        keyv(p.inputs["Emission Strength"], F(off), strength); keyv(p.inputs["Emission Strength"], F(off + 0.4), 0.0)


def shake(i, s, dur=0.5, amp=0.06):
    r = JARS[i]["root"]; x0 = r.location.x
    r.keyframe_insert("location", frame=F(s))
    n = int(dur * FPS)
    for k in range(1, n):
        r.location.x = x0 + amp * math.sin(k * 2.2) * (1 - k / n); r.keyframe_insert("location", frame=F(s) + k)
    r.location.x = x0; r.keyframe_insert("location", frame=F(s) + n)


# timeline
for i, j in enumerate(JARS):
    pop(j["root"], 0.25 + i * 0.09, dur=0.55)
for o in ("ledT", "ledB"):
    pass

RA = reach_curve(0); RB = reach_curve(1); RC = reach_curve(4)
# A: get_customer
grow(*RA, 1.9, 2.6); ring_on(0, 2.6, "#0fbdb8", off=9.6); bA = badge(0, "tick", 2.65)
# B: missing label, tries twice
grow(*RB, 3.6, 4.2); grow(*RB, 4.2, 4.5, 1.0, 0.25); grow(*RB, 4.6, 5.15, 0.25, 1.0)
ring_on(1, 5.15, "#e8840f", off=9.6); bB = badge(1, "q", 5.2); shake(1, 4.2, 0.35, 0.03)
# C: read_records -> deletes
grow(*RC, 5.9, 6.6); ring_on(4, 6.7, "#e0392c", 5.0, off=None)
shake(4, 6.65, 0.6, 0.07)
cp = JARS[4]["cont"].node_tree.nodes["Principled BSDF"]
keyv(cp.inputs["Base Color"], F(6.65), hexrgb(CONTENT[4])); keyv(cp.inputs["Base Color"], F(7.1), hexrgb("#f2a59c"))
keyv(cp.inputs["Emission Strength"], F(6.65), 0.0); keyv(cp.inputs["Emission Strength"], F(7.1), 0.35)
dl.scale = (1, 1, 0); dl.keyframe_insert("scale", frame=F(6.9)); dl.scale = (1, 1, 1); dl.keyframe_insert("scale", frame=F(7.2))
bC = badge(4, "warn", 6.9)
# reach lines dim then go
keyv(reachE, F(2.6), 3.0); keyv(reachE, F(9.0), 3.0); keyv(reachE, F(9.6), 0.0)
for (cu, pk, fp), a in ((RA, 3.2), (RB, 5.6), (RC, 9.0)):
    cu.bevel_factor_end = 1.0; cu.keyframe_insert("bevel_factor_end", frame=F(a))
    cu.bevel_factor_end = 0.0; cu.keyframe_insert("bevel_factor_end", frame=F(a + 0.5))

# scanner
SC0, SC1 = 10.4, 13.4
scan_m = mat("scan", hexrgb("#20e3dc"), 0.2, emit=hexrgb("#20e3dc"), estr=8.0)
scan = box("scanner", (0.08, 0.08, 4.1), (0, -0.78, 1.72), scan_m, 0)
sheet_m = mat("sheet", hexrgb("#20e3dc"), 0.2, emit=hexrgb("#20e3dc"), estr=1.5)
sheet_m.node_tree.nodes["Principled BSDF"].inputs["Alpha"].default_value = 0.12
try:
    sheet_m.surface_render_method = "BLENDED"
except Exception:
    pass
for k, (wd, off) in enumerate(((0.5, -0.25), (1.1, -0.55))):
    bpy.ops.mesh.primitive_plane_add(size=1, location=(off, -0.02, 0), rotation=(math.radians(90), 0, 0))
    sh = bpy.context.object; sh.name = f"sheet{k}"; sh.scale = (wd, 4.0, 1); sh.data.materials.append(sheet_m); sh.parent = scan
sl = bpy.data.lights.new("scanL", "AREA"); sl.shape = "RECTANGLE"; sl.size = 0.1; sl.size_y = 4.0
sl.color = (0.25, 0.95, 0.9); sl.energy = 0
slo = bpy.data.objects.new("scanL", sl); bpy.context.collection.objects.link(slo)
slo.location = (0, -1.3, 1.72); slo.rotation_euler = (math.radians(90), 0, 0); slo.parent = scan
x0, x1 = CX - 3.0, CX + 3.0
scan.location.x = x0; scan.scale = (1, 1, 0); scan.keyframe_insert("location", frame=F(SC0)); scan.keyframe_insert("scale", frame=1)
scan.keyframe_insert("scale", frame=F(SC0 - 0.3))
scan.scale = (1, 1, 1); scan.keyframe_insert("scale", frame=F(SC0))
scan.location.x = x1; scan.keyframe_insert("location", frame=F(SC1))
scan.keyframe_insert("scale", frame=F(SC1)); scan.scale = (1, 1, 0); scan.keyframe_insert("scale", frame=F(SC1 + 0.3))
sl.energy = 0; sl.keyframe_insert("energy", frame=F(SC0 - 0.3)); sl.energy = 22; sl.keyframe_insert("energy", frame=F(SC0))
sl.keyframe_insert("energy", frame=F(SC1)); sl.energy = 0; sl.keyframe_insert("energy", frame=F(SC1 + 0.3))

FIN = 14.0
for i, j in enumerate(JARS):
    fa = SC0 + (SC1 - SC0) * ((j["x"] - x0) / (x1 - x0))
    j["fixAt"] = fa
    if j["fac"] is not None:
        keyv(j["fac"], F(fa), 0.0); keyv(j["fac"], F(fa + 0.45), 1.0)
        r = j["root"]; z0 = r.location.z
        r.location.z = z0; r.keyframe_insert("location", index=2, frame=F(fa))
        r.location.z = z0 + 0.22; r.keyframe_insert("location", index=2, frame=F(fa + 0.18))
        r.location.z = z0; r.keyframe_insert("location", index=2, frame=F(fa + 0.42))
    if i == 0:
        continue
    if i == 1:
        unpop(bB, fa); badge(1, "tick", fa + 0.2); ring_on(1, fa, "#0fbdb8", 4.0)
    elif i == 4:
        unpop(bC, fa); badge(4, "shield", fa + 0.2)
        p = JARS[4]["ring"].node_tree.nodes["Principled BSDF"]
        keyv(p.inputs["Emission Strength"], F(fa), 5.0)
        p.inputs["Emission Color"].default_value = hexrgb("#e0392c")
        keyv(cp.inputs["Emission Strength"], F(fa), 0.35); keyv(cp.inputs["Emission Strength"], F(fa + 0.4), 0.0)
    elif i == 5:
        badge(5, "shield", fa + 0.2); ring_on(5, fa, "#e8840f", 4.0)
    else:
        badge(i, "tick", fa + 0.2); ring_on(i, fa, "#0fbdb8", 4.0)
# jar0 ring back on at fix
ring_on(0, JARS[0]["fixAt"], "#0fbdb8", 4.0)
# jar4 ring: red -> amber (colour can't be keyed simply on a shared value; re-key emission colour)
p4 = JARS[4]["ring"].node_tree.nodes["Principled BSDF"]
keyv(p4.inputs["Emission Color"], F(6.6), hexrgb("#e0392c")); keyv(p4.inputs["Emission Color"], F(JARS[4]["fixAt"]), hexrgb("#e0392c"))
keyv(p4.inputs["Emission Color"], F(JARS[4]["fixAt"] + 0.4), hexrgb("#e8840f"))
# LED finale
keyv(ledE, F(FIN), 0.0); keyv(ledE, F(FIN + 0.6), 25.0)
_bp = back.node_tree.nodes["Principled BSDF"]; _bp.inputs["Emission Color"].default_value = hexrgb("#8ff5ef")
keyv(_bp.inputs["Emission Strength"], F(FIN), 0.0); keyv(_bp.inputs["Emission Strength"], F(FIN + 0.8), 0.55)
bl = bpy.data.lights.new("backglow", "AREA"); bl.size = 6.0; bl.color = (0.2, 0.95, 0.9); bl.energy = 0
blo = bpy.data.objects.new("backglow", bl); bpy.context.collection.objects.link(blo)
blo.location = (CX, 0.85, 1.8); blo.rotation_euler = (math.radians(90), 0, 0)
bl.keyframe_insert("energy", frame=F(FIN)); bl.energy = 260; bl.keyframe_insert("energy", frame=F(FIN + 0.8))

# ---------- lights ----------
def area(name, loc, rot, size, energy, col=(1, 1, 1)):
    L = bpy.data.lights.new(name, "AREA"); L.size = size; L.energy = energy; L.color = col
    o = bpy.data.objects.new(name, L); bpy.context.collection.objects.link(o)
    o.location = loc; o.rotation_euler = [math.radians(a) for a in rot]
    return L


area("key", (-4.5, -7.5, 7.5), (48, 0, -30), 4.0, 1000, (1, 0.97, 0.93))
area("fill", (8.5, -6.0, 3.0), (75, 0, 50), 7.0, 220, (0.9, 0.97, 1.0))
area("rim", (1.7, 4.0, 7.0), (-45, 0, 180), 5.0, 500, (0.8, 1.0, 1.0))
area("top", (1.7, -1.5, 8.5), (0, 0, 0), 4.0, 120)

# ---------- camera ----------
cam_d = bpy.data.cameras.new("cam"); cam_d.lens = 42
cam_d.dof.use_dof = True; cam_d.dof.aperture_fstop = 4.0
cam = bpy.data.objects.new("cam", cam_d); bpy.context.collection.objects.link(cam); sc.camera = cam
tgt = bpy.data.objects.new("tgt", None); bpy.context.collection.objects.link(tgt)
cam_d.dof.focus_object = tgt
tc = cam.constraints.new("TRACK_TO"); tc.target = tgt; tc.track_axis = "TRACK_NEGATIVE_Z"; tc.up_axis = "UP_Y"
CAM_KEYS = [(0.0, (0.0, -16.5, 2.4), (0.6, 0, 2.0)),
            (2.2, (0.3, -14.0, 3.5), (0.6, 0, 2.15)),
            (9.8, (0.7, -13.7, 3.6), (0.65, 0, 2.15)),
            (14.0, (0.5, -13.8, 3.5), (0.6, 0, 2.15)),
            (20.0, (-0.1, -13.5, 3.4), (0.6, 0, 2.15))]
for s, cl, tl in CAM_KEYS:
    cam.location = cl; cam.keyframe_insert("location", frame=F(s))
    tgt.location = tl; tgt.keyframe_insert("location", frame=F(s))

# ---------- render ----------
os.makedirs(OUT, exist_ok=True)
sc.render.image_settings.file_format = "PNG"
if MODE == "inspect":
    for o in bpy.data.objects:
        if o.name.startswith("badge"):
            vs = [o.matrix_world @ v.co for v in o.data.vertices]
            c = sum(vs, Vector()) / len(vs)
            fc = []
            print("INSPECT", o.name, tuple(round(x, 2) for x in o.location), "centre", tuple(round(x, 2) for x in c), "parent", o.parent.name if o.parent else None, "curves", sorted(set(f.data_path for f in fc)) if fc else "?")
elif MODE == "still":
    pct = int(ARGS[1]); fr = int(ARGS[2])
    sc.render.resolution_percentage = pct; sc.frame_set(fr)
    sc.render.filepath = f"{OUT}/still_{fr:04d}.png"
    bpy.ops.render.render(write_still=True)
else:
    pct = int(ARGS[1]); sc.render.resolution_percentage = pct
    if len(ARGS) > 3:
        sc.frame_start, sc.frame_end = int(ARGS[2]), int(ARGS[3])
    sc.render.filepath = f"{OUT}/f_"
    bpy.ops.render.render(animation=True)
