---
name: cinematic-capture-director
description: >-
  Use when directing footage of a real 3D world - trailer material, a camera move,
  a screenshot board, "make a video of the world". Owns the craft: deciding what a
  viewer must understand, an editorial spine, shot families, scouting with stills
  before any camera motion, approving start and end framing, then capturing long
  raw takes with editing handles. Project-agnostic; pair it with the project's own
  cinematics skill or docs for worlds, commands and constraints. Not for montage,
  audio, titles or colour grade.
metadata:
  version: "1.0"
---

# Cinematic capture director

You are directing footage of a real product. This is not generated video: every
frame comes out of an actual running world, rendered by the actual engine, and
any claim the footage makes must be true.

This skill owns the craft and nothing else. If the project carries its own
cinematics documentation or a project skill, that owns the worlds, the commands,
the constraints and the house style; read it alongside this and let it win on
anything specific.


## The one question

Before every shot, answer this and write it down:

> **What will a person who knows nothing about the product understand from this image?**

Not "does it look cinematic". A beautiful frame that teaches the viewer nothing is
a failed shot. A plain frame that makes someone say "wait, that whole city is
real and I can fly through it" is a good one.

A shot with no `viewer_question` does not get captured.

## Workflow

Run it in order. Each stage is cheap enough to throw away; the expensive stage is
last on purpose.

```text
purpose            what must the viewer learn
   |
editorial spine    an approximate minute, as a planning device
   |
shot families      one family per viewer question
   |
scouting stills    authenticated frames, no motion yet
   |
approved framing   start and end (and midpoint for complex moves)
   |
raw takes          long, with handles, 2-3 variants where it matters
   |
authentication     the frames are of the world we asked for
```

### 1. Read the purpose before touching a camera

Open the project vision and public messaging, the active release concern, and the
accepted evidence for the worlds involved. Decide the three to five things a
stranger must learn. Write them as sentences about the viewer, not about features.

Show the product's own concrete capability. Never stage something the product
cannot do, and never imply a capability the build does not have.

### 2. Draft an editorial spine

Sketch roughly a minute of beats. Mark it explicitly as a planning device, not a
montage commitment - it exists to justify why each shot is being collected, and
the real edit will diverge.

A workable default for a world-reconstruction piece:

| Beat | Job |
|---|---|
| open | prove it is a real product, not a render |
| reveal | establish scale; the viewer should feel the size |
| traverse | prove continuity and depth; parallax over a long move |
| feature | make the specific technical claim legible without text |
| second subject | prove the system is general, not one hand-built demo |

### 3. Decompose into shot families

A family answers exactly one viewer question. Name the question, the feature it
proves, the world, and what must be visible and what must be avoided.

Do not plan individual random cameras. Plan families, then variants inside them.

### 4. Scout with stills before motion

Generate candidate poses and capture them as stills through the authenticated
still route. Then look at them yourself and judge:

- **subject separation** - is the thing you are showing distinguishable from
  everything else, or is it lost in a grey field?
- **silhouette** - does the skyline or ridge read as a shape?
- **depth layers** - foreground, midground, background. Two layers is flat; three
  reads as a world.
- **horizon placement** - where it sits decides whether the shot is about the
  ground or the sky. Dead centre is usually the weakest choice.
- **dead space** - empty water, empty sky, empty haze. Some is composition; a lot
  is a wasted frame.
- **feature legibility** - is the thing this shot exists to prove actually big
  enough in frame to notice?
- **landmarks** - is anything recognisable in shot, and is it recognisable at
  this distance?

Iterate poses until the still communicates the goal. Stills are cheap; renders
are not.

### 5. Approve start and end framing before authoring motion

Every move is a journey between two frames. Authenticate both endpoint stills,
and a midpoint too when the path curves or the subject changes. If the endpoints
do not already tell the story as two photographs, the motion between them will
not rescue it. Fix the framing first.

### 6. Order the shot description consistently

When writing or reasoning about a shot, go in this order. It keeps the intent
stable and makes two shots comparable:

```text
subject -> context -> framing and lens -> camera motion -> atmosphere -> treatment
```

- **subject** - what the shot is of.
- **context** - where it sits and what surrounds it.
- **framing and lens** - shot size, angle, focal length intent. Wide reads as
  place; long reads as compression and distance. State the intent, not a number
  you cannot justify.
- **camera motion** - what moves, how fast, and why. Slow and readable beats fast
  and impressive for anything the viewer must comprehend. A move should reveal
  something: if the end frame teaches nothing the start frame did not, the move
  is decoration.
- **atmosphere** - light, time of day, haze, weather.
- **treatment** - anything deliberate about the render itself.

Camera motion vocabulary worth keeping straight, because they communicate
different things: a **push** commits the viewer to a subject; a **reveal** hides
then discloses; a **traverse** proves continuity through parallax; an **orbit**
describes an object but proves nothing about the world around it; a **descent**
converts scale into human scale.

### 7. Capture long, not to the edit

This is the rule most often broken, so it is stated as a hard constraint.

For every 3 to 6 seconds you expect to use in an edit, capture something closer
to 10 to 25 seconds. Establishing shots deserve 20 to 40.

Every take carries **handles**: two to three seconds of stable, usable frame
before the useful action begins and again after it ends. An edit without handles
cannot dissolve, cannot retime, and cannot slip the cut a few frames.

Where the framing decision is genuinely uncertain, capture 2 to 3 variants: one
safe and wide, one stronger, and optionally one from a different direction or
height. Not dozens. Storage is cheap next to reconstructing a camera move weeks
later; render time is not, so vary deliberately.

### 8. Pick the adapter by what the shot must prove

| The shot must prove | Use |
|---|---|
| the product is real: menu, loading, gameplay, playability | real runtime capture of an actual build |
| geography, scale, massing, controlled camera motion | Sequencer or CineCamera rendered through MRQ |
| framing candidates, review, before-and-after | authenticated still capture in the editor |

Never fake gameplay with an editor camera when the point of the shot is that a
player can do it. An editor flythrough proves the world exists; it does not prove
anyone can play it. Use the right one and say which you used.

### 9. Authenticate every take

The editor will happily open a fallback world and produce a beautiful,
technically valid capture of the wrong place. That has already happened in this
project.

Every take records, and every take is rejected on mismatch:

- the map actually loaded, compared against the map requested;
- the sequence and camera identity;
- duration, frame count, resolution, frame rate;
- the output path and its hash;
- the scalability level the capture ran at.

Then look at the footage: first frame, a middle frame, and the last frame at
minimum. MRQ producing bytes is not evidence that the bytes show anything.

### 10. Stop at raw

This skill ends with raw material and its records. Montage, music, titles,
voice-over, colour grade, and the final cut are a separate concern with a
separate owner. Do not drift into them.

## Where the reasoning goes

Keep the two apart, or the creative notes calcify into engine schema:

- **The shot plan** carries only what reproduces the camera - map, duration, lens,
  pose keys. It is machine input.
- **The shot board** - one small Markdown table beside the plans - carries the
  viewer question each take answers, the move in a phrase, and what the scouting
  pass settled. It is for people.

A line on the board is enough. Something like:

```text
city_scale_reveal | How large is this world? | low aerial pushing toward
the skyline, 420 m rising to 520 m | 24 s | show: skyline, river, continuous
city | avoid: world edge, empty foreground
```

Do not turn `viewer_question`, `handles_s`, `show` or `avoid` into required fields
a script validates. They are judgement, and judgement belongs where a person reads
it.

## Judgement notes

- **Motion speed is a comprehension budget.** The viewer must recognise what they
  are seeing before it leaves frame. If in doubt, slow down.
- **Scale needs a reference.** A huge city with nothing familiar in frame reads as
  a texture. Put something whose size the viewer already knows into the shot -
  a bridge, a river, a recognisable tower, a street grid.
- **Parallax is the proof of a world.** A static wide could be a photograph. Only
  relative motion between near and far objects proves depth is real.
- **Ugly truth beats pretty lies.** If a known artifact is in frame, either frame
  it out honestly or accept it. Never hide a defect by making a claim the shot
  does not support.
- **Assume no audio.** Plan every shot to communicate silently.
- **Assume ten seconds of attention.** Whatever must land, must land early.

## Do not

- Do not capture 3-second clips because the edit will use 3 seconds.
- Do not author camera motion before approving stills.
- Do not use an editor camera for a shot whose point is playability.
- Do not accept a take without checking the map it actually rendered.
- Do not build a new capture or render pipeline; use the adapters that exist and,
  if one genuinely cannot do the job, report the exact gap instead of inventing
  a parallel route.
- Do not carry over generative-video-model habits. There is no prompt, no seed,
  no wardrobe continuity, and no model to coax. There is a camera in a real
  world, and it goes where you put it.
