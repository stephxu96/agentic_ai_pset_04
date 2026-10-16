# AI Enters the CAD-to-Simulation Handoff

## Scene 1 — The answer

NARRATION:
What changed in AI for engineering? AI is moving into the handoffs inside the workflow: reusable CAD-feature creation and simulation setup. The answer is not that CAD has gained a better chat window. Onshape and SimScale describe systems that act at distinct engineering stages. These are meaningful workflow announcements for teams that can constrain inputs and retain engineering review. They do not establish dependable production geometry or correct simulation decisions. This video uses AI-generated presentation. As of October 16, 2026.

VISUAL NOTE:
A simple chain: “LLM request → reusable CAD feature → simulation setup → engineering decision.” Highlight the first two handoffs. Add a large label: “Workflow announcements, not validation.”

## Scene 2 — Onshape’s claim

NARRATION:
First, upstream in CAD. Onshape says its FeatureScript MCP Server connects large language models to Onshape and enables teams to generate custom features from natural-language requests. Onshape also says the workflow can carry requirements from an LLM request into Onshape.

This is text-to-code-to-CAD. FeatureScript is code for reusable parametric CAD functionality, not just a one-off geometry prompt. My interpretation is that this makes the workflow easier to inspect. A team can review the generated script, exercise its parameters, inspect the geometry, and check whether it implements intended design rules.

VISUAL NOTE:
Diagram: “Natural-language requirement → FeatureScript code → parametric custom feature.” Beside it, a review checklist: “Code; parameters; geometry; encoded rules.”

## Scene 3 — What that check does not establish

NARRATION:
Apply the core test: what was actually checked? Here, the evidence is Onshape’s product description. It supports what Onshape says the server enables.

It is not a disclosed test of generated FeatureScripts across requirements, edge cases, revisions, or manufacturing outcomes. So this source claim does not show that a generated feature preserves design intent in a production model. A valid-looking feature is not, by itself, proof that the design rules are right.

VISUAL NOTE:
Two-column comparison. Left: “Observed: Onshape product description.” Right: “Not shown: tests across edge cases, revisions, and manufacturing outcomes.” Stamp the right column: “Not established.”

## Scene 4 — SimScale moves downstream

NARRATION:
Downstream, Engineering.com reports that SimScale’s Engineering AI Agent is available through Onshape’s app store. SimScale says that, from one prompt, its agent can take a CAD model, propose a setup, mesh it, run physics, and report results in Onshape.

That is a broader handoff. It places an agent at simulation setup and execution. But a completed run is not evidence of a valid analysis.

VISUAL NOTE:
A CAD model enters a simulation pipeline: “propose setup → mesh → run physics → report results.” Put a check mark only beside “reported availability,” and a question mark over every simulation step.

## Scene 5 — The verification burden changes

NARRATION:
The difference matters. For a generated CAD feature, review can center on code, parameter behavior, geometry, and encoded rules.

For simulation, reviewers must also ask whether the abstraction answers the engineering question. Loads, boundary conditions, material assumptions, contact definitions, mesh choices, solver settings, and result interpretation all matter.

The observed checks here are narrow. Engineering.com supports the reported availability of the integration. The quoted release supports what SimScale says its agent can do in its described workflow. Neither presents a public comparison with engineer-reviewed ground truth, or a validation study showing results match the relevant physical system.

VISUAL NOTE:
Comparison table. CAD-feature review: “code, parameters, geometry, rules.” Simulation review: “loads, boundaries, materials, contacts, mesh, solver, interpretation.” Footer: “One prompt; different verification burden.”

## Scene 6 — Supporting robotics context

NARRATION:
Robotics provides supporting context, not proof for either CAD workflow. In an NVIDIA Robotics Office Hour, a presenter states that Newton physics for robot simulation is completely open source. The check is the presenter’s statement. It supports only NVIDIA’s claim about Newton’s availability and contribution model. It does not demonstrate simulator accuracy, transfer to hardware, or usefulness for a specific CAD-to-simulation workflow.

A Physical AI Podcast episode reports a blind evaluation with 10 manipulation tasks, three attempts per task, a shared time window, and a shared scoring sheet. If verified, that is closer to useful evaluation discipline: common tasks, bounded attempts, and a shared scoring procedure. But this is an automatic transcript, not underlying evaluation materials or a public grader. The figures and protocol details remain uncertain.

VISUAL NOTE:
Split screen. Left: “Newton: open source — source claim.” Right: a blind-evaluation card: “10 tasks; 3 attempts; shared time window; shared scoring sheet.” Add an uncertainty banner: “Transcript report; verify against audio, video, and evaluation materials.”

## Scene 7 — What to do next

NARRATION:
My interpretation is that AI is being attached to engineering interfaces, not merely offered as an assistant that drafts text. Teams should pilot these tools where inputs are constrained and engineering review remains explicit.

For CAD, require tests tied to intended rules and reusable parameters. For simulation, require reviewers to approve setup assumptions before treating outputs as decisions. Watch next for public task suites, disclosed graders, repeatable comparisons with engineer-authored setups, and evidence that connects a completed simulation to physical validation.

VISUAL NOTE:
Final checklist: “Constrain inputs. Review CAD rules. Approve simulation assumptions. Demand public checks.” End on: “What was checked, by whom, and under what conditions?”

