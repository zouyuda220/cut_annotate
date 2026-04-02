import streamlit as st
import streamlit.components.v1 as components
import re
import uuid
from urllib.parse import quote

# ===== COS 公网访问配置 =====
COS_BUCKET = "image-url-2-feature-1251524319"
COS_REGION = "ap-shanghai"
COS_PUBLIC_BASE_URL = f"https://{COS_BUCKET}.cos.{COS_REGION}.myqcloud.com"


def oss_key_to_cos_key(oss_key: str) -> str:
    """
    OSS 路径 → COS 路径
      user/zouyuda/shots/xxx/xxx.mp4
      → 0_zouyuda/shots/xxx/xxx.mp4

    规则：去掉开头的 'user/'，在第一段用户名前加 '0_'
    """
    oss_key = oss_key.strip()
    if oss_key.startswith("user/"):
        remainder = oss_key[len("user/"):]   # "zouyuda/shots/..."
        return "0_" + remainder              # "0_zouyuda/shots/..."
    return oss_key                           # 不符合规则则原样返回


def get_public_url(oss_key: str) -> str:
    """
    根据 OSS 路径直接拼出 COS 永久公网 URL
    """
    cos_key = oss_key_to_cos_key(oss_key)
    encoded_key = quote(cos_key, safe="/")
    return f"{COS_PUBLIC_BASE_URL}/{encoded_key}"


# ===== 配置 =====
CUT_TYPES = ["Scene Change", "Subject Change", "Camera Change", "Behavior Change"]

st.set_page_config(page_title="Cuts 编辑器", layout="wide")
st.markdown("""
<style>
    [data-testid="stColumn"]:nth-of-type(1) {
        position: sticky; top: 3rem; z-index: 100; align-self: flex-start;
    }
    .stButton>button { padding: 2px 10px; }
</style>
""", unsafe_allow_html=True)

# ===== 状态 =====
for k, v in {
    'cuts': None,
    'video_url': "",
    'seek_time': 0.0,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ===== 解析 / 导出 =====

def parse_cuts(text: str) -> list[dict]:
    cuts = []
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        header = re.match(r'\[\d+\]\s+([\d.]+)s', line)
        if not header:
            continue
        timestamp = float(header.group(1))
        rest = line[header.end():]
        parts = [p.strip() for p in re.split(r'[│|]', rest)]
        cut_type = parts[1] if len(parts) > 1 else ""
        desc = parts[2] if len(parts) > 2 else ""
        cuts.append({
            "id": str(uuid.uuid4()),
            "timestamp": timestamp,
            "type": cut_type,
            "desc": desc,
        })
    return cuts


def export_cuts(cuts: list[dict]) -> str:
    lines = []
    for i, c in enumerate(cuts):
        type_padded = c['type'].ljust(21)
        lines.append(f"[{i}]  {c['timestamp']:.1f}s   │ {type_padded} │ {c['desc']}")
    return "\n".join(lines)


def save_cuts_from_widgets():
    for c in st.session_state.cuts:
        cid = c["id"]
        if f"ts_{cid}" in st.session_state:
            c["timestamp"] = st.session_state[f"ts_{cid}"]
        if f"tp_{cid}" in st.session_state:
            c["type"] = st.session_state[f"tp_{cid}"]
        if f"dc_{cid}" in st.session_state:
            c["desc"] = st.session_state[f"dc_{cid}"]


def delete_cut(idx):
    save_cuts_from_widgets()
    cid = st.session_state.cuts[idx]["id"]
    st.session_state.cuts.pop(idx)
    for k in [k for k in st.session_state if k.endswith(f"_{cid}")]:
        del st.session_state[k]


def insert_cut_before(idx):
    save_cuts_from_widgets()
    ref_ts = st.session_state.cuts[idx]["timestamp"]
    prev_ts = st.session_state.cuts[idx-1]["timestamp"] if idx > 0 else 0.0
    new_ts = round((prev_ts + ref_ts) / 2, 1)
    st.session_state.cuts.insert(idx, {
        "id": str(uuid.uuid4()),
        "timestamp": new_ts,
        "type": "Scene Change",
        "desc": "",
    })


def append_cut():
    save_cuts_from_widgets()
    last_ts = st.session_state.cuts[-1]["timestamp"] if st.session_state.cuts else 0.0
    st.session_state.cuts.append({
        "id": str(uuid.uuid4()),
        "timestamp": last_ts + 5.0,
        "type": "Scene Change",
        "desc": "",
    })


# ===== 界面 =====
st.title("✂️ Cuts 编辑器")

with st.expander("⚙️ 设置视频 & 粘贴 cuts",
                 expanded=(st.session_state.cuts is None)):

    vc1, vc2 = st.columns(2)

    with vc1:
        st.markdown("**OSS路径（自动转为COS公网URL）**")
        oss_key = st.text_input(
            "",
            placeholder="user/zouyuda/shots/xxx/xxx.mp4",
            label_visibility="collapsed",
        )
        # 实时展示转换后的 COS 路径和公网 URL，方便核对
        if oss_key.strip():
            cos_preview = oss_key_to_cos_key(oss_key)
            public_url_preview = get_public_url(oss_key)
            st.caption(f"📦 COS路径预览：`{cos_preview}`")
            st.caption(f"🌐 公网URL预览：`{public_url_preview}`")

    with vc2:
        st.markdown("**粘贴 cuts 列内容（可留空）**")
        raw_cuts = st.text_area(
            "", height=180,
            placeholder=(
                "[0]  11.5s   │ Camera Change        │ The camera...\n"
                "[1]  14.2s   │ Subject Change       │ ...\n"
                "留空则直接进入编辑，手动追加 cut"
            ),
        )

        if st.button("↓ 解析 ↓", use_container_width=True, type="primary"):
            st.session_state.seek_time = 0.0

            if oss_key.strip():
                st.session_state.video_url = get_public_url(oss_key)
                cos_key = oss_key_to_cos_key(oss_key)
                st.success(f"✅ 视频已加载（COS路径：`{cos_key}`）")
            else:
                st.warning("未填写OSS路径，视频不会加载")

            if raw_cuts.strip():
                result = parse_cuts(raw_cuts)
                if result:
                    st.session_state.cuts = result
                    st.success(f"✅ 解析到 {len(result)} 个 cut")
                else:
                    st.error("未解析到内容，请检查格式")
            else:
                st.session_state.cuts = []
                st.info("ℹ️ 未粘贴 cuts，已清空，可手动追加")


st.divider()

if st.session_state.cuts is not None or st.session_state.video_url:

    if st.session_state.cuts is None:
        st.session_state.cuts = []

    col_vid, col_edit = st.columns([1.2, 2.5], gap="large")

    with col_vid:
        st.subheader("📺 视频")
        if st.session_state.video_url:
            player = f"""<!DOCTYPE html><html><head><style>
body{{margin:0;padding:0;background:transparent;font-family:sans-serif;}}
video{{width:100%;max-height:300px;background:#000;border-radius:8px;border:1px solid #555;}}
.ctrl{{background:#262730;padding:10px;border-radius:8px;margin-top:6px;}}
.row{{display:flex;align-items:center;gap:6px;margin-bottom:8px;}}
.t{{background:#000;color:#00ff00;font-family:monospace;font-size:16px;font-weight:bold;
    padding:3px 8px;border-radius:4px;border:1px solid #444;min-width:70px;text-align:center;}}
button{{background:#444;color:#fff;border:none;padding:5px 8px;border-radius:4px;
        cursor:pointer;font-size:12px;font-weight:bold;flex:1;}}
button:hover{{background:#666;}}
input[type=range]{{width:100%;accent-color:#ff4b4b;cursor:pointer;}}
.sl{{display:flex;align-items:center;gap:6px;}}
.lb{{color:#aaa;font-size:11px;font-family:monospace;white-space:nowrap;}}
</style></head><body>
<video id="v" src="{st.session_state.video_url}"
    playsinline preload="metadata"></video>
<div class="ctrl">
    <div class="row">
        <button onclick="togglePlay()">⏯</button>
        <button onclick="adj(-1)">-1s</button>
        <button onclick="adj(-0.1)">-0.1</button>
        <div class="t" id="td">0.0</div>
        <button onclick="adj(+0.1)">+0.1</button>
        <button onclick="adj(+1)">+1s</button>
    </div>
    <div class="sl">
        <span class="lb">0</span>
        <input type="range" id="sc" min="0" max="100" step="0.1" value="0">
        <span class="lb" id="dd">--</span>
    </div>
</div>
<script>
    const v  = document.getElementById('v');
    const sc = document.getElementById('sc');
    const td = document.getElementById('td');
    const dd = document.getElementById('dd');

    const round1 = t => Math.round(t * 10) / 10;
    const seekTarget = {st.session_state.seek_time};

    let isScrubbing = false;
    let wasPaused   = true;
    let lastSeeked  = -1;

    v.addEventListener('loadedmetadata', () => {{
        sc.max = v.duration;
        dd.innerText = round1(v.duration).toFixed(1);
        if (seekTarget > 0) {{
            v.currentTime = seekTarget;
            sc.value = seekTarget;
            td.innerText = seekTarget.toFixed(1);
        }} else {{
            v.currentTime = 0;
            sc.value = 0;
            td.innerText = "0.0";
        }}
    }});

    function togglePlay() {{ v.paused ? v.play() : v.pause(); }}

    function adj(delta) {{
        const t = round1(Math.max(0, Math.min(v.duration || 99999, v.currentTime + delta)));
        v.currentTime = t;
        sc.value = t;
        td.innerText = t.toFixed(1);
    }}

    sc.addEventListener('pointerdown', () => {{
        isScrubbing = true;
        wasPaused   = v.paused;
        v.pause();
        lastSeeked  = -1;
    }});

    sc.addEventListener('input', () => {{
        const t = round1(parseFloat(sc.value));
        td.innerText = t.toFixed(1);
        if (t !== lastSeeked) {{ lastSeeked = t; v.currentTime = t; }}
    }});

    sc.addEventListener('pointerup', () => {{
        const t = round1(parseFloat(sc.value));
        v.currentTime = t;
        isScrubbing = false;
        if (!wasPaused) v.play();
    }});

    sc.addEventListener('pointercancel', () => {{
        isScrubbing = false;
        if (!wasPaused) v.play();
    }});

    v.addEventListener('timeupdate', () => {{
        if (!isScrubbing) {{
            sc.value = v.currentTime;
            td.innerText = round1(v.currentTime).toFixed(1);
        }}
    }});
</script></body></html>"""
            components.html(player, height=420)
        else:
            st.warning("请在上方设置视频路径")

    with col_edit:
        st.subheader(f"✂️ Cuts 编辑（共 {len(st.session_state.cuts)} 个）")

        for i, c in enumerate(st.session_state.cuts):
            cid = c["id"]
            col_ts, col_seek, col_tp, col_ins, col_del = st.columns([1.2, 0.7, 1.8, 0.7, 0.7])

            with col_ts:
                st.number_input(
                    f"[{i}] 时间(s)",
                    min_value=0.0, step=0.1, format="%.1f",
                    value=c["timestamp"],
                    key=f"ts_{cid}",
                    on_change=save_cuts_from_widgets,
                )

            with col_seek:
                st.write("")
                st.button(
                    "🎯", key=f"seek_{cid}", help="跳转到该时间点",
                    on_click=lambda t=c["timestamp"]: st.session_state.update({"seek_time": t}),
                    use_container_width=True,
                )

            with col_tp:
                type_idx = CUT_TYPES.index(c["type"]) if c["type"] in CUT_TYPES else 0
                st.selectbox(
                    "类型", options=CUT_TYPES, index=type_idx,
                    key=f"tp_{cid}", label_visibility="collapsed",
                )

            with col_ins:
                st.write("")
                st.button(
                    "➕", key=f"ins_{cid}", help="在此行前插入一个cut",
                    on_click=insert_cut_before, args=(i,), use_container_width=True,
                )

            with col_del:
                st.write("")
                st.button(
                    "🗑️", key=f"del_{cid}", help="删除此cut",
                    on_click=delete_cut, args=(i,), use_container_width=True,
                )

            st.text_input(
                "描述", value=c["desc"], key=f"dc_{cid}",
                label_visibility="collapsed", placeholder="描述...",
            )
            st.markdown("---")

        if st.button("➕ 末尾追加 Cut", use_container_width=True):
            append_cut()
            st.rerun()

        if st.session_state.cuts:
            st.subheader("📋 导出")
            save_cuts_from_widgets()
            sorted_cuts = sorted(st.session_state.cuts, key=lambda x: x["timestamp"])
            st.code(export_cuts(sorted_cuts), language="text")

else:
    st.info("👆 请在上方填写OSS路径或粘贴 cuts 文本，然后点击解析")
