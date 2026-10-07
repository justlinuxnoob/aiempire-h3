#!/usr/bin/env python3
"""
AI Empire · H3 Video Cloner — workflow builder.

Builds the two ComfyUI workflows (UI format, drag-and-drop) plus matching
API-format files used only for automated validation:

  workflows/AI_Empire_H3_Reference.json   main mode: your character photos (+ optional voice)
  workflows/AI_Empire_H3_FirstLast.json   start and/or end image of your character

The system prompts are read from prompts/*.txt, so edit those and re-run:
  python3 tools/build_workflows.py
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = json.load(open(os.path.join(ROOT, "tools", "node_schema.json")))
PROMPTS = {n: open(os.path.join(ROOT, "prompts", f)).read().strip() for n, f in {
    "analyst": "1_video_analyst.txt",
    "ref": "2_h3_builder_reference.txt",
    "frames": "3_h3_builder_frames.txt",
}.items()}

# ---- model files (must match docker/start.sh) ----
GEMMA = "gemma4_12b_int8_convrot.safetensors"
H3_TE = "qwen3vl_32b_minimax_h3_int8_convrot.safetensors"
VAE_V = "minimax_h3_video_vae_fp16.safetensors"
VAE_A = "minimax_h3_audio_vae_fp32.safetensors"
REALISM = "h3-realism-people-t2v-i2v-r2v.safetensors"
MODES = {
    "ref": dict(unet="minimax_h3_ref2va_pruned_int8_convrot.safetensors",
                turbo="minimax_h3_ref2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors"),
    "frames": dict(unet="minimax_h3_fl2va_pruned_int8_convrot.safetensors",
                   turbo="minimax_h3_fl2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors"),
}
FRAMES_EXPR = "max(5, round(a * 24)) + (5 - (max(5, round(a * 24)) % 17)) % 17"  # seconds -> 17k+5 frames @24fps

# brand colours (ComfyUI node colour pairs)
GOLD = ("#3d2f0a", "#5c4710")      # things the member edits
BRAIN = ("#1f2a44", "#2c3d63")     # automatic AI brain
ENGINE = ("#222", "#000")          # H3 engine, don't touch
OUT = ("#1d3b2a", "#2a5a40")       # result

WIDGET_TYPES = {"INT", "FLOAT", "STRING", "BOOLEAN", "COMBO", "COMFY_DYNAMICCOMBO_V3"}


class Graph:
    def __init__(self):
        self.nodes, self.links, self.groups = [], [], []
        self.api = {}
        self._nid = 0
        self._lid = 0

    # ---------------------------------------------------------------- nodes
    def add(self, ntype, pos, size, widgets=(), title=None, colors=ENGINE, api=True, ui_widgets=None, mode=0):
        """widgets: ordered list of (name, value). ui_widgets overrides the UI widgets_values."""
        self._nid += 1
        nid = self._nid
        node = {"id": nid, "type": ntype, "pos": list(pos), "size": list(size), "flags": {},
                "order": nid, "mode": mode, "inputs": [], "outputs": [],
                "properties": {"Node name for S&R": ntype}}
        sch = SCHEMA.get(ntype)
        if sch:
            for sect in ("required", "optional"):
                for name in sch["input_order"].get(sect, []):
                    spec = sch["input"][sect][name]
                    t = spec[0] if isinstance(spec[0], str) else "COMBO"
                    opts = spec[1] if len(spec) > 1 else {}
                    is_widget = t in WIDGET_TYPES and not opts.get("forceInput")
                    if is_widget or t.startswith("COMFY_AUTOGROW") or t.startswith("COMFY_MATCHTYPE"):
                        continue
                    sock = {"name": name, "type": t, "link": None}
                    if sect == "optional":
                        sock["shape"] = 7
                    node["inputs"].append(sock)
            for i, (otype, oname) in enumerate(zip(sch["output"], sch["output_name"])):
                node["outputs"].append({"name": oname, "type": otype, "links": []})
            node["properties"]["cnr_id"] = "comfy-core" if not ntype.startswith("VHS") else "comfyui-videohelpersuite"
        if title:
            node["title"] = title
        node["color"], node["bgcolor"] = colors
        node["widgets_values"] = ui_widgets if ui_widgets is not None else [v for _, v in widgets]
        self.nodes.append(node)
        if api and sch:
            self.api[str(nid)] = {"class_type": ntype,
                                  "inputs": {k: v for k, v in widgets if k != "control_after_generate"},
                                  "_meta": {"title": title or ntype}}
        return nid

    def node(self, nid):
        return self.nodes[nid - 1]

    # ---------------------------------------------------------------- links
    def link(self, src, out_slot, dst, inp, label=None, socket_type=None):
        s, d = self.node(src), self.node(dst)
        otype = socket_type or s["outputs"][out_slot]["type"]
        if s["outputs"][out_slot]["type"].startswith("COMFY_MATCHTYPE"):
            s["outputs"][out_slot]["type"] = otype
        self._lid += 1
        lid = self._lid
        sock = next((x for x in d["inputs"] if x["name"] == inp), None)
        if sock is None:
            sock = {"name": inp, "type": otype, "link": None}
            if label:
                sock["label"] = label
            base = inp.split(".")[0]
            sch = SCHEMA.get(d["type"], {})
            for sect in ("required", "optional"):
                spec = sch.get("input", {}).get(sect, {}).get(base)
                if spec:
                    t = spec[0] if isinstance(spec[0], str) else "COMBO"
                    if t in WIDGET_TYPES and "." not in inp:
                        sock["widget"] = {"name": inp}
                        sock["type"] = "COMBO" if t == "COMBO" else t
                    if sect == "optional":
                        sock["shape"] = 7
            d["inputs"].append(sock)
        if sock["type"].startswith("COMFY_MATCHTYPE"):
            sock["type"] = otype
        sock["link"] = lid
        s["outputs"][out_slot]["links"].append(lid)
        d_slot = d["inputs"].index(sock)
        self.links.append([lid, src, out_slot, dst, d_slot, otype])
        if str(dst) in self.api:
            self.api[str(dst)]["inputs"][inp] = [str(src), out_slot]
        return lid

    def group(self, title, x, y, w, h, color):
        self.groups.append({"id": len(self.groups) + 1, "title": title,
                            "bounding": [x, y, w, h], "color": color, "flags": {}})

    def note(self, text, pos, size, title):
        return self.add("MarkdownNote", pos, size, ui_widgets=[text], title=title, colors=("#3d2f0a", "#2a2008"), api=False)

    # ---------------------------------------------------------------- output
    def ui(self):
        for n in self.nodes:
            for o in n["outputs"]:
                if not o["links"]:
                    o["links"] = None
        return {"id": "a1e3e000-0000-4000-8000-00000000a1e3", "revision": 0,
                "last_node_id": self._nid, "last_link_id": self._lid,
                "nodes": self.nodes, "links": self.links, "groups": self.groups,
                "config": {}, "extra": {"ds": {"scale": 0.55, "offset": [60, 120]},
                                        "aiempire": {"workflow": "H3 Video Cloner", "version": "1.0"}},
                "version": 0.4}


def text_gen(g, pos, title, clip, prompt_src, system_src, max_len, temp, video=None, audio=None, prompt_text=""):
    nid = g.add("TextGenerate", pos, (400, 330), title=title, colors=BRAIN, widgets=[
        ("prompt", prompt_text), ("max_length", max_len),
        ("sampling_mode", "on"), ("sampling_mode.temperature", temp), ("sampling_mode.top_k", 64),
        ("sampling_mode.top_p", 0.95), ("sampling_mode.min_p", 0.05),
        ("sampling_mode.repetition_penalty", 1.05), ("sampling_mode.seed", 7),
        ("sampling_mode.presence_penalty", 0.0),
        ("thinking", False), ("use_default_template", True), ("mtp", "auto"),
    ])
    g.link(clip, 0, nid, "clip")
    if prompt_src:
        g.link(prompt_src, 0, nid, "prompt")
    g.link(system_src, 0, nid, "system_prompt")
    if video:
        g.link(video[0], video[1], nid, "video")
    if audio:
        g.link(audio[0], audio[1], nid, "audio")
    return nid


def build(mode):
    g = Graph()
    m = MODES[mode]
    ref = mode == "ref"

    # ===================== column 1: ① YOUR CHARACTER ===================== #
    X1, Y = 0, 0
    g.group("① YOUR CHARACTER" if ref else "① YOUR START / END IMAGE", X1 - 20, Y + 200, 380, 1240, "#b58b2a")
    if ref:
        face = g.add("LoadImage", (X1, Y + 250), (340, 330), title="📸 Picture 1 · face close-up",
                     colors=GOLD, widgets=[("image", "face.png")], ui_widgets=["face.png", "image"])
        body = g.add("LoadImage", (X1, Y + 610), (340, 330), title="📸 Picture 2 · full body",
                     colors=GOLD, widgets=[("image", "body.png")], ui_widgets=["body.png", "image"])
        use_voice = g.add("PrimitiveBoolean", (X1, Y + 970), (340, 60), title="🎤 Use my voice reference?",
                          colors=GOLD, widgets=[("value", False)])
        voice = g.add("LoadAudio", (X1, Y + 1060), (340, 140), title="🎤 Voice sample (5-15 s of her talking)",
                      colors=GOLD, widgets=[("audio", "aiempire_no_voice.wav")],
                      ui_widgets=["aiempire_no_voice.wav", None, None])
        voice_sw = g.add("ComfySwitchNode", (X1, Y + 1230), (340, 80), title="voice on/off", colors=ENGINE,
                         widgets=[("switch", False)])
        g.link(use_voice, 0, voice_sw, "switch")
        g.link(voice, 0, voice_sw, "on_true", socket_type="AUDIO")
        voice_line = g.add("PrimitiveString", (X1, Y + 1340), (340, 60), title="voice line", colors=ENGINE,
                           widgets=[("value", "<Audio 1>: a recording of my character's voice.")])
        no_line = g.add("PrimitiveString", (X1, Y + 1340), (340, 60), title="empty", colors=ENGINE,
                        widgets=[("value", " ")])
        g.node(no_line)["pos"] = [X1, Y + 1380]
        line_sw = g.add("ComfySwitchNode", (X1 + 0, Y + 1300), (340, 80), title="voice text on/off",
                        colors=ENGINE, widgets=[("switch", False)])
        g.node(line_sw)["pos"] = [X1 + 380, Y + 1380]
        g.node(voice_sw)["pos"] = [X1 + 380, Y + 1290]
        g.node(voice_line)["pos"] = [X1, Y + 1290]
        g.link(use_voice, 0, line_sw, "switch")
        g.link(voice_line, 0, line_sw, "on_true", socket_type="STRING")
        g.link(no_line, 0, line_sw, "on_false", socket_type="STRING")
        refs = g.add("StringFormat", (X1 + 380, Y + 1470), (340, 160), title="references list", colors=ENGINE,
                     widgets=[("f_string", "<Picture 1>: close-up photo of my character's face.\n"
                                           "<Picture 2>: full-body photo of my character.\n{a}")])
        g.link(line_sw, 0, refs, "values.a", label="a", socket_type="STRING")
        g.node(voice_sw)["pos"] = [X1 + 380, Y + 1230]
        g.groups[-1]["bounding"][3] = 1240
    else:
        use_start = g.add("PrimitiveBoolean", (X1, Y + 250), (340, 60), title="🟢 Use a START image?",
                          colors=GOLD, widgets=[("value", True)])
        start = g.add("LoadImage", (X1, Y + 330), (340, 330), title="📸 START image (frame 1)",
                      colors=GOLD, widgets=[("image", "aiempire_blank.png")], ui_widgets=["aiempire_blank.png", "image"])
        use_end = g.add("PrimitiveBoolean", (X1, Y + 690), (340, 60), title="🔴 Use an END image?",
                        colors=GOLD, widgets=[("value", False)])
        end = g.add("LoadImage", (X1, Y + 770), (340, 330), title="📸 END image (last frame)",
                    colors=GOLD, widgets=[("image", "aiempire_blank.png")], ui_widgets=["aiempire_blank.png", "image"])
        start_sw = g.add("ComfySwitchNode", (X1 + 380, Y + 1230), (300, 80), title="start on/off",
                         widgets=[("switch", True)])
        end_sw = g.add("ComfySwitchNode", (X1 + 380, Y + 1330), (300, 80), title="end on/off",
                       widgets=[("switch", False)])
        g.link(use_start, 0, start_sw, "switch")
        g.link(start, 0, start_sw, "on_true", socket_type="IMAGE")
        g.link(use_end, 0, end_sw, "switch")
        g.link(end, 0, end_sw, "on_true", socket_type="IMAGE")
        refs = g.add("StringFormat", (X1 + 380, Y + 1440), (340, 140), title="frames list", colors=ENGINE,
                     widgets=[("f_string", "start image: {a}\nend image: {b}")])
        yn = []
        for i, flag in enumerate((use_start, use_end)):
            yes = g.add("PrimitiveString", (X1, Y + 1140 + 70 * i), (160, 60), title="yes", widgets=[("value", "yes")])
            no = g.add("PrimitiveString", (X1 + 180, Y + 1140 + 70 * i), (160, 60), title="no", widgets=[("value", "no")])
            sw = g.add("ComfySwitchNode", (X1 + 380, Y + 1630 + 90 * i), (300, 80), title="yes/no",
                       widgets=[("switch", False)])
            g.link(flag, 0, sw, "switch")
            g.link(yes, 0, sw, "on_true", socket_type="STRING")
            g.link(no, 0, sw, "on_false", socket_type="STRING")
            g.link(sw, 0, refs, "values." + "ab"[i], label="ab"[i], socket_type="STRING")

    # ===================== column 2: ② VIRAL VIDEO + ③ SETTINGS ===================== #
    X2 = 420
    g.group("② THE VIDEO TO COPY", X2 - 20, Y + 200, 380, 900, "#b58b2a")
    vid = g.add("VHS_LoadVideo", (X2, Y + 250), (340, 560), title="🎬 Viral video (5-15 s)", colors=GOLD,
                widgets=[("video", "viral.mp4"), ("force_rate", 24), ("custom_width", 0), ("custom_height", 0),
                         ("frame_load_cap", 360), ("skip_first_frames", 0), ("select_every_nth", 1),
                         ("format", "None")],
                ui_widgets={"video": "viral.mp4", "force_rate": 24, "custom_width": 0, "custom_height": 0,
                            "frame_load_cap": 360, "skip_first_frames": 0, "select_every_nth": 1,
                            "format": "None", "videopreview": {"hidden": False, "paused": False, "params": {}}})
    g.node(vid)["properties"]["cnr_id"] = "comfyui-videohelpersuite"
    changes = g.add("PrimitiveStringMultiline", (X2, Y + 840), (340, 230),
                    title="✏️ CHANGES (optional: new lines, outfit, place...)", colors=GOLD,
                    widgets=[("value", "")])

    g.group("③ SETTINGS", X2 - 20, Y + 1120, 380, 420, "#b58b2a")
    secs = g.add("PrimitiveFloat", (X2, Y + 1170), (340, 60), title="⏱ Length (seconds)", colors=GOLD,
                 widgets=[("value", 6.0)])
    res = g.add("ResolutionSelector", (X2, Y + 1260), (340, 130), title="📐 Shape & quality (0.6 fast · 1.0 sharp)",
                colors=GOLD, widgets=[("aspect_ratio", "9:16 (Portrait Widescreen)"), ("megapixels", 0.6),
                                      ("multiple", 32)])
    frames = g.add("ComfyMathExpression", (X2, Y + 1420), (340, 90), title="seconds → frames", colors=ENGINE,
                   widgets=[("expression", FRAMES_EXPR)])
    g.link(secs, 0, frames, "values.a", label="a")

    # ===================== column 3: 🧠 AI EMPIRE BRAIN ===================== #
    X3 = 840
    g.group("🧠 AI EMPIRE BRAIN · watches the video & writes the prompt (automatic)", X3 - 20, Y + 200, 900, 1340, "#2c3d63")
    gem = g.add("CLIPLoader", (X3, Y + 250), (400, 110), title="Gemma 4 12B (local, no API key)", colors=BRAIN,
                widgets=[("clip_name", GEMMA), ("type", "stable_diffusion"), ("device", "default")])
    sys1 = g.add("PrimitiveStringMultiline", (X3, Y + 390), (400, 300), title="system prompt · Video Analyst",
                 colors=BRAIN, widgets=[("value", PROMPTS["analyst"])])
    analyst = text_gen(g, (X3, Y + 720), "1 · watch the video", gem, None, sys1, 3072, 0.3,
                       video=(vid, 0), audio=(vid, 2),
                       prompt_text="Break down this clip using your format.")
    sys2 = g.add("PrimitiveStringMultiline", (X3 + 440, Y + 250), (420, 300),
                 title="system prompt · H3 Prompt Builder", colors=BRAIN,
                 widgets=[("value", PROMPTS["ref" if ref else "frames"])])
    brief = g.add("StringFormat", (X3 + 440, Y + 580), (420, 200), title="brief for the builder", colors=BRAIN,
                  widgets=[("f_string", ("REFERENCES:\n{a}" if ref else "FRAMES:\n{a}") +
                            "\n\nANALYSIS:\n{b}\n\nCHANGES:\n{c}\n\nDURATION: {d:.2f}")])
    g.link(refs, 0, brief, "values.a", label="a")
    g.link(analyst, 0, brief, "values.b", label="b")
    g.link(changes, 0, brief, "values.c", label="c")
    g.link(secs, 0, brief, "values.d", label="d")
    builder = text_gen(g, (X3 + 440, Y + 810), "2 · write the H3 prompt", gem, brief, sys2, 3072, 0.5)
    final = g.add("StringFormat", (X3 + 440, Y + 1170), (420, 110), title="add realism trigger", colors=BRAIN,
                  widgets=[("f_string", "r34l1sm, {a}")])
    g.link(builder, 0, final, "values.a", label="a")

    # ===================== column 4: previews ===================== #
    X4 = 1780
    g.group("👀 WHAT THE AI WROTE", X4 - 20, Y + 200, 520, 1340, "#2c3d63")
    p1 = g.add("PreviewAny", (X4, Y + 250), (480, 600), title="breakdown of the viral video", colors=BRAIN)
    g.link(analyst, 0, p1, "source")
    p2 = g.add("PreviewAny", (X4, Y + 880), (480, 620), title="final H3 prompt", colors=BRAIN)
    g.link(final, 0, p2, "source")

    # ===================== column 5: 🎬 H3 ENGINE ===================== #
    X5 = 2340
    g.group("🎬 MINIMAX H3 ENGINE · don't touch", X5 - 20, Y + 200, 820, 1340, "#444")
    unet = g.add("UNETLoader", (X5, Y + 250), (360, 90), widgets=[("unet_name", m["unet"]), ("weight_dtype", "default")])
    turbo = g.add("LoraLoaderModelOnly", (X5, Y + 370), (360, 90), title="⚡ Turbo 8-step LoRA",
                  widgets=[("lora_name", m["turbo"]), ("strength_model", 1.0)])
    g.link(unet, 0, turbo, "model")
    real = g.add("LoraLoaderModelOnly", (X5, Y + 490), (360, 90), title="🧍 Realism people LoRA (0.6-1.0)",
                 colors=GOLD, widgets=[("lora_name", REALISM), ("strength_model", 0.7)])
    g.link(turbo, 0, real, "model")
    shift = g.add("MiniMaxH3SigmaShift", (X5, Y + 610), (360, 90),
                  widgets=[("shift_video", 10.0), ("shift_audio", 3.0)])
    g.link(real, 0, shift, "model")
    te = g.add("CLIPLoader", (X5, Y + 730), (360, 110), widgets=[("clip_name", H3_TE), ("type", "minimax"), ("device", "default")])
    vae = g.add("VAELoader", (X5, Y + 870), (360, 60), title="video VAE", widgets=[("vae_name", VAE_V)])
    avae = g.add("VAELoader", (X5, Y + 960), (360, 60), title="audio VAE", widgets=[("vae_name", VAE_A)])

    if ref:
        cond = g.add("MiniMaxH3ReferenceToVideo", (X5 + 400, Y + 250), (380, 330), widgets=[
            ("prompt", ""), ("width", 576), ("height", 1024), ("length", 141), ("ref_image_size", "match")])
        g.link(te, 0, cond, "clip")
        g.link(vae, 0, cond, "vae")
        g.link(avae, 0, cond, "audio_vae")
        g.link(face, 0, cond, "ref_images.ref_image_0", label="ref_image_0")
        g.link(body, 0, cond, "ref_images.ref_image_1", label="ref_image_1")
        g.link(voice_sw, 0, cond, "ref_audios.ref_audio_0", label="ref_audio_0", socket_type="AUDIO")
    else:
        cond = g.add("MiniMaxH3ImageToVideo", (X5 + 400, Y + 250), (380, 330), widgets=[
            ("prompt", ""), ("width", 576), ("height", 1024), ("length", 141)])
        g.link(te, 0, cond, "clip")
        g.link(vae, 0, cond, "vae")
        g.link(start_sw, 0, cond, "first_frame", socket_type="IMAGE")
        g.link(end_sw, 0, cond, "last_frame", socket_type="IMAGE")
    g.link(final, 0, cond, "prompt")
    g.link(res, 0, cond, "width")
    g.link(res, 1, cond, "height")
    g.link(frames, 1, cond, "length")

    guider = g.add("BasicGuider", (X5 + 400, Y + 610), (380, 50))
    g.link(shift, 0, guider, "model")
    g.link(cond, 0, guider, "conditioning")
    sampler = g.add("KSamplerSelect", (X5 + 400, Y + 690), (380, 60), widgets=[("sampler_name", "res_multistep")])
    sched = g.add("BasicScheduler", (X5 + 400, Y + 780), (380, 110),
                  widgets=[("scheduler", "simple"), ("steps", 8), ("denoise", 1.0)])
    g.link(shift, 0, sched, "model")
    noise = g.add("RandomNoise", (X5 + 400, Y + 920), (380, 90), title="🎲 Seed", colors=GOLD,
                  widgets=[("noise_seed", 2026), ("control_after_generate", "randomize")])
    sca = g.add("SamplerCustomAdvanced", (X5 + 400, Y + 1040), (380, 110))
    g.link(noise, 0, sca, "noise")
    g.link(guider, 0, sca, "guider")
    g.link(sampler, 0, sca, "sampler")
    g.link(sched, 0, sca, "sigmas")
    g.link(cond, 1, sca, "latent_image")
    dec = g.add("VAEDecode", (X5, Y + 1180), (360, 50))
    g.link(sca, 0, dec, "samples")
    g.link(vae, 0, dec, "vae")
    adec = g.add("VAEDecodeAudio", (X5, Y + 1260), (360, 50))
    g.link(sca, 0, adec, "samples")
    g.link(avae, 0, adec, "vae")

    # ===================== column 6: 💾 RESULT ===================== #
    X6 = 3200
    g.group("💾 YOUR VIDEO", X6 - 20, Y + 200, 560, 1340, "#2a5a40")
    mk = g.add("CreateVideo", (X6, Y + 250), (520, 130), colors=OUT,
               widgets=[("fps", 24.0), ("bit_depth", "auto"), ("color_space", "sRGB"), ("codec", "none")])
    g.link(dec, 0, mk, "images")
    g.link(adec, 0, mk, "audio")
    save = g.add("SaveVideo", (X6, Y + 410), (520, 1000), title="💾 Saved to output/AIEmpire", colors=OUT,
                 widgets=[("filename_prefix", "AIEmpire/H3_" + mode), ("format", "auto"), ("format.codec", "auto")])
    g.link(mk, 0, save, "video")

    # ===================== header notes ===================== #
    if ref:
        how = ("# 👑 AI EMPIRE · H3 VIDEO CLONER\n"
               "**Copy any viral video with YOUR AI character, voice and all.**\n\n"
               "1. **①** Upload a face close-up and a full-body photo of your character. Voice sample? Turn the 🎤 switch on and upload 5-15 s of her talking.\n"
               "2. **②** Upload the viral video (5-15 s). Want different words or a new outfit? Write it in ✏️ CHANGES.\n"
               "3. **③** Pick the length. Leave the rest.\n"
               "4. Press **Run**. The 🧠 brain watches the video and writes the prompt for you, then H3 makes the video.\n\n"
               "⏳ First run loads ~65 GB of models, so be patient. Your video lands in **output/AIEmpire**.")
    else:
        how = ("# 👑 AI EMPIRE · H3 FIRST / LAST FRAME\n"
               "**Animate a photo of your character in the style of any viral video.**\n\n"
               "1. **①** Upload a START image, an END image, or both, and set the switches to match.\n"
               "2. **②** Upload the viral video to copy. Extra wishes go in ✏️ CHANGES.\n"
               "3. **③** Pick the length, press **Run**.\n\n"
               "⚠️ This mode needs the pod started with `FRAMES_MODE=1` (extra 23 GB download).")
    g.note(how, (0, -260), (1180, 420), "👑 START HERE")
    g.note("### 🧠 How the brain works\n"
           "Gemma 4 runs **on this pod**, so no API key and no extra cost.\n\n"
           "**Step 1** watches and listens to the viral video and writes a second-by-second breakdown.\n"
           "**Step 2** turns that breakdown into MiniMax H3's official prompt format, swapping the original person for your character.\n\n"
           "Read both results in **👀 WHAT THE AI WROTE**. Not happy with the prompt? Change ✏️ CHANGES and run again.",
           (1220, -260), (1040, 420), "how it works")
    g.note("### ⚖️ Licence\nMiniMax H3 is released under the **MiniMax H3 Community License**, which does **not** cover "
           "the EU, UK, USA or South Korea (including outputs). Check that it covers you before using it. "
           "Shown in this interface as required: **MiniMax H3**.\n\n© AI Empire · skool.com/aiempire",
           (2300, -260), (1440, 420), "licence")
    return g


def main():
    os.makedirs(os.path.join(ROOT, "workflows"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "tools", "api"), exist_ok=True)
    for mode, name in (("ref", "AI_Empire_H3_Reference"), ("frames", "AI_Empire_H3_FirstLast")):
        g = build(mode)
        with open(os.path.join(ROOT, "workflows", name + ".json"), "w") as f:
            json.dump(g.ui(), f, indent=1, ensure_ascii=False)
        with open(os.path.join(ROOT, "tools", "api", name + ".api.json"), "w") as f:
            json.dump(g.api, f, indent=1, ensure_ascii=False)
        print(f"built {name}: {len(g.nodes)} nodes, {len(g.links)} links")


if __name__ == "__main__":
    main()
