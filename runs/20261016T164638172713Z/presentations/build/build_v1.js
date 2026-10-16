// AI-assisted deck generator for run 20261016T164638172713Z (three narrated pieces).
const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");
const React = require("react");
const RDS = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");
const SKILL = "/Users/stephxu/.claude/skills/synced/b1bba7fb-4620-43d5-b5cb-902ec0e9177f_4b57c246-201a-4641-9536-25488f87a2a7/pptx";
const { applyTheme } = require(SKILL + "/scripts/apply_theme.js");

const SP = __dirname;
const OUT = process.argv[2];
const D = JSON.parse(fs.readFileSync(path.join(SP, "scenes.json"), "utf8"));

// ---------- shared editorial system ----------
const BASE = { dk2: "4A5663", lt1: "FFFFFF", lt2: "EEF1F4", accent2: "2E7D5B", accent3: "8F5A00", accent4: "5E4C94", accent5: "B3362B", accent6: "66707C", hlink: "1F5A99", folHlink: "5E4C94" };
const DECKS = {
  "01": { accent1: "0E6B73", dk1: "12292D", name: "AI Enters the CAD-to-Simulation Handoff" },
  "02": { accent1: "2C5596", dk1: "161E33", name: "A CAD File Is Not Yet an Engineering Workflow" },
  "03": { accent1: "3D4F5C", dk1: "231E21", name: "Pilot Where Mistakes Are Easy to Undo" },
};
const HEAD = "Cambria", BODY = "Calibri";
const L = 0.6, W = 12.133, R = L + W;

const WINDOWS = {
  "01": ["00:00–00:33", "00:33–01:10", "01:10–01:40", "01:40–02:07", "02:07–02:47", "02:47–03:40", "03:40–04:13"],
  "02": ["00:00–00:21", "00:21–00:47", "00:47–01:12", "01:12–01:37", "01:37–02:05", "02:05–02:40", "02:40–03:05", "03:05–03:29"],
  "03": ["00:00–00:24", "00:24–00:56", "00:56–01:33", "01:33–02:10", "02:10–02:50", "02:50–03:21", "03:21–03:54"],
};

const REFS = {
  "01": {
    on: "Onshape, “5 Ways Teams Can Leverage the Onshape FeatureScript MCP Server,” September 30, 2026. https://www.onshape.com/en/blog/featurescript-mcp-server-use-cases-text-code-cad",
    eng: "Engineering.com, “Multiphysics gets MCP server and Onshape gets SimScale agent,” September 23, 2026. https://www.engineering.com/multiphysics-gets-mcp-server-and-onshape-gets-simscale-agent/",
    nv: "NVIDIA, “What’s New in Newton Physics for Robot Simulation | Robotics Office Hour,” October 15, 2026, 18:10–18:13. https://www.youtube.com/watch?v=4dbaTrlaLJ8",
    pod: "Physical AI Podcast, “Black Forest Labs Beat NVIDIA, Figure's Rival Did the Maths,” September 26, 2026, 3:36–3:45. https://dts.podtrac.com/redirect.mp3/op3.dev/e,pg=83ccf97e-1d88-565b-ad28-0411c3a101af/physicalaipodcast.co/audio/episode-008.mp3",
  },
  "02": {
    eng: "Engineering.com, “Welcome to the vibe-CAD era,” September 30, 2026. https://www.engineering.com/welcome-to-the-vibe-cad-era/",
    mit: "MIT-CDFG, “On the Opportunities and Risks of Frontier Models for 3D Modeling, Computational Design and Robotics,” September 22, 2026. https://mit-cdfg.github.io/Survey-AI-for-3D-modeling-Robotics/",
    pod: "Physical AI Podcast, “AI Models Fail 63 of 84 Robot Tasks, Waymo Borrows $5B,” October 10, 2026, 00:02:47–00:02:51 and 00:03:48–00:03:55. https://dts.podtrac.com/redirect.mp3/op3.dev/e,pg=83ccf97e-1d88-565b-ad28-0411c3a101af/physicalaipodcast.co/audio/episode-010.mp3",
    cl: "Changelog Media, “Open models and the future of Physical AI with NVIDIA,” October 1, 2026, 00:23:59–00:24:19. https://pscrb.fm/rss/p/dts.podtrac.com/redirect.mp3/media.transistor.fm/217445d3/e1eb0b6a.mp3",
  },
  "03": {
    on: "Onshape, “Introducing AI Descriptive Image Search from Onshape Labs,” October 5, 2026. https://www.onshape.com/en/blog/ai-generated-thumbnail-description-search",
    nv: "NVIDIA, “5 Steps to Create SimReady Assets for Robotics with Frontier AI Models,” October 8, 2026, video passages at 00:20–00:50. https://www.youtube.com/shorts/H5UaOdIZERw",
    eng: "Engineering.com, “Autodesk’s AI push is actually a pull,” September 22, 2026. https://www.engineering.com/autodesks-ai-push-is-actually-a-pull/",
    pod: "Physical AI Podcast, “Atlas Loses Its Pinky, Only One Humanoid in Eight Walks,” October 3, 2026, audio passage at 07:28–07:35. https://physicalaipodcast.co/episodes/009",
    wl: "World Labs, “World Labs is Joining AMD,” September 28, 2026. https://www.worldlabs.ai/blog/amd-announcement",
  },
};

const EV = {
  fact: { label: "REPORTED FACT", c: "accent2" },
  claim: { label: "SOURCE CLAIM", c: "accent3" },
  infer: { label: "EDITORIAL INFERENCE", c: "accent4" },
  unver: { label: "UNVERIFIED · TRANSCRIPT", c: "accent6", dashed: true },
  none: { label: "NOT ESTABLISHED", c: "accent5" },
};

function mmss(t) { const m = Math.floor(t / 60), s = t - m * 60; return `${String(m).padStart(2, "0")}:${s.toFixed(1).padStart(4, "0")}`; }

async function iconData(Comp, hex) {
  const svg = RDS.renderToStaticMarkup(React.createElement(Comp, { color: "#" + hex, size: 256 }));
  const buf = await sharp(Buffer.from(svg)).resize(256, 256).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

async function buildDeck(n) {
  const deck = DECKS[n];
  const THEME = { name: "Engineering Evidence " + n, headFontFace: HEAD, bodyFontFace: BODY, colors: Object.assign({}, BASE, { accent1: deck.accent1, dk1: deck.dk1 }) };
  const hex = THEME.colors;
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE";
  pres.theme = { headFontFace: HEAD, bodyFontFace: BODY };
  pres.title = deck.name;
  pres.author = "Steph Xu";
  pres.subject = "AI-ASSISTED";
  const C = pres.SchemeColor;
  const footer = `AI-ASSISTED · ${deck.name}`;

  const ICON = {
    check: await iconData(fa.FaCheckCircle, hex.accent2),
    q: await iconData(fa.FaQuestionCircle, hex.accent3),
    x: await iconData(fa.FaTimesCircle, hex.accent5),
    chat: await iconData(fa.FaRegCommentDots, hex.accent1),
    lock: await iconData(fa.FaLock, "FFFFFF"),
    search: await iconData(fa.FaSearch, hex.dk2),
    cube: await iconData(fa.FaCube, hex.accent6),
  };

  const darkCommon = (titleY, titleH, size) => ({
    background: { color: C.text1 },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: L, y: titleY, w: W, h: titleH, fontSize: size, bold: true, color: C.background1, valign: "top", align: "left", margin: 0 }, text: "" } },
      { text: { text: footer, options: { x: L, y: 7.0, w: 11, h: 0.3, fontSize: 10, color: C.background2, margin: 0 } } },
    ],
    slideNumber: { x: 12.23, y: 7.0, w: 0.5, h: 0.3, fontSize: 10, color: C.background2, align: "right" },
  });
  pres.defineSlideMaster(Object.assign({ title: "DARK_OPEN" }, darkCommon(1.0, 1.3, 40)));
  pres.defineSlideMaster(Object.assign({ title: "DARK_CLOSE" }, darkCommon(0.45, 0.85, 32)));
  pres.defineSlideMaster({
    title: "CONTENT",
    background: { color: C.background1 },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: L, y: 0.42, w: W, h: 0.85, fontSize: 32, bold: true, color: C.text1, valign: "middle", align: "left", margin: 0 }, text: "" } },
      { text: { text: footer, options: { x: L, y: 7.0, w: 11, h: 0.3, fontSize: 10, color: C.text2, margin: 0 } } },
    ],
    slideNumber: { x: 12.23, y: 7.0, w: 0.5, h: 0.3, fontSize: 10, color: C.text2, align: "right" },
  });

  // ---------- drawing helpers ----------
  let objN = 0;
  const nm = (p) => `${p}-${++objN}`;
  const T = (s, text, o) => s.addText(text, Object.assign({ isTextBox: true, margin: 0, fontSize: 16, color: C.text1, valign: "top", objectName: nm("text") }, o));
  const node = (s, x, y, w, h, text, o = {}) => s.addText(text, Object.assign({
    shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.08, x, y, w, h, align: "center", valign: "middle", margin: 6,
    fontSize: 15, bold: true, color: C.text1, fill: { color: C.background2 }, line: { color: C.background2, width: 1 }, objectName: nm("node"),
  }, o));
  const rect = (s, x, y, w, h, o = {}) => s.addShape(pres.shapes.ROUNDED_RECTANGLE, Object.assign({ x, y, w, h, rectRadius: 0.1, fill: { color: C.background2 }, line: { color: C.background2, width: 1 }, objectName: nm("panel") }, o));
  const hArrow = (s, x1, x2, y, color = C.text2, o = {}) => s.addShape(pres.shapes.LINE, { x: x1, y, w: x2 - x1, h: 0, line: Object.assign({ color, width: 2, endArrowType: "triangle" }, o), objectName: nm("arrow") });
  const tag = (s, type, x, y, dark = false) => {
    const e = EV[type], w = e.label.length * 0.092 + 0.36;
    s.addText(e.label, {
      shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.13, x, y, w, h: 0.28, margin: 0, align: "center", valign: "middle",
      fontSize: 10, bold: true, charSpacing: 1, isTextBox: true, objectName: nm("evidence-tag"),
      color: e.dashed ? (dark ? C.background2 : C.accent6) : C.background1,
      fill: e.dashed ? { color: dark ? C.text1 : C.background1 } : { color: C[e.c] },
      line: e.dashed ? { color: dark ? C.background2 : C.accent6, width: 1.25, dashType: "dash" } : { color: C[e.c], width: 1 },
    });
    return w;
  };
  const tagNote = (s, type, x, y, text, o = {}) => { const w = tag(s, type, x, y, o.dark); T(s, text, Object.assign({ x: x + w + 0.15, y: y - 0.03, w: (o.w || W) - w - 0.15, h: 0.34, fontSize: 14, color: o.dark ? C.background2 : C.text2, valign: "middle" }, o.t || {})); };
  const src = (s, text, dark = false) => T(s, "Source: " + text, { x: L, y: 6.56, w: W, h: 0.34, fontSize: 11, color: dark ? C.background2 : C.text2, valign: "middle" });
  const icon = (s, k, x, y, d) => s.addImage({ data: ICON[k], x, y, w: d, h: d, objectName: nm("icon-" + k) });
  const legend = (s, y) => {
    T(s, "Evidence labels:", { x: L, y: y - 0.03, w: 1.6, h: 0.34, fontSize: 12, color: C.background2, valign: "middle" });
    let x = L + 1.55;
    for (const k of ["fact", "claim", "infer", "unver", "none"]) { x += tag(s, k, x, y, true) + 0.18; }
  };
  const hflow = (s, labels, { x, y, w, h, gap = 0.5, styles = [], size = 15, arrowColor = C.text2 }) => {
    const nw = (w - gap * (labels.length - 1)) / labels.length, pos = [];
    labels.forEach((lab, i) => {
      const nx = x + i * (nw + gap);
      node(s, nx, y, nw, h, lab, Object.assign({ fontSize: size }, styles[i] || {}));
      if (i < labels.length - 1) hArrow(s, nx + nw + 0.06, nx + nw + gap - 0.06, y + h / 2, arrowColor);
      pos.push({ x: nx, w: nw });
    });
    return pos;
  };

  const scenes = D[n];
  const slides = [];
  const add = (layout, title, refs, draw) => slides.push({ layout, title, refs, draw });

  // ---------- slide content ----------
  if (n === "01") {
    add("DARK_OPEN", "AI enters the CAD-to-simulation handoff", ["on", "eng"], (s) => {
      T(s, "AS OF OCTOBER 16, 2026  ·  THIS PRESENTATION USES AI-GENERATED NARRATION", { x: L, y: 0.5, w: W, h: 0.35, fontSize: 12, bold: true, charSpacing: 2, color: C.background2 });
      const labels = ["Natural-language request", "Reusable CAD feature", "Simulation setup", "Engineering decision"];
      const st = [
        { fill: { color: C.background1, transparency: 88 }, line: { color: C.background2, width: 1 }, color: C.background1 },
        { fill: { color: C.accent1 }, line: { color: C.accent1 }, color: C.background1 },
        { fill: { color: C.accent1 }, line: { color: C.accent1 }, color: C.background1 },
        { fill: { color: C.text1 }, line: { color: C.background2, width: 1, dashType: "dash" }, color: C.background2, bold: false },
      ];
      const pos = hflow(s, labels, { x: L, y: 2.75, w: W, h: 1.05, gap: 0.75, styles: st, size: 18, arrowColor: C.background2 });
      T(s, "Handoff 1: Onshape FeatureScript server", { x: pos[0].x + pos[0].w - 0.9, y: 3.95, w: 2.6, h: 0.6, fontSize: 13, color: C.background2, align: "center" });
      T(s, "Handoff 2: SimScale agent", { x: pos[1].x + pos[1].w - 0.9, y: 3.95, w: 2.6, h: 0.6, fontSize: 13, color: C.background2, align: "center" });
      T(s, "Workflow announcements, not validation", { x: L, y: 4.75, w: W, h: 0.7, fontSize: 30, italic: true, fontFace: HEAD, color: C.background1 });
      legend(s, 5.85);
      src(s, "Onshape, Sept. 30, 2026; Engineering.com, Sept. 23, 2026", true);
    });
    add("CONTENT", "Onshape: from a sentence to CAD code", ["on"], (s) => {
      tagNote(s, "claim", L, 1.6, "Onshape says its FeatureScript MCP Server connects AI language models to Onshape", { w: 7.6 });
      const pos = hflow(s, ["Natural-language requirement", "FeatureScript code", "Parametric custom feature"], {
        x: L, y: 2.35, w: 7.5, h: 1.15, gap: 0.55, size: 16,
        styles: [{}, { fill: { color: C.accent1 }, line: { color: C.accent1 }, color: C.background1 }, {}],
      });
      T(s, "Code for reusable CAD functionality that adapts to its inputs, not a one-off shape", { x: pos[1].x - 0.35, y: 3.65, w: pos[1].w + 0.7, h: 0.75, fontSize: 13, color: C.text2, align: "center" });
      T(s, "Text → code → CAD", { x: L, y: 4.75, w: 7.5, h: 0.6, fontSize: 28, fontFace: HEAD, bold: true, color: C.accent1 });
      T(s, "Requirements travel from the request into Onshape as code a team can read.", { x: L, y: 5.4, w: 7.4, h: 0.7, fontSize: 16, color: C.text2 });
      rect(s, 8.65, 1.6, 4.08, 4.6);
      tag(s, "infer", 8.95, 1.9);
      T(s, "Easier to inspect: what a team can review", { x: 8.95, y: 2.35, w: 3.5, h: 0.8, fontSize: 18, bold: true });
      ["Code", "Parameters", "Geometry", "Encoded design rules"].forEach((t, i) => {
        const y = 3.35 + i * 0.68;
        s.addShape(pres.shapes.RECTANGLE, { x: 8.95, y: y + 0.07, w: 0.3, h: 0.3, fill: { color: C.background1 }, line: { color: C.accent1, width: 1.5 }, objectName: nm("checkbox") });
        T(s, t, { x: 9.45, y, w: 3.1, h: 0.44, fontSize: 18, valign: "middle" });
      });
      src(s, "Onshape, “5 Ways Teams Can Leverage the Onshape FeatureScript MCP Server,” Sept. 30, 2026");
    });
    add("CONTENT", "What Onshape's description does not show", ["on"], (s) => {
      rect(s, L, 1.6, 5.5, 4.6);
      tag(s, "claim", L + 0.3, 1.9);
      T(s, "OBSERVED", { x: L + 0.3, y: 2.4, w: 4.9, h: 0.3, fontSize: 12, bold: true, charSpacing: 2, color: C.text2 });
      T(s, "Onshape's product description", { x: L + 0.3, y: 2.75, w: 4.9, h: 1.0, fontSize: 28, fontFace: HEAD, bold: true });
      T(s, "Supports what Onshape says the server enables.", { x: L + 0.3, y: 3.85, w: 4.9, h: 0.6, fontSize: 16, color: C.text2 });
      T(s, "A valid-looking feature is not, by itself, proof that the design rules are right.", { x: L + 0.3, y: 4.85, w: 4.9, h: 1.0, fontSize: 17, italic: true, fontFace: HEAD });
      rect(s, 6.5, 1.6, 6.23, 4.6, { fill: { color: C.background1 }, line: { color: C.accent5, width: 1.25 } });
      T(s, "NOT SHOWN", { x: 6.8, y: 1.95, w: 3, h: 0.3, fontSize: 12, bold: true, charSpacing: 2, color: C.accent5 });
      T(s, "No disclosed test of generated FeatureScripts across:", { x: 6.8, y: 2.35, w: 5.6, h: 0.4, fontSize: 16, color: C.text2 });
      ["Requirements", "Edge cases", "Revisions", "Manufacturing outcomes"].forEach((t, i) => {
        node(s, 6.8, 2.95 + i * 0.75, 3.7, 0.55, t, { align: "left", margin: [12, 0, 0, 0], fontSize: 17, bold: false, fill: { color: C.background1 }, line: { color: C.accent6, width: 1, dashType: "dash" } });
      });
      s.addText("NOT\nESTABLISHED", { shape: pres.shapes.RECTANGLE, x: 10.75, y: 3.55, w: 1.7, h: 1.0, rotate: -8, align: "center", valign: "middle", fontSize: 16, bold: true, charSpacing: 1, color: C.accent5, fill: { color: C.background1 }, line: { color: C.accent5, width: 2.5 }, margin: 0, objectName: nm("stamp") });
      src(s, "Onshape, “5 Ways Teams Can Leverage the Onshape FeatureScript MCP Server,” Sept. 30, 2026");
    });
    add("CONTENT", "SimScale moves the agent downstream", ["eng"], (s) => {
      tagNote(s, "claim", L, 1.6, "SimScale says that, from one prompt, its Engineering AI Agent can:");
      const pos = hflow(s, ["CAD model", "Propose setup", "Mesh", "Run physics", "Report results in Onshape"], {
        x: L, y: 2.75, w: W, h: 1.1, gap: 0.5, size: 16,
        styles: [{ fill: { color: C.text1 }, line: { color: C.text1 }, color: C.background1 }],
      });
      for (let i = 1; i < 5; i++) icon(s, "q", pos[i].x + pos[i].w - 0.4, 2.5, 0.48);
      T(s, "Each simulation step is a claim, not a checked result", { x: pos[1].x, y: 4.0, w: 9, h: 0.4, fontSize: 13, color: C.accent3, italic: true });
      icon(s, "check", L, 4.75, 0.42);
      T(s, "Available through Onshape's app store", { x: L + 0.55, y: 4.75, w: 4.6, h: 0.42, fontSize: 18, bold: true, valign: "middle" });
      tag(s, "fact", 5.55, 4.82);
      T(s, "A completed run is not evidence of a valid analysis.", { x: L, y: 5.55, w: W, h: 0.6, fontSize: 24, fontFace: HEAD, italic: true });
      src(s, "Engineering.com, “Multiphysics gets MCP server and Onshape gets SimScale agent,” Sept. 23, 2026");
    });
    add("CONTENT", "One prompt, two verification burdens", ["eng"], (s) => {
      T(s, "Reviewing a generated CAD feature", { x: L, y: 1.55, w: 4.9, h: 0.45, fontSize: 18, bold: true });
      ["Code", "Parameter behavior", "Geometry", "Encoded rules"].forEach((t, i) =>
        node(s, L, 2.15 + i * 0.58, 4.6, 0.46, t, { fontSize: 15, bold: false, align: "left", margin: [12, 0, 0, 0] }));
      T(s, "Reviewing an agent's simulation", { x: 5.9, y: 1.55, w: 6.8, h: 0.45, fontSize: 18, bold: true });
      node(s, 5.9, 2.15, 6.83, 0.46, "Does the model answer the engineering question?", { fontSize: 15, fill: { color: C.accent1 }, line: { color: C.accent1 }, color: C.background1, align: "left", margin: [12, 0, 0, 0] });
      ["Loads", "Boundary conditions", "Material assumptions", "Contact definitions", "Mesh choices", "Solver settings", "Result interpretation"].forEach((t, i) => {
        const col = i < 4 ? 0 : 1, row = i < 4 ? i : i - 4;
        node(s, 5.9 + col * 3.49, 2.73 + row * 0.58, 3.34, 0.46, t, { fontSize: 15, bold: false, align: "left", margin: [12, 0, 0, 0] });
      });
      rect(s, L, 5.15, W, 1.2, { fill: { color: C.background1 }, line: { color: C.accent6, width: 1 } });
      T(s, "What the sources checked", { x: L + 0.25, y: 5.25, w: 3, h: 0.32, fontSize: 13, bold: true, color: C.text2 });
      let w1 = tag(s, "fact", L + 0.25, 5.66);
      T(s, "The integration is available", { x: L + 0.4 + w1, y: 5.63, w: 3.0, h: 0.34, fontSize: 14, valign: "middle" });
      let w2 = tag(s, "claim", 6.0, 5.66);
      T(s, "What SimScale says its agent can do", { x: 6.15 + w2, y: 5.63, w: 4.6, h: 0.34, fontSize: 14, valign: "middle" });
      let w3 = tag(s, "none", L + 0.25, 6.0);
      T(s, "Not presented: a public comparison with engineer-reviewed setups, or a physical validation study", { x: L + 0.4 + w3, y: 5.97, w: 9.5, h: 0.34, fontSize: 14, valign: "middle" });
      src(s, "Engineering.com, “Multiphysics gets MCP server and Onshape gets SimScale agent,” Sept. 23, 2026");
    });
    add("CONTENT", "Robotics: context, not proof", ["nv", "pod"], (s) => {
      rect(s, L, 1.6, 5.85, 4.75);
      tag(s, "claim", L + 0.3, 1.9);
      T(s, "Newton physics for robot simulation", { x: L + 0.3, y: 2.35, w: 5.3, h: 0.35, fontSize: 15, color: C.text2 });
      T(s, "“Completely open source”", { x: L + 0.3, y: 2.75, w: 5.3, h: 0.65, fontSize: 30, fontFace: HEAD, bold: true });
      T(s, "A presenter's statement in an NVIDIA video", { x: L + 0.3, y: 3.42, w: 5.3, h: 0.35, fontSize: 14, color: C.text2 });
      T(s, "Supports: NVIDIA's claim about availability and how others can contribute", { x: L + 0.3, y: 4.0, w: 5.3, h: 0.7, fontSize: 15 });
      T(s, [{ text: "Does not show: ", options: { bold: true, color: C.accent5 } }, { text: "simulator accuracy, transfer to real hardware, or usefulness for a CAD-to-simulation workflow" }], { x: L + 0.3, y: 4.8, w: 5.3, h: 1.0, fontSize: 15 });
      rect(s, 6.88, 1.6, 5.85, 4.75, { fill: { color: C.background1 }, line: { color: C.accent6, width: 1.25, dashType: "dash" } });
      tag(s, "unver", 7.18, 1.9);
      T(s, "A blind robot evaluation, as reported", { x: 7.18, y: 2.35, w: 5.3, h: 0.4, fontSize: 17, bold: true });
      [["10", "manipulation tasks"], ["3", "attempts per task"], ["Shared", "time window"], ["Shared", "scoring sheet"]].forEach(([a, b], i) => {
        const x = 7.18 + (i % 2) * 2.7, y = 2.9 + Math.floor(i / 2) * 1.05;
        T(s, a, { x, y, w: 2.5, h: 0.6, fontSize: a.length > 2 ? 28 : 36, fontFace: HEAD, bold: true, color: C.accent1, valign: "bottom" });
        T(s, b, { x, y: y + 0.6, w: 2.5, h: 0.32, fontSize: 14, color: C.text2 });
      });
      T(s, "If verified, closer to useful evaluation discipline.", { x: 7.18, y: 5.0, w: 5.3, h: 0.32, fontSize: 14, italic: true });
      T(s, "Automatic transcript: verify against audio, video, and evaluation materials", { x: 7.18, y: 5.45, w: 5.3, h: 0.6, fontSize: 13, bold: true, color: C.accent6 });
      src(s, "NVIDIA, Robotics Office Hour, Oct. 15, 2026 (18:10–18:13); Physical AI Podcast, Sept. 26, 2026 (3:36–3:45)");
    });
    add("DARK_CLOSE", "Pilot where review stays explicit", ["on", "eng", "nv", "pod"], (s) => {
      tag(s, "infer", L, 1.5);
      [["Constrain inputs", "Pilot where inputs are constrained"],
       ["Review CAD rules", "Require tests tied to intended rules and reusable parameters"],
       ["Approve simulation assumptions", "Reviewers approve the setup before outputs become decisions"],
       ["Demand public checks", "Public task suites, disclosed graders, repeatable comparisons with engineer-authored setups, physical validation"]].forEach(([a, b], i) => {
        const y = 2.05 + i * 1.08;
        s.addText(String(i + 1), { shape: pres.shapes.OVAL, x: L, y, w: 0.55, h: 0.55, align: "center", valign: "middle", fontSize: 18, bold: true, color: C.background1, fill: { color: C.accent1 }, line: { color: C.accent1 }, margin: 0, objectName: nm("step") });
        T(s, a, { x: L + 0.8, y: y - 0.04, w: 6.6, h: 0.4, fontSize: 20, bold: true, color: C.background1 });
        T(s, b, { x: L + 0.8, y: y + 0.38, w: 6.6, h: 0.6, fontSize: 14, color: C.background2 });
      });
      T(s, "What was checked, by whom, and under what conditions?", { x: 8.55, y: 2.4, w: 4.18, h: 2.6, fontSize: 30, italic: true, fontFace: HEAD, color: C.background1, valign: "middle" });
      src(s, "Editorial recommendation drawing on Onshape (Sept. 30), Engineering.com (Sept. 23), NVIDIA (Oct. 15) and Physical AI Podcast (Sept. 26), 2026", true);
    });
  }

  if (n === "02") {
    add("DARK_OPEN", "A CAD file is not yet an engineering workflow", ["eng"], (s) => {
      T(s, "AS OF OCTOBER 16, 2026  ·  THIS PRESENTATION USES AI-GENERATED NARRATION", { x: L, y: 0.5, w: W, h: 0.35, fontSize: 12, bold: true, charSpacing: 2, color: C.background2 });
      T(s, "Backflip is the AI CAD tool tested. STEP is a neutral 3D file that any CAD tool can open. Fusion is Autodesk's CAD software.", { x: L, y: 2.0, w: W, h: 0.4, fontSize: 14, color: C.background2 });
      const pnl = { fill: { color: C.background1, transparency: 90 }, line: { color: C.background2, width: 0.75 } };
      rect(s, L, 2.65, 5.9, 2.85, pnl);
      rect(s, 6.83, 2.65, 5.9, 2.85, pnl);
      T(s, "NEUTRAL FILE", { x: L + 0.3, y: 2.85, w: 5, h: 0.3, fontSize: 12, bold: true, charSpacing: 2, color: C.background2 });
      const light = { fill: { color: C.background1 }, line: { color: C.background1 }, fontSize: 15 };
      hflow(s, ["Backflip STEP file", "Fusion import", "Mass check"], { x: L + 0.3, y: 3.35, w: 5.3, h: 0.95, gap: 0.4, styles: [light, light, light], arrowColor: C.background2 });
      node(s, L + 0.3, 4.6, 2.4, 0.55, "PASSED IN 2 TESTS", { fill: { color: C.accent2 }, line: { color: C.accent2 }, color: C.background1, fontSize: 14 });
      T(s, "EDITABLE CAD", { x: 7.13, y: 2.85, w: 5, h: 0.3, fontSize: 12, bold: true, charSpacing: 2, color: C.background2 });
      [["Native feature tree", "Partial"], ["Seven-body wire shelf", "1 of 7 bodies"]].forEach(([a, b], i) => {
        const y = 3.35 + i * 0.62;
        T(s, a, { x: 7.13, y, w: 3.0, h: 0.45, fontSize: 17, bold: true, color: C.background1, valign: "middle" });
        T(s, b, { x: 10.2, y, w: 2.2, h: 0.45, fontSize: 17, color: C.background2, valign: "middle" });
      });
      node(s, 7.13, 4.6, 2.4, 0.55, "NOT ESTABLISHED", { fill: { color: C.accent5 }, line: { color: C.accent5 }, color: C.background1, fontSize: 14 });
      legend(s, 5.85);
      src(s, "Engineering.com, “Welcome to the vibe-CAD era,” Sept. 30, 2026", true);
    });
    add("CONTENT", "Two mass checks passed after import", ["eng"], (s) => {
      [["Test 1", "Simplified TooTallToby drawing exercise", "Mass exactly correct"], ["Test 2", "Simplified TooTallToby drawing exercise", "Downloaded STEP file passed"]].forEach(([a, b, c], i) => {
        const x = L + i * 6.23;
        rect(s, x, 1.6, 5.9, 3.55);
        T(s, a, { x: x + 0.3, y: 1.85, w: 2, h: 0.45, fontSize: 22, fontFace: HEAD, bold: true });
        T(s, b, { x: x + 0.3, y: 2.3, w: 5.3, h: 0.35, fontSize: 14, color: C.text2 });
        const wh = { fill: { color: C.background1 }, line: { color: C.background1 } };
        hflow(s, ["Backflip STEP export", "Fusion import", "Apply material", "Mass check"], { x: x + 0.3, y: 2.95, w: 5.3, h: 1.0, gap: 0.3, size: 13, styles: [wh, wh, wh, { fill: { color: C.accent2 }, line: { color: C.accent2 }, color: C.background1 }] });
        icon(s, "check", x + 0.3, 4.3, 0.42);
        T(s, c, { x: x + 0.85, y: 4.3, w: 4.6, h: 0.42, fontSize: 17, bold: true, valign: "middle" });
      });
      const w = tag(s, "fact", L, 5.6);
      T(s, [{ text: "Observed: ", options: { bold: true } }, { text: "imported neutral geometry gave the expected mass with the selected material, in Fusion" }], { x: L + w + 0.15, y: 5.5, w: W - w - 0.15, h: 0.5, fontSize: 17, valign: "middle" });
      src(s, "Engineering.com, “Welcome to the vibe-CAD era,” Sept. 30, 2026");
    });
    add("CONTENT", "A mass check has a narrow scope", ["eng", "mit"], (s) => {
      const hd = { bold: true, fontSize: 15, color: C.background1, fill: { color: C.text1 }, valign: "middle", margin: [0.05, 0.12, 0.05, 0.12] };
      const cell = { fontSize: 16, color: C.text1, valign: "middle", margin: [0.05, 0.12, 0.05, 0.12] };
      const rows = [[{ text: "Checked", options: hd }, { text: "Not checked by this test", options: hd }]];
      const nc = ["Feature history (editable design intent)", "Dimensional tolerances", "Assembly relationships", "Manufacturability", "Physical inspection"];
      nc.forEach((t, i) => rows.push(i === 0
        ? [{ text: "Mass after STEP import", options: Object.assign({}, cell, { rowspan: 5, bold: true, color: C.accent2, fill: { color: C.background2 } }) }, { text: t, options: cell }]
        : [{ text: t, options: cell }]));
      s.addTable(rows, { x: L, y: 1.6, w: 7.6, colW: [3.0, 4.6], rowH: [0.5, 0.7, 0.7, 0.7, 0.7, 0.7], border: { type: "solid", pt: 0.75, color: hex.lt2 }, objectName: nm("scope-table") });
      tag(s, "infer", 8.7, 1.6);
      T(s, "Passing mass after STEP import is evidence about the file. It does not establish native editability, tolerance conformance, or manufacturability.", { x: 8.7, y: 2.1, w: 4.03, h: 2.7, fontSize: 21, fontFace: HEAD });
      T(s, "That is the test's scope, not a criticism of it.", { x: 8.7, y: 4.95, w: 4.03, h: 0.7, fontSize: 15, italic: true, color: C.text2 });
      src(s, "Engineering.com, “Welcome to the vibe-CAD era,” Sept. 30, 2026; MIT-CDFG survey, Sept. 22, 2026");
    });
    add("CONTENT", "The counterchecks: editable and multibody", ["eng"], (s) => {
      [0, 1].forEach((i) => rect(s, L + i * 6.23, 1.6, 5.9, 4.1));
      // Panel 1: partial recreation (schematic)
      T(s, "Drawing-to-CAD trial, Fusion add-in", { x: L + 0.3, y: 1.85, w: 5.3, h: 0.4, fontSize: 18, bold: true });
      s.addShape(pres.shapes.RECTANGLE, { x: L + 0.9, y: 2.75, w: 1.6, h: 1.8, fill: { color: C.accent1 }, line: { color: C.accent1 }, objectName: nm("recreated") });
      s.addShape(pres.shapes.RECTANGLE, { x: L + 2.5, y: 3.75, w: 2.4, h: 0.8, fill: { color: C.background1 }, line: { color: C.accent6, width: 1.5, dashType: "dash" }, objectName: nm("missing") });
      T(s, "recreated", { x: L + 0.9, y: 4.6, w: 1.6, h: 0.3, fontSize: 11, color: C.text2, align: "center" });
      T(s, "not recreated", { x: L + 2.5, y: 4.6, w: 2.4, h: 0.3, fontSize: 11, color: C.text2, align: "center" });
      T(s, "Observed: partial geometry recreation", { x: L + 0.3, y: 5.0, w: 5.3, h: 0.35, fontSize: 16, bold: true });
      T(s, "Schematic, not the tested part", { x: L + 0.3, y: 5.33, w: 5.3, h: 0.3, fontSize: 11, italic: true, color: C.text2 });
      // Panel 2: 1 of 7 bodies
      const x2 = L + 6.23;
      T(s, "Multibody wire-shelf test", { x: x2 + 0.3, y: 1.85, w: 5.3, h: 0.4, fontSize: 18, bold: true });
      for (let k = 0; k < 7; k++) {
        s.addShape(pres.shapes.RECTANGLE, { x: x2 + 0.45 + k * 0.72, y: 2.75, w: 0.55, h: 1.8, fill: { color: k === 0 ? C.accent1 : C.background1 }, line: { color: k === 0 ? C.accent1 : C.accent6, width: 1.5, dashType: k === 0 ? "solid" : "dash" }, objectName: nm("body") });
      }
      T(s, "seven bodies; one created", { x: x2 + 0.45, y: 4.6, w: 4.9, h: 0.3, fontSize: 11, color: C.text2 });
      T(s, "Observed: 1 of 7 bodies created", { x: x2 + 0.3, y: 5.0, w: 5.3, h: 0.35, fontSize: 16, bold: true });
      T(s, "Schematic, not the tested shelf", { x: x2 + 0.3, y: 5.33, w: 5.3, h: 0.3, fontSize: 11, italic: true, color: C.text2 });
      tag(s, "fact", L + 0.3, 2.3);
      tag(s, "fact", L + 6.53, 2.3);
      T(s, "A successful STEP export and a successful editable rebuild are separate claims.", { x: L, y: 5.85, w: W, h: 0.5, fontSize: 18, italic: true, fontFace: HEAD, valign: "middle" });
      src(s, "Engineering.com, “Welcome to the vibe-CAD era,” Sept. 30, 2026");
    });
    add("CONTENT", "The wider record: mostly demonstrations", ["mit"], (s) => {
      tagNote(s, "claim", L, 1.6, "MIT-CDFG's description of its own survey, not independent validation of each listed result");
      T(s, "1,646", { x: L, y: 2.2, w: 3.4, h: 0.85, fontSize: 52, fontFace: HEAD, bold: true, color: C.accent1, valign: "bottom" });
      T(s, "public posts reviewed", { x: L, y: 3.05, w: 3.4, h: 0.35, fontSize: 15, color: C.text2 });
      T(s, "707", { x: L, y: 3.6, w: 3.4, h: 0.85, fontSize: 52, fontFace: HEAD, bold: true, color: C.accent1, valign: "bottom" });
      T(s, "cases those posts cover", { x: L, y: 4.45, w: 3.4, h: 0.35, fontSize: 15, color: C.text2 });
      s.addChart(pres.charts.BAR, [{ name: "Cases", labels: ["All cases", "With runnable code"], values: [707, 132] }], {
        x: 4.2, y: 2.15, w: 4.6, h: 2.9, barDir: "bar", chartColors: [hex.accent1], showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 14, dataLabelColor: hex.dk1, dataLabelFontFace: "+mn-lt",
        catAxisLabelFontSize: 14, catAxisLabelColor: hex.dk2, catAxisLabelFontFace: "+mn-lt", valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false,
        showTitle: true, title: "Only 132 of 707 cases include runnable code", titleFontSize: 14, titleColor: hex.dk1, titleFontFace: "+mn-lt", catAxisOrientation: "maxMin", barGapWidthPct: 60, objectName: nm("runnable-chart"),
      });
      rect(s, 9.2, 2.15, 3.53, 2.9, { fill: { color: C.background1 }, line: { color: C.accent5, width: 1.5 } });
      icon(s, "x", 9.45, 2.4, 0.45);
      T(s, "Tolerance and manufacturability: not tested on physical parts", { x: 9.45, y: 2.95, w: 3.1, h: 1.3, fontSize: 18, bold: true, color: C.accent5 });
      T(s, "in the CAD evidence MIT-CDFG summarizes", { x: 9.45, y: 4.15, w: 3.1, h: 0.6, fontSize: 13, color: C.text2 });
      T(s, "MIT-CDFG says most listed capabilities are demonstrations rather than independent reproductions.", { x: L, y: 5.5, w: W, h: 0.5, fontSize: 16, valign: "middle" });
      src(s, "MIT-CDFG, “On the Opportunities and Risks of Frontier Models for 3D Modeling, Computational Design and Robotics,” Sept. 22, 2026");
    });
    add("CONTENT", "One score can hide different failures", ["pod"], (s) => {
      tagNote(s, "unver", L, 1.6, "Podcast source claims from automatic transcripts", { w: 7 });
      T(s, "5 frontier models, 84 Robot World tasks", { x: L, y: 2.05, w: 5.5, h: 0.35, fontSize: 15, bold: true });
      const sq = 0.34, g = 0.09;
      for (let k = 0; k < 84; k++) {
        const c = k % 12, r = Math.floor(k / 12), un = k < 63;
        s.addShape(pres.shapes.RECTANGLE, { x: L + c * (sq + g), y: 2.5 + r * (sq + g), w: sq, h: sq, fill: { color: un ? C.accent6 : C.background1 }, line: { color: un ? C.accent6 : C.accent1, width: 1.25 }, objectName: nm("task") });
      }
      const ly = 2.5 + 7 * (sq + g) + 0.1;
      s.addShape(pres.shapes.RECTANGLE, { x: L, y: ly + 0.06, w: 0.22, h: 0.22, fill: { color: C.accent6 }, line: { color: C.accent6 }, objectName: nm("key") });
      T(s, "63 unsolved by any model", { x: L + 0.32, y: ly, w: 2.6, h: 0.34, fontSize: 14, valign: "middle" });
      s.addShape(pres.shapes.RECTANGLE, { x: L + 2.9, y: ly + 0.06, w: 0.22, h: 0.22, fill: { color: C.background1 }, line: { color: C.accent1, width: 1.25 }, objectName: nm("key") });
      T(s, "21 solved by at least one", { x: L + 3.22, y: ly, w: 2.5, h: 0.34, fontSize: 14, valign: "middle" });
      // overlap of the two leading models
      T(s, "The two leading models", { x: 6.9, y: 2.05, w: 5.8, h: 0.35, fontSize: 15, bold: true });
      s.addShape(pres.shapes.OVAL, { x: 7.0, y: 2.55, w: 3.0, h: 3.0, fill: { color: C.accent1, transparency: 80 }, line: { color: C.accent1, width: 1.5 }, objectName: nm("model-a") });
      s.addShape(pres.shapes.OVAL, { x: 8.55, y: 2.55, w: 3.0, h: 3.0, fill: { color: C.accent4, transparency: 80 }, line: { color: C.accent4, width: 1.5 }, objectName: nm("model-b") });
      T(s, "8", { x: 8.55, y: 3.15, w: 1.45, h: 0.8, fontSize: 40, fontFace: HEAD, bold: true, align: "center", valign: "middle" });
      T(s, "shared\nsuccesses", { x: 8.55, y: 3.95, w: 1.45, h: 0.5, fontSize: 12, align: "center" });
      T(s, "Model A", { x: 7.3, y: 3.85, w: 1.6, h: 0.35, fontSize: 14, color: C.text2 });
      T(s, "Model B", { x: 9.9, y: 3.85, w: 1.4, h: 0.35, fontSize: 14, color: C.text2, align: "right" });
      T(s, "Individual totals not shown", { x: 7.0, y: 5.6, w: 4.55, h: 0.3, fontSize: 12, italic: true, color: C.text2, align: "center" });
      T(s, "Verify these numbers against the audio and the underlying study before publication.", { x: L, y: 5.95, w: W, h: 0.4, fontSize: 15, bold: true, color: C.accent6, valign: "middle" });
      src(s, "Physical AI Podcast, “AI Models Fail 63 of 84 Robot Tasks, Waymo Borrows $5B,” Oct. 10, 2026 (00:02:47–00:02:51; 00:03:48–00:03:55)");
    });
    add("CONTENT", "Define the output being tested", ["cl"], (s) => {
      tagNote(s, "claim", L, 1.6, "NVIDIA's Cosmos Lab vice president, describing world simulation");
      rect(s, L, 2.3, 3.6, 2.6);
      node(s, L + 0.25, 2.5, 3.1, 0.85, "Current observation", { fill: { color: C.background1 }, line: { color: C.background1 }, fontSize: 17 });
      T(s, "+", { x: L + 1.5, y: 3.38, w: 0.6, h: 0.45, fontSize: 24, bold: true, align: "center", valign: "middle", color: C.text2 });
      node(s, L + 0.25, 3.85, 3.1, 0.85, "Action input", { fill: { color: C.background1 }, line: { color: C.background1 }, fontSize: 17 });
      hArrow(s, 4.3, 5.05, 3.6);
      node(s, 5.15, 2.9, 3.0, 1.4, "World simulation", { fill: { color: C.accent1 }, line: { color: C.accent1 }, color: C.background1, fontSize: 19 });
      hArrow(s, 8.25, 9.0, 3.6);
      node(s, 9.1, 2.6, 3.63, 2.0, "Predicted future: video, audio, or other output", { fontSize: 17 });
      s.addText([{ text: "Not checked here: ", options: { bold: true } }, { text: "whether the prediction is physically correct, or transfers to a real robot" }], { shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.08, x: 6.6, y: 5.1, w: 6.13, h: 0.95, fontSize: 15, color: C.accent5, fill: { color: C.background1 }, line: { color: C.accent5, width: 1.5, dashType: "dash" }, margin: [12, 12, 0, 0], valign: "middle", objectName: nm("not-checked") });
      T(s, "A description of a capability, not evidence of its accuracy.", { x: L, y: 5.2, w: 5.7, h: 0.75, fontSize: 17, italic: true, fontFace: HEAD, valign: "middle" });
      src(s, "Changelog Media, “Open models and the future of Physical AI with NVIDIA,” Oct. 1, 2026 (00:23:59–00:24:19)");
    });
    add("DARK_CLOSE", "Five acceptance gates", ["eng", "mit"], (s) => {
      T(s, "Test each separately. What the evidence in this video shows at each gate:", { x: L, y: 1.45, w: 9.5, h: 0.4, fontSize: 15, color: C.background2 });
      const gates = [["STEP validation", "Mass check passed in 2 tests", "accent2"], ["Native editability", "Partial recreation", "accent5"], ["Multibody behavior", "1 of 7 bodies", "accent5"], ["Tolerances", "Not tested on physical parts", "accent5"], ["Manufacturability", "Not tested on physical parts", "accent5"]];
      const gw = (W - 4 * 0.25) / 5;
      gates.forEach(([a, b, c], i) => {
        const x = L + i * (gw + 0.25);
        rect(s, x, 2.0, gw, 2.35, { fill: { color: C.background1, transparency: 90 }, line: { color: C.background2, width: 0.75 } });
        T(s, String(i + 1), { x: x + 0.2, y: 2.15, w: 0.6, h: 0.45, fontSize: 20, fontFace: HEAD, bold: true, color: C.background2 });
        T(s, a, { x: x + 0.2, y: 2.6, w: gw - 0.3, h: 0.75, fontSize: 16, bold: true, color: C.background1 });
        node(s, x + 0.2, 3.45, gw - 0.4, 0.7, b, { fontSize: 13, fill: { color: C[c] }, line: { color: C[c] }, color: C.background1 });
      });
      T(s, "For each gate, record:", { x: L, y: 4.65, w: 2.6, h: 0.45, fontSize: 16, bold: true, color: C.background1, valign: "middle" });
      ["the file tested", "software used", "material assumptions", "who scored it", "failure cases"].forEach((t, i) =>
        node(s, 3.2 + i * 1.92, 4.65, 1.8, 0.45, t, { fontSize: 13, bold: false, fill: { color: C.text1 }, line: { color: C.background2, width: 0.75 }, color: C.background1 }));
      T(s, "Ask: what was checked, by whom, and under what conditions?", { x: L, y: 5.4, w: W, h: 0.7, fontSize: 26, italic: true, fontFace: HEAD, color: C.background1, valign: "middle" });
      src(s, "Engineering.com, Sept. 30, 2026; MIT-CDFG, Sept. 22, 2026. Gate list is an editorial recommendation", true);
    });
  }

  if (n === "03") {
    add("DARK_OPEN", "Pilot where mistakes are easy to undo", ["on", "nv", "eng"], (s) => {
      T(s, "AS OF OCTOBER 16, 2026  ·  THIS PRESENTATION USES AI-GENERATED NARRATION", { x: L, y: 0.5, w: W, h: 0.35, fontSize: 12, bold: true, charSpacing: 2, color: C.background2 });
      const base = 5.45;
      const st = { fill: { color: C.background1, transparency: 88 }, line: { color: C.background2, width: 0.75 }, color: C.background1, valign: "top", margin: [14, 10, 10, 10], align: "left", fontSize: 19 };
      node(s, L + 0.3, base - 0.95, 3.1, 0.95, "Discovery", st);
      node(s, 4.6, base - 1.65, 3.2, 1.65, "Simulation preparation", st);
      node(s, 9.2, base - 2.45, 3.53, 2.45, "PLM record", Object.assign({}, st, { fill: { color: C.background1 }, color: C.text1 }));
      T(s, "PLM (product lifecycle management): the official record of parts, revisions, and approvals", { x: 9.43, y: base - 1.85, w: 3.25, h: 1.2, fontSize: 13, color: C.text2 });
      hArrow(s, 4.05, 4.5, base - 0.5, C.background2);
      hArrow(s, 7.85, 8.2, base - 0.85, C.background2);
      hArrow(s, 8.75, 9.1, base - 0.85, C.background2);
      s.addShape(pres.shapes.RECTANGLE, { x: 8.3, y: base - 3.0, w: 0.4, h: 3.0, fill: { color: C.accent5 }, line: { color: C.accent5 }, objectName: nm("approval-gate") });
      icon(s, "lock", 8.38, base - 2.9, 0.24);
      T(s, "HUMAN APPROVAL", { x: 6.95, y: base - 3.42, w: 3.1, h: 0.35, fontSize: 13, bold: true, charSpacing: 2, color: C.background1, align: "center" });
      T(s, "Cost of an error rises with each step →", { x: L + 0.3, y: 2.4, w: 5.5, h: 0.4, fontSize: 15, italic: true, color: C.background2 });
      legend(s, 5.85);
      src(s, "Editorial interpretation based on Onshape (Oct. 5), NVIDIA (Oct. 8) and Engineering.com reporting on Autodesk (Sept. 22), 2026", true);
    });
    add("CONTENT", "Start with discovery", ["on"], (s) => {
      tagNote(s, "claim", L, 1.6, "Onshape says: an opt-in Onshape Labs feature, released for public documents only", { w: 7.3 });
      rect(s, L, 2.15, 6.7, 3.3);
      node(s, L + 0.3, 2.4, 6.1, 0.6, "red bracket", { align: "left", margin: [50, 0, 0, 0], bold: false, fontSize: 17, fill: { color: C.background1 }, line: { color: C.accent6, width: 1 } });
      icon(s, "search", L + 0.45, 2.53, 0.34);
      for (let k = 0; k < 3; k++) {
        const x = L + 0.3 + k * 2.1;
        rect(s, x, 3.2, 1.9, 1.5, { fill: { color: C.background1 }, line: { color: C.accent6, width: 1 } });
        icon(s, "cube", x + 0.7, 3.5, 0.5);
        T(s, "candidate " + (k + 1), { x, y: 4.15, w: 1.9, h: 0.35, fontSize: 12, align: "center", color: C.text2 });
      }
      T(s, "Schematic, not Onshape's interface", { x: L + 0.3, y: 4.88, w: 6.1, h: 0.3, fontSize: 11, italic: true, color: C.text2 });
      T(s, [{ text: "Observed check: ", options: { bold: true } }, { text: "retrieve public-document candidates from their thumbnails" }], { x: L, y: 5.6, w: 6.7, h: 0.7, fontSize: 16 });
      rect(s, 7.75, 2.15, 4.98, 4.15, { fill: { color: C.background1 }, line: { color: C.accent5, width: 1.25 } });
      T(s, "NOT CHECKED", { x: 8.05, y: 2.4, w: 3, h: 0.3, fontSize: 12, bold: true, charSpacing: 2, color: C.accent5 });
      ["Dimensions", "Material", "Tolerances", "Revision state"].forEach((t, i) => {
        icon(s, "x", 8.05, 2.9 + i * 0.6, 0.36);
        T(s, t, { x: 8.55, y: 2.88 + i * 0.6, w: 3.8, h: 0.4, fontSize: 18, valign: "middle" });
      });
      T(s, "A retrieved bracket may look right without being right.", { x: 8.05, y: 5.4, w: 4.4, h: 0.75, fontSize: 16, italic: true, fontFace: HEAD });
      src(s, "Onshape, “Introducing AI Descriptive Image Search from Onshape Labs,” Oct. 5, 2026");
    });
    add("CONTENT", "Simulation preparation: stronger checks", ["nv"], (s) => {
      tagNote(s, "claim", L, 1.6, "NVIDIA's walkthrough for preparing a robot asset for simulation");
      hflow(s, ["Reference material", "Check scale, parts, appearance", "Set joints, collision shapes, physical properties", "Rerun checks + grasp test", "Isaac Sim"], {
        x: L, y: 2.4, w: W, h: 1.55, gap: 0.42, size: 15,
        styles: [{}, {}, {}, {}, { fill: { color: C.accent1 }, line: { color: C.accent1 }, color: C.background1 }],
      });
      T(s, "NVIDIA's robot simulator", { x: 10.4, y: 4.05, w: 2.33, h: 0.3, fontSize: 12, color: C.text2, align: "center" });
      s.addShape(pres.shapes.LINE, { x: L, y: 4.85, w: W, h: 0, line: { color: C.accent5, width: 2, dashType: "dash" }, objectName: nm("boundary") });
      icon(s, "check", L, 4.3, 0.38);
      T(s, "Checked: readiness for the demonstrated simulated workflow", { x: L + 0.5, y: 4.3, w: 9, h: 0.38, fontSize: 16, bold: true, valign: "middle" });
      icon(s, "x", L, 5.05, 0.38);
      T(s, "Not shown: that a real robot will perform reliably in a physical environment", { x: L + 0.5, y: 5.05, w: 11, h: 0.38, fontSize: 16, bold: true, color: C.accent5, valign: "middle" });
      src(s, "NVIDIA, “5 Steps to Create SimReady Assets for Robotics with Frontier AI Models,” Oct. 8, 2026 (00:20–00:50)");
    });
    add("CONTENT", "Writing to PLM raises the stakes", ["eng"], (s) => {
      tagNote(s, "claim", L, 1.55, "Autodesk's Jeff Kinder: planned, expected “in the next couple of quarters.” Not deployed.");
      ["Slack", "Microsoft Teams", "Outlook"].forEach((t, i) => {
        const y = 2.15 + i * 1.0;
        node(s, L, y, 2.6, 0.75, t, { align: "left", margin: [52, 0, 0, 0], fontSize: 16, fill: { color: C.background1 }, line: { color: C.accent6, width: 1 } });
        icon(s, "chat", L + 0.15, y + 0.19, 0.38);
      });
      s.addShape(pres.shapes.LINE, { x: 3.25, y: 2.52, w: 0.8, h: 0.83, line: { color: C.text2, width: 1.75, endArrowType: "triangle" }, objectName: nm("arrow") });
      hArrow(s, 3.25, 4.05, 3.52);
      s.addShape(pres.shapes.LINE, { x: 3.25, y: 3.7, w: 0.8, h: 0.83, flipV: true, line: { color: C.text2, width: 1.75, endArrowType: "triangle" }, objectName: nm("arrow") });
      node(s, 4.15, 2.95, 2.3, 1.15, "AI inference", { fontSize: 18, fill: { color: C.background2 } });
      hArrow(s, 6.55, 7.25, 3.52);
      s.addText([{ text: "Human approval", options: { breakLine: true } }, { text: "+ audit trail" }], { shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.1, x: 7.35, y: 1.95, w: 2.45, h: 3.15, fill: { color: C.accent5 }, line: { color: C.accent5 }, color: C.background1, fontSize: 21, bold: true, align: "center", valign: "middle", margin: [8, 8, 8, 40], objectName: nm("approval-gate") });
      icon(s, "lock", 8.3, 2.25, 0.5);
      hArrow(s, 9.9, 10.55, 3.52);
      node(s, 10.65, 2.85, 2.08, 1.35, "PLM system of record", { fontSize: 17, fill: { color: C.text1 }, line: { color: C.text1 }, color: C.background1 });
      T(s, "Must be correct and auditable:", { x: L, y: 5.45, w: 3.4, h: 0.4, fontSize: 15, bold: true, valign: "middle" });
      ["extraction", "attribution", "revision context", "approval context", "entry into PLM"].forEach((t, i) =>
        node(s, 3.95 + i * 1.77, 5.45, 1.65, 0.42, t, { fontSize: 13, bold: false }));
      src(s, "Engineering.com, “Autodesk's AI push is actually a pull,” Sept. 22, 2026");
    });
    add("CONTENT", "Sequence adoption by consequence", ["on", "eng"], (s) => {
      const hd = { bold: true, fontSize: 14, color: C.background1, fill: { color: C.text1 }, valign: "middle", margin: [0.05, 0.12, 0.05, 0.12] };
      const c = { fontSize: 14, color: C.text1, valign: "middle", margin: [0.05, 0.12, 0.05, 0.12] };
      const b = Object.assign({}, c, { bold: true, fontSize: 16 });
      const rows = [
        [{ text: "Workflow", options: hd }, { text: "Observed check (per source)", options: hd }, { text: "If it is wrong", options: hd }, { text: "Required control", options: hd }],
        [{ text: "Discovery", options: b }, { text: "Retrieval from thumbnails; public documents only (Onshape)", options: c }, { text: "A person inspects the candidate before acting", options: c }, { text: "Human inspection", options: c }],
        [{ text: "Simulation preparation", options: b }, { text: "Scale, parts, appearance checks; rerun checks and grasp test, in simulation (NVIDIA)", options: c }, { text: "Traceable if the evidence is kept", options: c }, { text: "Keep references, asset changes, check results, simulation conditions", options: c }],
        [{ text: "Writing to PLM", options: b }, { text: "None disclosed; capability is planned (Autodesk)", options: c }, { text: "Inferred information becomes part of the official record", options: c }, { text: "Auditable approval required", options: Object.assign({}, b, { color: C.background1, fill: { color: C.accent5 } }) }],
      ];
      s.addTable(rows, { x: L, y: 1.6, w: W, colW: [2.3, 3.6, 3.1, 3.133], rowH: [0.5, 0.95, 1.05, 0.95], border: { type: "solid", pt: 0.75, color: hex.lt2 }, objectName: nm("adoption-table") });
      tagNote(s, "infer", L, 5.45, "Ordered by reversibility and consequence, from what each workflow says it does. Not a claim that any system is more accurate.");
      src(s, "Inference from Onshape, Oct. 5, 2026; NVIDIA, Oct. 8, 2026; Engineering.com, Sept. 22, 2026");
    });
    add("CONTENT", "Watch for physical-task evidence", ["nv", "pod"], (s) => {
      rect(s, L, 1.6, 5.9, 3.9);
      T(s, "SIMULATION", { x: L + 0.3, y: 1.85, w: 3, h: 0.3, fontSize: 12, bold: true, charSpacing: 2, color: C.text2 });
      T(s, "Grasp test in Isaac Sim", { x: L + 0.3, y: 2.25, w: 5.3, h: 0.6, fontSize: 24, fontFace: HEAD, bold: true });
      tag(s, "claim", L + 0.3, 3.05);
      T(s, "Part of NVIDIA's simulation-preparation workflow", { x: L + 0.3, y: 3.5, w: 5.3, h: 0.4, fontSize: 15, color: C.text2 });
      icon(s, "check", L + 0.3, 4.3, 0.4);
      T(s, "Checked in simulation, not physical deployment", { x: L + 0.85, y: 4.3, w: 4.8, h: 0.4, fontSize: 16, bold: true, valign: "middle" });
      rect(s, 6.83, 1.6, 5.9, 3.9, { fill: { color: C.background1 }, line: { color: C.accent6, width: 1.25, dashType: "dash" } });
      T(s, "PHYSICAL", { x: 7.13, y: 1.85, w: 3, h: 0.3, fontSize: 12, bold: true, charSpacing: 2, color: C.text2 });
      T(s, "Replicated real-robot tasks", { x: 7.13, y: 2.25, w: 4.6, h: 0.6, fontSize: 24, fontFace: HEAD, bold: true });
      icon(s, "q", 11.85, 1.85, 0.62);
      tag(s, "unver", 7.13, 3.05);
      T(s, "Podcast report: most cited world-action-model results came from simulation benchmarks; the real-robot result covered one task.", { x: 7.13, y: 3.5, w: 5.3, h: 1.0, fontSize: 15 });
      T(s, "Secondary report from an automatic transcript: check against the audio and underlying paper.", { x: 7.13, y: 4.6, w: 5.3, h: 0.7, fontSize: 13, bold: true, color: C.accent6 });
      tagNote(s, "infer", L, 5.8, "Physical-task replication is a more consequential watch item than another simulation-only demonstration.");
      src(s, "NVIDIA, Oct. 8, 2026; Physical AI Podcast, “Atlas Loses Its Pinky, Only One Humanoid in Eight Walks,” Oct. 3, 2026 (07:28–07:35)");
    });
    add("DARK_CLOSE", "Pilot, retain, approve, watch", ["wl", "on", "nv", "eng", "pod"], (s) => {
      tag(s, "infer", L, 1.5);
      [["Pilot retrieval", "A narrow retrieval pilot, with human inspection"],
       ["Retain simulation evidence", "References, asset changes, check results, simulation conditions"],
       ["Approve PLM writes", "Approval before inferred content becomes a record"],
       ["Watch deployment and physical replication", "Published deployment evidence, review controls, physical-task results beyond simulation"]].forEach(([a, b], i) => {
        const y = 2.05 + i * 1.08;
        s.addText(String(i + 1), { shape: pres.shapes.OVAL, x: L, y, w: 0.55, h: 0.55, align: "center", valign: "middle", fontSize: 18, bold: true, color: C.background1, fill: { color: i === 2 ? C.accent5 : C.accent1 }, line: { color: i === 2 ? C.accent5 : C.background2, width: 0.75 }, margin: 0, objectName: nm("step") });
        T(s, a, { x: L + 0.8, y: y - 0.04, w: 6.9, h: 0.4, fontSize: 20, bold: true, color: C.background1 });
        T(s, b, { x: L + 0.8, y: y + 0.38, w: 6.9, h: 0.6, fontSize: 14, color: C.background2 });
      });
      rect(s, 8.75, 2.05, 3.98, 3.6, { fill: { color: C.text1 }, line: { color: C.background2, width: 1, dashType: "dash" } });
      tag(s, "claim", 9.0, 1.65, true);
      T(s, "SEPARATE FROM CAPABILITY EVIDENCE", { x: 9.0, y: 2.25, w: 3.5, h: 0.55, fontSize: 11, bold: true, charSpacing: 1, color: C.background2 });
      T(s, "World Labs–AMD", { x: 9.0, y: 2.8, w: 3.5, h: 0.5, fontSize: 22, fontFace: HEAD, bold: true, color: C.background1 });
      T(s, "World Labs says it has signed a definitive agreement to join AMD, subject to regulatory approvals and customary closing conditions.", { x: 9.0, y: 3.35, w: 3.5, h: 1.4, fontSize: 14, color: C.background2 });
      T(s, "A proposed transaction, not evidence of what the technology can do.", { x: 9.0, y: 4.75, w: 3.5, h: 0.75, fontSize: 14, bold: true, color: C.background1 });
      src(s, "World Labs, “World Labs is Joining AMD,” Sept. 28, 2026; recommendations are editorial", true);
    });
  }

  if (slides.length !== scenes.length) throw new Error(`piece ${n}: ${slides.length} slides vs ${scenes.length} scenes`);
  const audioName = `piece${n}_voiceover.m4a`;
  slides.forEach((sd, i) => {
    const sc = scenes[i];
    pres.addSection && i === 0 && pres.addSection({ title: deck.name });
    const s = pres.addSlide({ masterName: sd.layout, sectionTitle: deck.name });
    s.addText(sd.title, { placeholder: "title" });
    sd.draw(s);
    const start = sc.start, end = sc.start + sc.slide_dur;
    const notes = [
      sc.narration,
      "",
      "———",
      `VOICEOVER CUE: ${mmss(start)}–${mmss(end)} in ${audioName} (AI-generated voice: Chatterbox clone of the author’s voice). Suggested script window: ${WINDOWS[n][i]}.`,
      `SCENE ${i + 1}: ${sc.title}`,
      "SOURCES:",
      ...sd.refs.map((k) => "- " + REFS[n][k]),
      "AI-ASSISTED.",
    ].join("\n");
    s.addNotes(notes);
  });

  const file = path.join(OUT, `piece${n}_${deck.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/-+$/, "")}.pptx`);
  await pres.writeFile({ fileName: file });
  await applyTheme(file, THEME);
  console.log(file);
  return file;
}

(async () => { for (const n of ["01", "02", "03"]) await buildDeck(n); })().catch((e) => { console.error(e); process.exit(1); });
