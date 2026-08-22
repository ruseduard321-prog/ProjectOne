/* ==========================================================================
   ProjectOne — the screens

   Every product surface, registered into `PO.views` and rendered by the core
   router. Three page templates and nothing else:

     cockpit    full-width working surfaces — Home, Studio, Library, spend
     workbench  a split view with an inspector — projects, runs, review
     focus      a centred column for consequential forms — plan, settings, auth

   A screen never computes a permission, a price or a legal transition. It
   renders the payload.
   ========================================================================== */
'use strict';

(function () {
  var U = PO.ui, C = PO.CAMPAIGN;
  var esc = U.esc, icon = U.icon, money = U.money, num = U.num, plural = U.plural, anno = U.anno;
  var frame = U.frame, badge = U.badge, notice = U.notice, empty = U.empty, faces = U.faces, avatar = U.avatar;

  /* ====================================================== creation modes

     One creation experience, six modes. A mode changes the placeholder, the
     suggested inputs, the output system and the recommended workflow. It does
     not change the interaction, and it is not a separate application.

     `art` on each output is what lets the outcome panel draw the actual thing
     rather than an icon of its file type.
     ==================================================================== */
  function d(id, name, stage, o) {
    o = o || {};
    return {
      id: id, name: name, stage: stage, n: o.n || 1, dep: o.dep || null, gate: !!o.gate,
      channel: o.ch || null,
      low: o.low || 0.01, high: o.high || 0.03, mins: o.mins || 2,
      ai: o.ai || '', editable: o.editable || 'Everything, as text.',
      truth: o.truth || 'proposed', from: o.from || 'Your brief',
      art: o.art || { scene: 'sear', aspect: '16x9' }
    };
  }
  /* `set` names a rotation in the campaign layer: which set-up, lockup and line
     each copy of a multi-copy deliverable gets. Without it, "twelve supporting
     posts" draws one descriptor twelve times and the shifted crop is the only
     thing telling them apart — which is how a campaign ends up looking like one
     photograph wearing forty crops. `scene` stays as the fallback for the
     single-copy case and for anything that asks for this art without a seat. */
  var A = {
    page: { doc: 'outline' }, script: { doc: 'script' }, email: { doc: 'email' },
    deck: { doc: 'carousel' }, sheet: { doc: 'sheet' },
    hero: { set: 'hero', scene: 'flip', aspect: '16x9', lockup: 'title' },
    key: { scene: 'flame', aspect: '16x9', lockup: 'title' },
    title: { set: 'episode', scene: 'sear', aspect: '16x9', lockup: 'episode' },
    thumb: { set: 'thumb', scene: 'flip', aspect: '16x9', lockup: 'title' },
    vert: { set: 'vert', scene: 'flip', aspect: '9x16', lockup: 'caption' },
    vert2: { scene: 'loaf', aspect: '9x16', lockup: 'caption' },
    still: { set: 'concept', scene: 'sear', aspect: '16x9' },
    caps: { scene: 'sear', aspect: '16x9', lockup: 'caption' },
    social: { set: 'social', scene: 'plate', aspect: '1x1', lockup: 'caption' },
    /* Paid placements. Each one is a different set-up carrying a different
       piece of platform furniture, because six placements that share a picture
       AND a layout are one ad with six file names. */
    adMeta:  { set: 'admeta',  scene: 'plate', aspect: '4x5',  lockup: 'ad', ad: 'meta',    headline: 'Six techniques. No fear.', cta: 'Watch the trailer' },
    adStory: { set: 'adstory', scene: 'flip',  aspect: '9x16', lockup: 'ad', ad: 'story',   headline: 'Cook it scared.', cta: 'Watch now' },
    adTok:   { set: 'adtok',   scene: 'hands', aspect: '9x16', lockup: 'ad', ad: 'tiktok',  headline: 'Hotter than you think.', cta: 'See the season' },
    adPre:   { set: 'adpre',   scene: 'flame', aspect: '16x9', lockup: 'ad', ad: 'preroll', headline: 'Season Two. 14 September.', cta: 'Subscribe' },
    adDisp:  { set: 'addisp',  scene: 'sear',  aspect: '8x1',  lockup: 'ad', ad: 'display', unit: [728, 90], headline: 'Cook it scared.', cta: 'Watch' },
    adCopy:  { set: 'adcopy',  scene: 'quote', aspect: '16x9', lockup: 'ad', ad: 'copy',
               headline: 'Six techniques. No fear.', cta: 'Watch the trailer',
               headlineB: 'Cook it scared.', ctaB: 'Watch now' }
  };

  /* One descriptor, built once, so a deliverable draws the same way on Home,
     on the plan, in a picker and in a recipe card. */
  function artOf(o, m) {
    var a = o.art || {};
    return { set: a.set, scene: a.scene || (m && m.scene) || 'sear', aspect: a.aspect || '16x9',
             doc: a.doc, lockup: a.lockup, headline: a.headline, cta: a.cta,
             headlineB: a.headlineB, ctaB: a.ctaB, ad: a.ad, unit: a.unit,
             name: o.name, docTitle: o.name, caption: C.tagline.toLowerCase(), slideN: '04',
             lockupTitle: C.brand, lockupEyebrow: C.season };
  }

  var MODES = [
    { id: 'plan', label: 'Plan', full: 'Plan a project', icon: 'book',
      blurb: 'ProjectOne reads the brief and returns a production plan before anything is generated.',
      placeholder: 'Describe the project — its goal, its audience, and what a good outcome looks like.',
      source: 'Your brief', scene: 'quote',
      guide: 'A good plan brief names the format, the audience and how many pieces it has to become.',
      workflow: { name: 'Project planning', truth: 'existing', note: 'Runs today, end to end.' },
      examples: ['A six-episode season teaching one intimidating technique per episode.',
                 'A weekly series built entirely from shelf-stable ingredients.'],
      outputs: [
        d('validated', 'Validated brief', 'Understand', { truth: 'existing', low: 0, high: 0, mins: 1, art: A.page,
          ai: 'Checks the brief has a goal, a format and an audience before any AI call is made.', editable: 'The brief itself.' }),
        d('outline', 'Production outline', 'Plan', { dep: 'validated', gate: true, truth: 'existing', low: 0.04, high: 0.14, mins: 3, art: A.page,
          ai: 'Drafts a structured plan: an outline, a running order and a hook per item.', editable: 'Every section, as text.' }),
        d('quality', 'Quality review', 'Plan', { dep: 'outline', truth: 'existing', low: 0, high: 0, mins: 1, art: A.page,
          ai: 'Scores the draft against completeness rules and flags gaps.', editable: 'The flags are advisory.' }),
        d('research', 'Research brief', 'Research', { truth: 'planned', low: 0.06, high: 0.18, mins: 4, art: A.page,
          ai: 'Gathers supporting material and sources for the topic.', editable: 'Sources and summary.' }),
        d('milestones', 'Milestone plan', 'Plan', { dep: 'outline', truth: 'planned', low: 0.03, high: 0.08, mins: 2, art: A.page,
          ai: 'Turns the outline into dated milestones against your launch.', editable: 'Dates and grouping.' })
      ] },

    { id: 'script', label: 'Script', full: 'Write a script', icon: 'file-text',
      blurb: 'From a topic to a shootable script, with the research it stands on.',
      placeholder: 'Describe the video or episode you want scripted — the topic, the angle, and roughly how long.',
      source: 'Your topic', scene: 'knife',
      guide: 'Say the claim you want to make and who has already heard it. The length can come later.',
      workflow: { name: 'Research and script agents', truth: 'planned', note: 'Designed, approved, not built.' },
      examples: ['Twelve minutes on why cast iron seasoning fails, for people who already own the pan.',
                 'A five-minute explainer on salting pasta water, myth-busting but not smug.'],
      outputs: [
        d('research', 'Research brief', 'Research', { truth: 'planned', low: 0.06, high: 0.18, mins: 4, art: A.page,
          ai: 'Collects claims, sources and counter-arguments.', editable: 'Sources and notes.' }),
        d('outline', 'Structure outline', 'Structure', { dep: 'research', truth: 'planned', low: 0.03, high: 0.09, mins: 2, art: A.page,
          ai: 'Shapes the argument into beats.', editable: 'Beat order and headings.', from: 'Research brief' }),
        d('script', 'Full script', 'Script', { dep: 'outline', gate: true, truth: 'planned', low: 0.18, high: 0.42, mins: 6, art: A.script,
          ai: 'Writes the spoken script against your tone.', editable: 'Every line, as text.', from: 'Structure outline' }),
        d('hooks', 'Hook variants', 'Script', { dep: 'script', n: 5, truth: 'planned', low: 0.04, high: 0.11, mins: 2, art: A.script,
          ai: 'Writes five alternative openings to test.', editable: 'Each variant.', from: 'Full script' }),
        d('shotlist', 'Shot list', 'Production', { dep: 'script', truth: 'proposed', low: 0.05, high: 0.12, mins: 3, art: A.page,
          ai: 'Breaks the script into shots and b-roll needs.', editable: 'Every row.', from: 'Full script' })
      ] },

    { id: 'visual', label: 'Visual', full: 'Create a visual', icon: 'image',
      blurb: 'Concept directions first, then the artwork that follows from the one you pick.',
      placeholder: 'Describe the visual — the subject, the mood, the format, and where it will be seen.',
      source: 'Your description', scene: 'spice',
      guide: 'Describe the light and the subject, not the style. Where it will be seen matters more than the adjectives.',
      workflow: { name: 'Image generation', truth: 'planned', note: 'Designed, approved, not built.' },
      examples: ['Key art for a season of cast iron episodes: warm, matte, no stock-photo gloss.',
                 'A title card system for six episodes, legible at thumbnail size.'],
      outputs: [
        d('directions', 'Concept directions', 'Concepts', { n: 3, truth: 'planned', low: 0.09, high: 0.24, mins: 3, art: A.still,
          ai: 'Proposes three distinct visual directions with reasoning.', editable: 'Direction notes and prompts.' }),
        d('keyvisual', 'Key visual', 'Design', { dep: 'directions', gate: true, truth: 'planned', low: 0.15, high: 0.36, mins: 4, art: A.key,
          ai: 'Produces the primary artwork from the chosen direction.', editable: 'Regenerate or refine by prompt.', from: 'Concept directions' }),
        d('thumbs', 'Title card set', 'Design', { dep: 'keyvisual', n: 6, truth: 'planned', low: 0.12, high: 0.27, mins: 3, art: A.title,
          ai: 'Adapts the key visual into one card per episode.', editable: 'Crop, text and variant choice.', from: 'Key visual' }),
        d('stylenotes', 'Style notes', 'Design', { dep: 'directions', truth: 'proposed', low: 0.03, high: 0.06, mins: 2, art: A.page,
          ai: 'Writes down the rules so later work stays consistent.', editable: 'All of it.', from: 'Concept directions' })
      ] },

    { id: 'video', label: 'Video', full: 'Create a video', icon: 'film',
      blurb: 'One idea becomes a script, a master cut, and everything that ships alongside it.',
      placeholder: 'Describe the video — the story you want to tell, its length, and where it will live.',
      source: 'Your idea', scene: 'flip',
      guide: 'Say who it is for, what it should make them do, and how long it has.',
      workflow: { name: 'Video production pipeline', truth: 'planned', note: 'Designed, approved, not built.' },
      examples: ['A trailer for a six-episode season, warm and practical, ninety seconds.',
                 'A three-minute pantry recipe with no on-camera presenter.'],
      outputs: [
        d('research', 'Research brief', 'Research', { truth: 'planned', low: 0.06, high: 0.18, mins: 4, art: A.page,
          ai: 'Collects the claims and sources the video rests on.', editable: 'Sources and notes.' }),
        d('script', 'Script', 'Script', { dep: 'research', gate: true, truth: 'planned', low: 0.18, high: 0.42, mins: 6, art: A.script,
          ai: 'Writes the script in your voice.', editable: 'Every line, as text.', from: 'Research brief' }),
        d('shotlist', 'Shot list', 'Production', { dep: 'script', truth: 'proposed', low: 0.05, high: 0.12, mins: 3, art: A.page,
          ai: 'Breaks the script into shots.', editable: 'Every row.', from: 'Script' }),
        d('master', 'Master cut', 'Production', { dep: 'script', gate: true, truth: 'planned', low: 0.54, high: 1.38, mins: 22, art: A.hero,
          ai: 'Assembles the master from the script and your media.', editable: 'Scenes and timing, by text and direct edit.', from: 'Script' }),
        d('captions', 'Captions', 'Production', { dep: 'master', truth: 'proposed', low: 0.03, high: 0.09, mins: 3, art: A.caps,
          ai: 'Transcribes and times the captions.', editable: 'Text and timing.', from: 'Master cut' }),
        d('thumbs', 'Thumbnail concepts', 'Design', { dep: 'script', n: 4, truth: 'planned', low: 0.12, high: 0.27, mins: 3, art: A.thumb,
          ai: 'Proposes four thumbnail concepts drawn from the script.', editable: 'Prompt, crop and text.', from: 'Script' })
      ] },

    { id: 'repurpose', label: 'Repurpose', full: 'Repurpose existing work', icon: 'layers',
      blurb: 'One finished piece becomes the whole set of things it should already have been.',
      placeholder: 'Point at the source and describe what you want it to become.',
      source: 'Your source video', scene: 'hands',
      guide: 'Point at the source, then say which moments matter and what they should become.',
      workflow: { name: 'Repurposing pipeline', truth: 'proposed', note: 'A proposal. It needs your approval before it is scheduled.' },
      examples: ['Turn the season trailer into vertical teasers, a carousel and a newsletter, in the same voice.',
                 'Pull the six strongest moments out of this tutorial for short-form.'],
      outputs: [
        d('transcript', 'Transcript', 'Understand', { truth: 'proposed', low: 0.03, high: 0.09, mins: 3, art: A.script,
          ai: 'Transcribes the source with speaker and timing.', editable: 'Text and timings.', from: 'Your source video' }),
        d('highlights', 'Highlight map', 'Understand', { dep: 'transcript', truth: 'proposed', low: 0.06, high: 0.15, mins: 3, art: A.page,
          ai: 'Finds the moments that stand alone and says why.', editable: 'Add, remove and retime any moment.', from: 'Transcript' }),
        d('clips', 'Vertical teasers', 'Variants', { dep: 'highlights', n: 6, gate: true, truth: 'proposed', low: 0.27, high: 0.66, mins: 12, art: A.vert,
          ai: 'Cuts six vertical teasers from the marked moments.', editable: 'In and out points, captions, crop.', from: 'Highlight map' }),
        d('clipcaps', 'Burned-in captions', 'Variants', { dep: 'clips', truth: 'proposed', low: 0.03, high: 0.09, mins: 3, art: A.vert2,
          ai: 'Burns timed captions into each teaser.', editable: 'Text, style and timing.', from: 'Vertical teasers' }),
        d('thumbs', 'Thumbnail concepts', 'Design', { dep: 'highlights', n: 3, truth: 'planned', low: 0.09, high: 0.21, mins: 3, art: A.thumb,
          ai: 'Proposes thumbnails from the strongest frames.', editable: 'Frame choice and text.', from: 'Highlight map' }),
        d('carousel', 'Carousel draft', 'Drafts', { dep: 'highlights', truth: 'proposed', low: 0.06, high: 0.12, mins: 3, art: A.deck,
          ai: 'Writes a slide-by-slide carousel from the key points.', editable: 'Every slide.', from: 'Highlight map' }),
        d('newsletter', 'Newsletter draft', 'Drafts', { dep: 'transcript', truth: 'proposed', low: 0.06, high: 0.15, mins: 3, art: A.email,
          ai: 'Writes a newsletter version in your voice.', editable: 'Every paragraph.', from: 'Transcript' })
      ] },

    { id: 'campaign', label: 'Campaign', full: 'Build a campaign', icon: 'zap',
      blurb: 'A launch as one connected system rather than a list of unrelated posts.',
      placeholder: 'Describe the campaign — what you are launching, to whom, and over what period.',
      source: 'Your campaign brief', scene: 'flame',
      guide: 'Name what you are launching, who already knows about it, and the date it has to be ready.',
      workflow: { name: 'Multi-agent campaign workflow', truth: 'proposed', note: 'A proposal. It needs your approval before it is scheduled.' },
      examples: ['A three-week launch for season two, to the existing audience.',
                 'Turn the best-performing pantry post into a four-week series.'],
      outputs: [
        d('audience', 'Audience brief', 'Research', { truth: 'planned', low: 0.06, high: 0.15, mins: 4, art: A.page,
          ai: 'Describes who this is for and what they already believe.', editable: 'All of it.' }),
        d('narrative', 'Campaign narrative', 'Strategy', { dep: 'audience', gate: true, truth: 'proposed', low: 0.09, high: 0.21, mins: 4, art: A.page,
          ai: 'Sets the through-line every asset ladders up to.', editable: 'Every section.', from: 'Audience brief' }),
        d('channelplan', 'Channel plan', 'Strategy', { dep: 'narrative', truth: 'proposed', low: 0.06, high: 0.15, mins: 3, art: A.page,
          ai: 'Maps the narrative to formats and a sequence.', editable: 'Sequence and formats.', from: 'Campaign narrative' }),
        d('hero', 'Hero assets', 'Production', { dep: 'narrative', n: 3, gate: true, truth: 'planned', low: 0.36, high: 0.84, mins: 14, art: A.hero,
          ai: 'Produces the three anchor pieces.', editable: 'Script, visuals and timing.', from: 'Campaign narrative' }),
        d('supporting', 'Supporting posts', 'Variants', { dep: 'hero', n: 12, truth: 'proposed', low: 0.18, high: 0.45, mins: 8, art: A.social,
          ai: 'Derives twelve supporting posts from the hero assets.', editable: 'Every post.', from: 'Hero assets' }),
        d('checklist', 'Launch checklist', 'Drafts', { dep: 'channelplan', truth: 'proposed', low: 0.03, high: 0.06, mins: 2, art: A.page,
          ai: 'Turns the plan into a dated checklist against your launch.', editable: 'Every item.', from: 'Channel plan' }),

        /* The advertising the creator is making. `ch` ties each one to a
           channel in the brief essentials, so unticking a channel takes its
           placements — and their cost — off the plan. */
        d('ad_meta', 'Meta feed ad', 'Paid media', { dep: 'hero', n: 2, ch: 'meta', truth: 'proposed', low: 0.06, high: 0.15, mins: 3, art: A.adMeta,
          ai: 'Cuts the hero to feed sizes and writes the paid headline and call to action.', editable: 'Crop, headline, call to action.', from: 'Hero assets' }),
        d('ad_story', 'Story and Reels ad', 'Paid media', { dep: 'hero', n: 2, ch: 'instagram', truth: 'proposed', low: 0.09, high: 0.21, mins: 4, art: A.adStory,
          ai: 'Builds the vertical paid cut with safe areas and a sound-off opening.', editable: 'In and out points, headline, call to action.', from: 'Hero assets' }),
        d('ad_tiktok', 'TikTok ad variation', 'Paid media', { dep: 'hero', n: 2, ch: 'tiktok', truth: 'proposed', low: 0.09, high: 0.21, mins: 4, art: A.adTok,
          ai: 'Rebuilds the same story for in-feed, hook first.', editable: 'Hook, pacing, captions.', from: 'Hero assets' }),
        d('ad_preroll', 'YouTube pre-roll', 'Paid media', { dep: 'hero', n: 2, ch: 'youtube', truth: 'proposed', low: 0.12, high: 0.28, mins: 5, art: A.adPre,
          ai: 'Cuts six and fifteen second pre-rolls that work before the skip.', editable: 'Length, opening frame, end card.', from: 'Hero assets' }),
        d('ad_display', 'Display banner set', 'Paid media', { dep: 'hero', n: 5, ch: 'display', truth: 'proposed', low: 0.05, high: 0.12, mins: 3, art: A.adDisp,
          ai: 'Crops one plate to the five standard sizes rather than squeezing it.', editable: 'Crop per size, headline, call to action.', from: 'Hero assets' }),
        d('ad_copy', 'Paid copy and CTA variants', 'Paid media', { dep: 'narrative', n: 8, ch: '*', truth: 'proposed', low: 0.04, high: 0.09, mins: 2, art: A.adCopy,
          ai: 'Writes headline and call-to-action variants against the narrative, one marked as the control.', editable: 'Every line.', from: 'Campaign narrative' })
      ] }
  ];
  var modeById = function (id) { return MODES.filter(function (m) { return m.id === id; })[0] || MODES[0]; };
  var PRIMARY_BY_MODE = { plan: 'outline', script: 'script', visual: 'keyvisual', video: 'master', repurpose: 'clips', campaign: 'hero' };

  var DESTINATIONS = [
    { id: 'youtube', label: 'Long-form video', note: 'A full episode, landscape.' },
    { id: 'shorts', label: 'Short-form video', note: 'Vertical, under a minute.' },
    { id: 'social', label: 'Social posts', note: 'Square and portrait stills.' },
    { id: 'newsletter', label: 'Newsletter', note: 'Written, for your list.' },
    { id: 'internal', label: 'Keep it internal', note: 'Nothing leaves the workspace.' }
  ];
  var destById = function (id) { return DESTINATIONS.filter(function (x) { return x.id === id; })[0] || DESTINATIONS[0]; };

  var RECIPES = [
    { id: 'r_season', name: 'Launch a season', mode: 'video', dest: 'youtube', ref: 'as_script',
      note: 'Trailer, teasers, title cards and the announcement, from one brief.',
      prompt: 'A ninety-second trailer for a six-episode season teaching one intimidating technique per episode. Warm, practical, no mysticism.' },
    { id: 'r_repurpose', name: 'One cut, every format', mode: 'repurpose', dest: 'shorts', ref: 'as_trailer',
      note: 'A finished master becomes teasers, a carousel and a newsletter.',
      prompt: 'Turn the season trailer into six vertical teasers, a carousel and a newsletter, keeping the same voice.' },
    { id: 'r_explainer', name: 'Answer the comments', mode: 'script', dest: 'youtube', ref: null,
      note: 'The twelve questions you keep answering, as one explainer.',
      prompt: 'Twelve minutes answering the cast-iron questions that fill the comments on every other video. Patient, myth-busting, evidence first.' },
    { id: 'r_key', name: 'Build the look', mode: 'visual', dest: 'social', ref: 'as_keyart',
      note: 'Key art first, then every card that has to match it.',
      prompt: 'Key art for season two: ember and ivory, real kitchen light, legible at thumbnail size.' },
    { id: 'r_launch', name: 'Three-week launch', mode: 'campaign', dest: 'social', ref: null,
      note: 'A narrative, a channel plan, three anchors and twelve supports.',
      prompt: 'A three-week launch for season two to the existing audience, ending on the premiere.' },
    { id: 'r_scope', name: 'Scope it before you spend', mode: 'plan', dest: 'internal', ref: null,
      note: 'The cheapest possible first step: a plan, priced, before anything is made.',
      prompt: 'A six-episode season teaching one intimidating technique per episode, for cooks who own the pans but not the nerve.' }
  ];

  var REF_LIBRARY = [
    { id: 'as_trailer', name: 'Season Two — Trailer (v4)', meta: '1:52 · 412 MB', kind: 'film' },
    { id: 'as_script', name: 'Trailer script (v6)', meta: '640 words · 18 KB', kind: 'file-text' },
    { id: 'as_keyart', name: 'Season key art (v2)', meta: '2400 × 1350 · 3.1 MB', kind: 'image' },
    { id: 'as_selects', name: 'Season two — selects', meta: '10 frames · 2.8 MB', kind: 'grid' }
  ];

  /* ================================================== brief essentials

     Four things every brief needs and most briefs leave out. They are not a
     form: each has a sensible value the moment a mode is chosen, each is one
     press to change, and none of them is a commitment — the plan restates
     every one of them before anything runs, and the plan can still be
     cancelled. What differs per mode is which four, because "length" means
     nothing to a key visual and "set size" means nothing to a trailer.
     ==================================================================== */
  var CHANNELS = [
    { id: 'youtube', label: 'YouTube', paid: 'Pre-roll' },
    { id: 'shorts', label: 'Shorts', paid: null },
    { id: 'instagram', label: 'Instagram', paid: 'Story and Reels' },
    { id: 'tiktok', label: 'TikTok', paid: 'In-feed' },
    { id: 'meta', label: 'Meta feed', paid: 'Feed' },
    { id: 'display', label: 'Display', paid: 'Banner set' },
    { id: 'newsletter', label: 'Newsletter', paid: null }
  ];
  var chanById = function (id) { return CHANNELS.filter(function (x) { return x.id === id; })[0]; };

  var AUD = ['Home cooks who own the pans', 'Complete beginners', 'The existing subscribers',
             'Lapsed viewers', 'Trade and press'];
  var TONE = ['Warm, practical, evidence first', 'Calm and instructional',
              'Fast and playful', 'Editorial and restrained'];

  function f(key, label, opts, def) { return { key: key, label: label, opts: opts, def: def || opts[0] }; }
  function ch(label, opts, def) { return { key: 'channels', label: label, multi: true, opts: opts, def: def }; }

  var ESS = {
    plan: [f('audience', 'Audience', AUD), f('tone', 'Tone', TONE),
           f('scope', 'Scope', ['Six episodes', 'Twelve episodes', 'One pilot', 'A single video']),
           f('launch', 'Launch', ['14 September', 'Late October', 'No date yet'])],
    script: [f('audience', 'Audience', AUD), f('tone', 'Tone', TONE),
             f('length', 'Length', ['5 minutes', '12 minutes', '20 minutes'], '12 minutes'),
             f('evidence', 'Evidence', ['Cited, with sources', 'Experience only', 'Light — no citations'])],
    visual: [f('audience', 'Audience', AUD), f('tone', 'Tone', TONE),
             f('format', 'Format', ['2400 × 1350', '1080 × 1350', '1080 × 1920']),
             f('setsize', 'Set size', ['Key visual + 6 cards', 'One key visual', 'The full system'])],
    video: [f('audience', 'Audience', AUD), f('tone', 'Tone', TONE),
            f('length', 'Length', ['60 seconds', '90 seconds', '3 minutes', '12 minutes'], '90 seconds'),
            ch('Channels', ['youtube', 'shorts', 'instagram', 'tiktok'], ['youtube', 'shorts'])],
    repurpose: [f('audience', 'Audience', AUD), f('tone', 'Tone', TONE),
                f('cliplen', 'Clips', ['Under 30 seconds', '30–60 seconds', 'Up to 90 seconds'], '30–60 seconds'),
                ch('Channels', ['shorts', 'instagram', 'tiktok', 'newsletter'], ['shorts', 'instagram', 'tiktok'])],
    campaign: [f('audience', 'Audience', AUD), f('tone', 'Tone', TONE),
               f('runtime', 'Run time', ['Two weeks', 'Three weeks', 'Six weeks'], 'Three weeks'),
               /* Every placement on by default. A launch plan that quietly
                  omits two channels shows a cheaper number than the campaign
                  it describes; showing the whole pack and letting it be cut
                  is the honest direction to be wrong in. */
               ch('Channels', ['meta', 'instagram', 'tiktok', 'youtube', 'display'],
                  ['meta', 'instagram', 'tiktok', 'youtube', 'display'])]
  };
  var essFields = function (modeId) { return ESS[modeId] || ESS.video; };
  function essField(modeId, key) {
    return essFields(modeId).filter(function (x) { return x.key === key; })[0];
  }
  /** The current value, defaulting to the mode's own, never undefined. */
  function essValue(modeId, key, store) {
    var fd = essField(modeId, key);
    if (!fd) return null;
    var bag = (store || c.ess)[modeId];
    var v = bag ? bag[key] : undefined;
    if (v === undefined) return fd.multi ? fd.def.slice() : fd.def;
    return fd.multi ? v.slice() : v;
  }
  function essSet(modeId, key, value) {
    if (!c.ess[modeId]) c.ess[modeId] = {};
    c.ess[modeId][key] = value;
  }
  /** What an essential reads as in one line. */
  function essLabel(modeId, key, store) {
    var fd = essField(modeId, key), v = essValue(modeId, key, store);
    if (!fd) return '';
    if (!fd.multi) return v;
    if (!v.length) return 'None — organic only';
    var names = v.map(function (id) { var x = chanById(id); return x ? x.label : id; });
    return names.length > 2 ? names.slice(0, 2).join(' · ') + ' +' + (names.length - 2) : names.join(' · ');
  }

  /* -------------------------------------------------------- composer state */
  var c = {
    mode: 'video', prompt: '', ref: null, project: null, dest: 'youtube',
    removed: {}, selected: null, plan: null, ess: {}
  };
  PO.composer = c;

  /* One filter, used by Home and by the plan, so the two can never disagree
     about what is on the plan. A placement whose channel is not ticked is not
     "removed" — it was never asked for, and adding the channel brings it and
     its cost back. */
  function outputsFor(modeId, removed, store) {
    var m = modeById(modeId);
    var chans = essField(modeId, 'channels') ? essValue(modeId, 'channels', store) : null;
    return m.outputs.filter(function (o) {
      if (removed[o.id]) return false;
      if (!o.channel) return true;
      if (!chans) return false;
      return o.channel === '*' ? chans.length > 0 : chans.indexOf(o.channel) !== -1;
    });
  }
  function outputs(modeId) { return outputsFor(modeId, c.removed, c.ess); }
  function totals(list) {
    var low = 0, high = 0, mins = 0, count = 0, gates = 0;
    list.forEach(function (o) {
      low += o.low * o.n; high += o.high * o.n; mins += o.mins * o.n;
      count += o.n; if (o.gate) gates++;
    });
    return { low: low, high: high, mins: mins, count: count, gates: gates };
  }
  function minutesLabel(m) {
    if (m < 60) return '~' + Math.round(m) + ' min';
    var h = Math.floor(m / 60), r = Math.round(m % 60);
    return '~' + h + 'h' + (r ? ' ' + r + 'm' : '');
  }
  function sourceName() {
    if (c.ref) { var r = REF_LIBRARY.filter(function (x) { return x.id === c.ref; })[0]; return r ? r.name : 'Your reference'; }
    return modeById(c.mode).source;
  }

  /* ========================================================== HOME — cockpit
     The one route that leaves the centred reading column. A workspace, not a
     document: the brief on the left, what it becomes on the right, and the
     three things worth interrupting for underneath.
     ====================================================================== */
  PO.views.dashboard = function () {
    var gov = U.governedNotices('start');
    return '<div class="cockpit">' +
      (gov ? '<div class="cockpit__gov">' + gov + '</div>' : '') +
      '<header class="cockpit__head">' +
        '<p class="cockpit__thesis">One idea. <em>The whole production.</em></p>' +
        '<h1 class="cockpit__ask t-display-hero">What will we create today?</h1>' +
        '<div class="cockpit__meta">' + U.ambientCost() + '</div>' +
      '</header>' +
      '<div class="cockpit__work">' + composer() + outcome() + '</div>' +
      '<div class="cockpit__zones">' + zoneRecipes() + zoneContinue() + zoneAttention() + '</div>' +
      '</div>';
  };

  function composer() {
    var m = modeById(c.mode), gate = U.startGate(), b = U.budgetView();
    var ref = c.ref ? REF_LIBRARY.filter(function (x) { return x.id === c.ref; })[0] : null;
    var proj = c.project ? U.projectById(c.project) : null;
    var t = totals(outputs(c.mode));

    return '<section class="composer" aria-labelledby="composer-h"' + anno('proposed', 'one composer, six modes') + '>' +
      '<h2 class="u-sr-only" id="composer-h">Describe what you want to make</h2>' +

      '<div class="modes" role="group" aria-label="Creation mode">' +
        MODES.map(function (x) {
          var on = x.id === c.mode;
          return '<button type="button" class="mode' + (on ? ' is-on' : '') + '" data-act="mode" data-arg="' + x.id + '"' +
            ' aria-pressed="' + on + '"><span>' + esc(x.label) + '</span></button>';
        }).join('') +
      '</div>' +

      '<p class="composer__blurb t-sm t-muted">' + esc(m.blurb) + '</p>' +

      /* One well: the thing you write in, and — while it is empty — the two
         sentences that show what "written" looks like. Keeping the guidance
         inside the writing area rather than under it is what stops the
         composer changing height the moment you start typing. */
      '<div class="composer__write">' +
        '<div class="composer__field">' +
          '<label class="u-sr-only" for="composer-input">' + esc(m.full) + '</label>' +
          '<textarea id="composer-input" class="composer__input" rows="3" placeholder="' + esc(m.placeholder) + '">' + esc(c.prompt) + '</textarea>' +
        '</div>' +
        (c.prompt ? '' :
          '<div class="guide">' +
            '<p class="guide__lead t-xs t-muted">' + esc(m.guide) + '</p>' +
            '<div class="tryrow" role="group" aria-label="Example briefs">' +
              m.examples.map(function (x, i) {
                return '<button type="button" class="try" data-act="try" data-arg="' + i + '" title="' + esc(x) + '">' +
                  icon('arrow-right', 'icon icon--sm try__go') + '<span class="try__t">' + esc(x) + '</span></button>';
              }).join('') + '</div></div>') +
      '</div>' +

      essentials(m) +

      '<div class="composer__tools">' +
        (ref
          ? '<span class="chip chip--on">' + icon(ref.kind, 'icon icon--sm') + '<span class="chip__text">' + esc(ref.name) + '</span>' +
            '<button type="button" class="chip__x" data-act="ref-clear" aria-label="Remove ' + esc(ref.name) + '">' + icon('x', 'icon icon--sm') + '</button></span>'
          : '<button type="button" class="chip" data-act="ref-open">' + icon('paperclip', 'icon icon--sm') + '<span class="chip__text">Add a reference</span></button>') +
        (proj
          ? '<span class="chip chip--on">' + icon('layers', 'icon icon--sm') + '<span class="chip__text">' + esc(proj.name) + '</span>' +
            '<button type="button" class="chip__x" data-act="ctx-clear" aria-label="Clear project context">' + icon('x', 'icon icon--sm') + '</button></span>'
          : '<button type="button" class="chip" data-act="ctx-open">' + icon('layers', 'icon icon--sm') + '<span class="chip__text">Use a project</span></button>') +
        '<button type="button" class="chip chip--dest" data-act="dest-open" id="dest-trigger" aria-haspopup="dialog" aria-expanded="false" aria-controls="dest-popover">' +
          icon('send', 'icon icon--sm') + '<span class="chip__text">' + esc(destById(c.dest).label) + '</span>' + icon('chevron-down', 'icon icon--sm') +
        '</button>' +
      '</div>' +

      '<div class="composer__foot">' +
        '<p class="composer__est t-xs t-muted">' +
          (gate.ok
            ? 'Estimated ' + money(t.low) + '–' + money(t.high) + ' · ' + money(b.remaining) + ' left this month'
            : gate.why === 'permission' ? 'Your role cannot start production'
            : gate.why === 'breaker' ? 'AI work is paused for this workspace'
            : gate.why === 'budget' ? 'The monthly ceiling has been reached'
            : gate.why === 'offline' ? 'Services are unreachable'
            : 'Rate limited — this clears within a minute') +
        '</p>' +
        '<button type="button" class="btn btn--primary btn--lg" id="composer-cta" data-act="prepare"' +
          (c.prompt.trim() && gate.ok ? '' : ' disabled') + '>' +
          'Prepare the plan' + icon('arrow-right', 'icon') +
        '</button>' +
      '</div>' +
    '</section>';
  }

  /* The four values, always present, never a wall of inputs. Empty they are
     the mode's own starting point; filled they are what the brief was read
     as. Either way the note above them says so, and every one is one press
     from being something else. */
  function essentials(m) {
    var filled = !!c.prompt.trim();
    return '<section class="essentials" aria-labelledby="ess-h">' +
      '<div class="essentials__head">' +
        '<h3 class="eyebrow" id="ess-h">Brief essentials</h3>' +
        '<p class="essentials__note t-xs t-muted">' +
          (filled ? 'Read from your brief — change any of them'
                  : 'Where ' + esc(m.label) + ' starts — change any of them') + '</p>' +
      '</div>' +
      '<div class="essentials__grid">' +
        essFields(m.id).map(function (fd) {
          return '<button type="button" class="ess" id="ess-' + fd.key + '" data-act="ess" data-arg="' + fd.key + '"' +
            ' aria-haspopup="dialog" aria-expanded="false" aria-controls="ess-popover">' +
            '<span class="ess__k">' + esc(fd.label) + '</span>' +
            '<span class="ess__v"><span class="ess__t">' + esc(essLabel(m.id, fd.key)) + '</span>' +
              icon('chevron-down', 'icon icon--sm ess__go') + '</span>' +
          '</button>';
        }).join('') +
      '</div>' +
    '</section>';
  }

  /* ---------------------------------------------------------- the outcome
     Shown once, beside the brief, never repeated further down the page. It
     updates on every change of mode, recipe, reference, project or
     destination — the point being that you can see what you are buying
     before you buy it. */
  function outcome() {
    var m = modeById(c.mode);
    var list = outputs(c.mode);
    var t = totals(list);
    var body = c.selected ? outcomeDetail(c.selected) : outcomeChain(m, list);
    return '<section class="outcome" aria-labelledby="outcome-head"' + anno('proposed', 'priced before it is made') + '>' +
      '<div class="outcome__top">' +
        '<h2 class="eyebrow" id="outcome-head">What this becomes</h2>' +
        (c.selected ? '' : '<span class="outcome__count t-xs t-muted">' + plural(t.count, 'deliverable') + '</span>') +
      '</div>' +
      '<div class="outcome__body">' + body + '</div>' +
      '<dl class="outcome__foot">' +
        '<div><dt>Estimate</dt><dd class="t-num">' + money(t.low) + '–' + money(t.high) + '</dd></div>' +
        '<div><dt>Ready in</dt><dd class="t-num">' + minutesLabel(t.mins) + '</dd></div>' +
        '<div><dt>Approvals</dt><dd class="t-num">' + t.gates + '</dd></div>' +
      '</dl>' +
    '</section>';
  }

  function outcomeChain(m, list) {
    var primaryId = PRIMARY_BY_MODE[m.id];
    var master = list.filter(function (o) { return o.id === primaryId; })[0] || list[list.length - 1];
    var before = list.filter(function (o) { return o !== master && !o.dep_of_master; });
    var pre = list.slice(0, list.indexOf(master));
    var derived = list.filter(function (o) { return o !== master && pre.indexOf(o) === -1; });

    return '<div class="vpath" role="list" aria-label="Everything that leads to the master">' +
        '<span class="vstep vstep--source" role="listitem">' +
          '<span class="vstep__dot" aria-hidden="true"></span>' +
          '<span class="vstep__name"><span class="vstep__kind">Source</span><span class="vstep__label">' + esc(sourceName()) + '</span></span>' +
        '</span>' +
        pre.map(function (o) {
          return '<button type="button" class="vstep vstep--btn" role="listitem" data-act="out" data-arg="' + o.id + '">' +
            '<span class="vstep__dot' + (o.gate ? ' is-gate' : '') + '" aria-hidden="true"></span>' +
            '<span class="vstep__name"><span class="vstep__kind">' + esc(o.stage) + '</span>' +
            '<span class="vstep__label">' + esc(o.name) + (o.gate ? ' ' + icon('shield-check', 'icon icon--sm') : '') + '</span></span>' +
          '</button>';
        }).join('') +
      '</div>' +

      '<button type="button" class="vmaster" data-act="out" data-arg="' + master.id + '">' +
        frame(artOf(master, m), { aspect: master.art.aspect || '16x9', gate: master.gate, n: master.n, cls: 'frame--master' }) +
        '<span class="vmaster__meta"><span class="vmaster__kind eyebrow">Master output</span>' +
        '<span class="vmaster__name">' + esc(master.name) + (master.n > 1 ? ' ×' + master.n : '') + '</span></span>' +
      '</button>' +

      (derived.length ? contactSheet(derived, m) : '');
  }

  /* Every derivative, at the count it actually has. One tile per piece, not
     one tile per line of the plan — twelve supporting posts should look like
     twelve, because that volume is the thing being bought. Beyond the cap the
     sheet says how many more rather than pretending the set is smaller. */
  /* Ten cells, two rows of five, and the last one is the count when there
     are more. Nine tiles plus a count beats ten tiles plus a third row of
     one. */
  var SHEET_CELLS = 10;
  function contactSheet(derived, m) {
    var total = 0;
    derived.forEach(function (o) { total += o.n; });
    var cap = total > SHEET_CELLS ? SHEET_CELLS - 1 : SHEET_CELLS;
    /* Round-robin, not run-length. Filling the cells by taking every copy of
       the first deliverable before moving on meant a campaign with twelve
       supporting posts showed twelve supporting posts and none of the six paid
       placements it also makes. A contact sheet exists to show the RANGE of a
       set, so it takes one of everything before it takes a second of anything.

       The seat is the copy index WITHIN its deliverable, not a running total,
       so copy one of the banner set is the leaderboard rather than whichever
       size the counter happened to land on. */
    var tiles = [], round = 0;
    while (tiles.length < cap && round < total) {
      var placed = 0;
      for (var d = 0; d < derived.length && tiles.length < cap; d++) {
        if (derived[d].n > round) { tiles.push({ o: derived[d], i: round + 1, seat: round }); placed++; }
      }
      if (!placed) break;
      round++;
    }
    var more = total - tiles.length;
    return '<div class="vderiv">' +
      '<div class="vderiv__head">' +
        '<h3 class="eyebrow" id="vd-h">Derived from it</h3>' +
        '<span class="t-xs t-muted">' + plural(total, 'piece') + '</span>' +
      '</div>' +
      '<div class="vfilm" role="list" aria-labelledby="vd-h">' +
        tiles.map(function (t) {
          var o = t.o, many = o.n > 1;
          var label = o.name + (many ? ' — ' + t.i + ' of ' + o.n : '');
          return '<button type="button" class="vfilm__btn" role="listitem" data-act="out" data-arg="' + o.id + '"' +
            ' title="' + esc(label) + '" aria-label="' + esc(label) + '">' +
            frame(artOf(o, m), { aspect: '16x9', detail: 'thumb',
                                 seat: t.seat, gate: o.gate && t.i === 1 }) +
          '</button>';
        }).join('') +
        (more > 0 ? '<span class="vfilm__more" aria-hidden="true">+' + more + '</span>' : '') +
      '</div>' +
    '</div>';
  }

  function outcomeDetail(id) {
    var m = modeById(c.mode);
    var o = m.outputs.filter(function (x) { return x.id === id; })[0];
    if (!o) return outcomeChain(m, outputs(c.mode));
    return '<div class="odetail">' +
      '<button type="button" class="backlink" id="outcome-back" data-act="out-back">' + icon('arrow-left', 'icon icon--sm') + 'All ' + plural(totals(outputs(c.mode)).count, 'deliverable') + '</button>' +
      frame(artOf(o, m), { aspect: o.art.aspect || '16x9', cls: 'frame--detail' }) +
      '<h3 class="odetail__name t-h3">' + esc(o.name) + (o.n > 1 ? ' ×' + o.n : '') + '</h3>' +
      '<dl class="odetail__facts">' +
        '<div><dt>Comes from</dt><dd>' + esc(o.from) + '</dd></div>' +
        '<div><dt>What AI does</dt><dd>' + esc(o.ai) + '</dd></div>' +
        '<div><dt>You can change</dt><dd>' + esc(o.editable) + '</dd></div>' +
        '<div><dt>Approval</dt><dd>' + (o.gate ? 'Needs your approval before it runs' : 'No approval needed') + '</dd></div>' +
        '<div><dt>In the estimate</dt><dd class="t-num">' + (o.low === 0 && o.high === 0 ? 'No AI cost' : money(o.low * o.n) + '–' + money(o.high * o.n)) + '</dd></div>' +
      '</dl>' +
    '</div>';
  }

  /* ------------------------------------------------------------ the zones */
  function zoneRecipes() {
    var recs = RECIPES.filter(function (r) { return r.mode === c.mode; })
      .concat(RECIPES.filter(function (r) { return r.mode !== c.mode; })).slice(0, 3);
    return '<section class="zone zone--recipes" aria-labelledby="z-rec"' + anno('proposed') + '>' +
      '<div class="zone__head"><h2 class="eyebrow" id="z-rec">Start from a recipe</h2>' +
      '<a class="zone__link" href="#/library/recipes">All ' + RECIPES.length + icon('chevron-right', 'icon icon--sm') + '</a></div>' +
      '<div class="zone__body">' + recs.map(function (r) {
        return '<button type="button" class="zrow" data-act="recipe" data-arg="' + r.id + '">' +
          '<span class="zrow__title">' + esc(r.name) + '</span>' +
          '<span class="zrow__meta t-xs t-muted">' + esc(r.note) + '</span></button>';
      }).join('') + '</div></section>';
  }

  function zoneContinue() {
    var live = U.projects().filter(function (p) { return p.status !== 'archive'; }).slice(0, 2);
    if (!live.length) {
      return '<section class="zone zone--continue" aria-labelledby="z-cont"' + anno('existing', 'projects and runs') + '>' +
        '<div class="zone__head"><h2 class="eyebrow" id="z-cont">Continue</h2></div>' +
        '<div class="zone__body"><p class="zone__none t-sm t-muted">Nothing in production yet. The first brief you write starts one.</p></div></section>';
    }
    return '<section class="zone zone--continue" aria-labelledby="z-cont"' + anno('existing', 'projects and runs') + '>' +
      '<div class="zone__head"><h2 class="eyebrow" id="z-cont">Continue</h2>' +
      '<a class="zone__link" href="#/projects">All projects' + icon('chevron-right', 'icon icon--sm') + '</a></div>' +
      '<div class="zone__body">' + live.map(function (p) {
        var act = nextActionFor(p);
        return '<a class="zrow zrow--work" href="' + act.href + '">' +
          '<span class="zthumb">' + frame({ scene: p.scene, aspect: '16x9' }, { aspect: '16x9', detail: 'thumb' }) + '</span>' +
          '<span class="zrow__stack"><span class="zrow__title">' + esc(p.name) + '</span>' +
          '<span class="zrow__meta t-xs t-muted">' + esc(act.label) + '</span></span>' +
          icon('chevron-right', 'icon icon--sm zrow__go') + '</a>';
      }).join('') + '</div></section>';
  }

  function nextActionFor(p) {
    var rs = U.runsForProject(p.id);
    var wait = rs.filter(function (r) { return r.status === 'awaiting_approval'; })[0];
    if (wait) return { label: U.server().permissions.can_approve
      ? 'A step is waiting for your approval' : 'A step is waiting to be approved',
      href: '#/runs/' + wait.id };
    var fail = rs.filter(function (r) { return r.status === 'failed'; })[0];
    if (fail) return { label: 'Stopped — recoverable', href: '#/runs/' + fail.id };
    var run = rs.filter(function (r) { return r.status === 'running'; })[0];
    if (run) return { label: 'Running now', href: '#/runs/' + run.id };
    var changes = (p.assets || []).map(U.assetById).filter(function (a) { return a && a.state === 'changes'; })[0];
    if (changes) return { label: 'Notes to resolve on ' + changes.short, href: '#/review/' + changes.id };
    var rev = (p.assets || []).map(U.assetById).filter(function (a) { return a && a.state === 'review'; })[0];
    if (rev) return { label: rev.short + ' is waiting on a decision', href: '#/review/' + rev.id };
    return { label: p.updated, href: '#/projects/' + p.id };
  }

  function zoneAttention() {
    var items = U.attentionItems();
    var approvals = items.filter(function (i) { return i.kind === 'approval'; }).length;
    var failures = items.filter(function (i) { return i.kind === 'failure'; }).length;
    var reviews = items.filter(function (i) { return i.kind === 'review' || i.kind === 'changes'; }).length;
    if (!items.length) {
      return '<section class="zone zone--attention" aria-labelledby="z-need"' + anno('planned', 'notifications') + '>' +
        '<div class="zone__head"><h2 class="eyebrow" id="z-need">Needs you</h2></div>' +
        '<div class="zone__body"><p class="zone__none t-sm t-muted">Nothing is waiting on you. That is allowed.</p></div></section>';
    }
    var top = items[0];
    return '<section class="zone zone--attention" aria-labelledby="z-need"' + anno('planned', 'notifications') + '>' +
      '<div class="zone__head"><h2 class="eyebrow" id="z-need">Needs you</h2>' +
      '<a class="zone__link" href="#/runs">Everything' + icon('chevron-right', 'icon icon--sm') + '</a></div>' +
      '<div class="zone__body">' +
        '<p class="zcounts t-xs">' +
          (approvals ? '<span class="zcount zcount--warn">' + plural(approvals, 'approval') + '</span>' : '') +
          (reviews ? '<span class="zcount zcount--warn">' + plural(reviews, 'review') + '</span>' : '') +
          (failures ? '<span class="zcount zcount--bad">' + failures + ' stopped</span>' : '') +
        '</p>' +
        '<a class="zurgent" href="' + top.href + '">' +
          '<span class="zrow__title">' + esc(top.title) + '</span>' +
          '<span class="zrow__meta t-xs t-muted">' + esc(top.why) + '</span>' +
          '<span class="zurgent__act">' + esc(top.act) + icon('arrow-right', 'icon icon--sm') + '</span>' +
        '</a>' +
      '</div></section>';
  }

  PO.modes = { MODES: MODES, modeById: modeById, outputs: outputs, outputsFor: outputsFor,
               totals: totals, minutesLabel: minutesLabel, artOf: artOf,
               RECIPES: RECIPES, REF_LIBRARY: REF_LIBRARY, DESTINATIONS: DESTINATIONS, destById: destById,
               PRIMARY_BY_MODE: PRIMARY_BY_MODE, sourceName: sourceName,
               CHANNELS: CHANNELS, chanById: chanById, ESS: ESS, essFields: essFields, essField: essField,
               essValue: essValue, essSet: essSet, essLabel: essLabel };
})();

/* ==========================================================================
   CREATION PLAN — focus template
   The moment the product earns trust: everything that will be made, what it
   costs, where it stops for you, and what is honestly not built yet.
   ========================================================================== */
(function () {
  var U = PO.ui, C = PO.CAMPAIGN, M = PO.modes, c = PO.composer;
  var esc = U.esc, icon = U.icon, money = U.money, plural = U.plural, frame = U.frame, anno = U.anno;

  var STAGES = ['Understand', 'Research', 'Structure', 'Strategy', 'Plan', 'Concepts', 'Script',
                'Design', 'Production', 'Variants', 'Paid media', 'Drafts'];

  function goalLine(prompt) {
    var s = String(prompt || '').trim();
    var stop = s.search(/[.!?]\s/);
    var first = stop > 0 ? s.slice(0, stop + 1) : s;
    return first.length > 150 ? first.slice(0, 147) + '…' : first;
  }
  /* A dependent whose dependency was removed is shown as unbuildable, naming
     what it lost. Silently dropping it would hide the consequence of the edit
     the user just made — which is the entire reason this screen exists. */
  function statusOf(o, present) {
    if (!o.dep) return 'ready';
    return present[o.dep] ? 'ready' : 'blocked';
  }

  PO.views.plan = function () {
    if (!c.plan) {
      return '<div class="focus">' +
        U.empty('file-text', 'No plan is open',
          'A plan is prepared from a brief. Write one on Home and this screen fills with everything it would make, what it would cost and where it would stop for you.',
          '<a class="btn btn--primary" href="#/dashboard">Start from a brief</a>', 'h1') + '</div>';
    }
    var p = c.plan;
    var m = M.modeById(p.mode);
    var list = M.outputsFor(p.mode, p.removed, p.ess);
    var present = {}; list.forEach(function (o) { present[o.id] = true; });
    var t = M.totals(list.filter(function (o) { return statusOf(o, present) === 'ready'; }));
    var master = list.filter(function (o) { return o.id === M.PRIMARY_BY_MODE[p.mode]; })[0] || list[list.length - 1];
    var proj = p.project ? U.projectById(p.project) : null;
    var gate = U.startGate();
    var unbuilt = list.filter(function (o) { return o.truth !== 'existing'; }).length;

    var byStage = {};
    list.forEach(function (o) { (byStage[o.stage] = byStage[o.stage] || []).push(o); });

    return '<div class="focus focus--wide">' +
      U.governedNotices('start') +

      '<header class="planhead">' +
        '<p class="eyebrow">Creation plan · ' + esc(m.full) + '</p>' +
        '<h1 class="planhead__goal t-display">' + esc(goalLine(p.prompt)) + '</h1>' +
        '<p class="planhead__sub t-sm t-muted">Nothing here has been made yet. This is what ProjectOne would produce, what it would cost, and every point it stops and asks you.</p>' +
      '</header>' +

      '<div class="plan__hero"' + anno('proposed') + '>' +
        frame(M.artOf(master, m), { aspect: master.art.aspect || '16x9', cls: 'frame--hero' }) +
        '<div class="plan__herometa">' +
          '<p class="eyebrow">The master</p>' +
          '<p class="t-h2">' + esc(master.name) + '</p>' +
          '<p class="t-sm t-muted">' + esc(master.ai) + '</p>' +
          '<p class="t-sm"><strong>Everything else on this plan is derived from it.</strong> Change the master and the derivatives change with it.</p>' +
        '</div>' +
      '</div>' +

      '<div class="plan__grid">' +
        '<div class="plan__main">' +

          '<section class="band" aria-labelledby="pl-read">' +
            U.bandHead('What ProjectOne understood', null) +
            '<dl class="dl--cols">' +
              '<div><dt>The goal</dt><dd>' + esc(goalLine(p.prompt)) + '</dd></div>' +
              M.essFields(p.mode).map(function (fd) {
                return '<div><dt>' + esc(fd.label) + '</dt><dd>' + esc(M.essLabel(p.mode, fd.key, p.ess)) + '</dd></div>';
              }).join('') +
              '<div><dt>Source material</dt><dd>' + esc(p.refName || M.modeById(p.mode).source) + '</dd></div>' +
              '<div><dt>Destination</dt><dd>' + esc(M.destById(p.dest).label) + '</dd></div>' +
              (proj ? '<div><dt>Reusing</dt><dd>' + esc(proj.name) + ' — its voice, audience and existing assets</dd></div>' : '') +
            '</dl>' +
          '</section>' +

          '<section class="band" aria-labelledby="pl-del">' +
            U.bandHead('Every deliverable', null) +
            Object.keys(byStage).sort(function (a, b) { return STAGES.indexOf(a) - STAGES.indexOf(b); }).map(function (stage) {
              return '<div class="stage">' +
                '<p class="stage__label t-xs">' + esc(stage) + '</p>' +
                byStage[stage].map(function (o) { return delivRow(o, statusOf(o, present), p); }).join('') +
                '</div>';
            }).join('') +
            '<div class="band__foot">' +
              '<button type="button" class="btn btn--ghost btn--sm" data-act="deliv-add-open">' + icon('plus', 'icon icon--sm') + 'Add something back</button>' +
            '</div>' +
          '</section>' +

          '<section class="band" aria-labelledby="pl-lim">' +
            U.bandHead('What this plan cannot promise', null) +
            '<ul class="limits">' +
              (unbuilt ? '<li><strong>' + plural(unbuilt, 'deliverable') + ' on this plan cannot be generated yet.</strong> Starting production runs the planning step — the part that works end to end today — and stops there. Nothing else is produced, and nothing else is billed.</li>' : '') +
              '<li><strong>The cost is an estimate and a range, never a quote.</strong> It is drawn from ' + esc(U.DATA.estimate.basis) + '. Real usage varies with the length of what you write and what the model returns.</li>' +
              '<li><strong>Each approval covers exactly one step.</strong> Approving the planning step does not approve anything after it — the run stops again at the next gate.</li>' +
              '<li><strong>If a step is interrupted after the provider was called, resuming may call it a second time.</strong> ProjectOne treats provider work as happening at least once, never exactly once, and says so rather than quietly hiding a possible second charge.</li>' +
            '</ul>' +
          '</section>' +
        '</div>' +

        '<aside class="plan__aside" aria-labelledby="pl-sum">' +
          '<div class="summary">' +
            '<h2 class="eyebrow" id="pl-sum">Before you start</h2>' +
            '<p class="summary__figure t-display">' + money(t.low) + ' – ' + money(t.high) + '</p>' +
            '<p class="t-xs t-muted">Estimated for this plan. You will see it again, with the same numbers, before anything runs.</p>' +
            '<dl class="summary__facts">' +
              '<div><dt>Deliverables</dt><dd class="t-num">' + t.count + '</dd></div>' +
              '<div><dt>Ready in</dt><dd class="t-num">' + M.minutesLabel(t.mins) + '</dd></div>' +
              '<div><dt>Stops for you</dt><dd class="t-num">' + plural(t.gates, 'time') + '</dd></div>' +
              '<div><dt>Left this month</dt><dd class="t-num">' + money(U.budgetView().remaining) + '</dd></div>' +
            '</dl>' +
            (gate.ok
              ? '<button type="button" class="btn btn--primary btn--lg btn--block" data-act="start-open">Start production' + icon('arrow-right', 'icon') + '</button>'
              : '<button type="button" class="btn btn--primary btn--lg btn--block" disabled>Start production</button>' +
                '<p class="t-xs t-muted summary__why">' + esc(
                  gate.why === 'permission' ? gate.reason :
                  gate.why === 'breaker' ? gate.reason :
                  gate.why === 'budget' ? 'This workspace is at its monthly AI ceiling.' :
                  gate.why === 'offline' ? 'ProjectOne cannot reach its services right now.' :
                  'Too many requests in a short window. This clears on its own within a minute.') + '</p>') +
            '<p class="t-xs t-muted summary__why">Starting runs the planning step and stops at the first approval. Nothing is published anywhere.</p>' +
          '</div>' +
        '</aside>' +
      '</div>' +
    '</div>';
  };

  function delivRow(o, status, p) {
    var blocked = status === 'blocked';
    var dep = blocked ? (M.modeById(p.mode).outputs.filter(function (x) { return x.id === o.dep; })[0] || {}).name : null;
    return '<div class="deliv' + (blocked ? ' is-blocked' : '') + '"' + anno(o.truth) + '>' +
      '<span class="deliv__frame">' + frame(M.artOf(o, M.modeById(p.mode)),
            { aspect: o.art.aspect || '16x9', detail: 'thumb', n: o.n, gate: o.gate }) + '</span>' +
      '<div class="deliv__body">' +
        '<p class="deliv__name">' + esc(o.name) + (o.n > 1 ? ' <span class="t-muted">×' + o.n + '</span>' : '') +
          (o.gate ? ' <span class="deliv__gate" title="Stops and asks before it runs">' + icon('shield-check', 'icon icon--sm') + '<span class="u-sr-only">Stops and asks before it runs</span></span>' : '') + '</p>' +
        '<p class="deliv__ai t-sm t-muted">' + esc(o.ai) + '</p>' +
        (blocked
          ? '<p class="deliv__blocked t-sm">' + icon('alert-triangle', 'icon icon--sm') + 'Cannot be built — it needed <strong>' + esc(dep || 'something you removed') + '</strong>.</p>'
          : '<p class="deliv__from t-xs t-muted">' + icon('corner-down-right', 'icon icon--sm') + 'From ' + esc(o.from) + '</p>') +
      '</div>' +
      '<div class="deliv__end">' +
        '<span class="deliv__cost t-num t-sm">' + (o.low === 0 && o.high === 0 ? 'No AI cost' : money(o.low * o.n) + '–' + money(o.high * o.n)) + '</span>' +
        '<button type="button" class="btn btn--ghost btn--sm" data-act="deliv-remove" data-arg="' + o.id + '">Remove<span class="u-sr-only"> ' + esc(o.name) + ' from the plan</span></button>' +
      '</div>' +
    '</div>';
  }

  PO.plan = { goalLine: goalLine, statusOf: statusOf };
})();

/* ==========================================================================
   PROJECTS — workbench template
   ========================================================================== */
(function () {
  var U = PO.ui;
  var esc = U.esc, icon = U.icon, money = U.money, plural = U.plural, frame = U.frame, faces = U.faces, anno = U.anno;

  PO.views.projects = function () {
    var list = U.projects();
    if (!list.length) {
      return '<div class="wb"><div class="wb__main">' +
        masthead('Projects', 'Every piece of work in this workspace.') +
        U.empty('layers', 'No projects yet',
          'A project is created the moment you prepare a plan from a brief. It then holds the work, the versions, the runs and the people.',
          '<a class="btn btn--primary" href="#/dashboard">Start from a brief</a>') +
        '</div></div>';
    }
    var live = list.filter(function (p) { return p.status !== 'archive'; });
    var archived = list.filter(function (p) { return p.status === 'archive'; });
    return '<div class="wb"><div class="wb__main">' +
      masthead('Projects', plural(live.length, 'live project') + (archived.length ? ' · ' + archived.length + ' archived' : '')) +
      U.governedNotices('quiet') +
      '<div class="pgrid"' + anno('existing', 'projects and lifecycle') + '>' + live.map(projectCard).join('') + '</div>' +
      (archived.length
        ? '<section class="band">' + U.bandHead('Archived', null) +
          '<div class="pgrid pgrid--quiet">' + archived.map(projectCard).join('') + '</div>' +
          '<p class="t-xs t-muted band__note">Archived projects stay listed. Archiving keeps the record; deleting removes it.</p></section>'
        : '') +
      '</div></div>';
  };

  function masthead(title, sub, extra) {
    return '<header class="masthead">' +
      '<div><h1 class="t-display">' + esc(title) + '</h1>' +
      (sub ? '<p class="masthead__sub t-sm t-muted">' + esc(sub) + '</p>' : '') + '</div>' +
      (extra ? '<div class="masthead__end">' + extra + '</div>' : '') + '</header>';
  }
  PO.masthead = masthead;

  function projectCard(p) {
    var act = PO.nextActionFor ? PO.nextActionFor(p) : null;
    var live = (p.assets || []).map(U.assetById).filter(Boolean);
    var needs = live.filter(function (a) { return a.state === 'review' || a.state === 'changes'; }).length;
    return '<a class="pcard" href="#/projects/' + p.id + '">' +
      '<span class="pcard__art">' + frame({ scene: p.scene, aspect: '16x9' }, { aspect: '16x9' }) + '</span>' +
      '<span class="pcard__body">' +
        '<span class="pcard__top">' + U.projectBadge(p.status) +
          (p.days_out ? '<span class="pcard__due t-xs">' + icon('clock', 'icon icon--sm') + p.days_out + ' days to launch</span>' : '') + '</span>' +
        '<span class="pcard__name t-h2">' + esc(p.name) + '</span>' +
        '<span class="pcard__brief t-sm t-muted">' + esc(p.brief) + '</span>' +
        '<span class="pcard__foot">' +
          (live.length ? '<span class="t-xs t-muted">' + plural(live.length, 'deliverable') + '</span>' : '<span class="t-xs t-muted">No deliverables yet</span>') +
          (needs ? '<span class="pcard__needs t-xs">' + needs + ' waiting on someone</span>' : '') +
          '<span class="pcard__spacer"></span>' + faces(p.people || []) +
        '</span>' +
      '</span></a>';
  }

  /* -------------------------------------------------------- project detail */
  var TABS = [
    { id: 'overview', label: 'Overview' },
    { id: 'work', label: 'Deliverables' },
    { id: 'runs', label: 'Production' },
    { id: 'activity', label: 'Activity' }
  ];

  PO.views.project = function (route) {
    var p = U.projectById(route.id);
    if (!p) return PO.views.notfound({ name: 'project', id: route.id });
    var tab = route.tab || 'overview';
    var runs = U.runsForProject(p.id);
    var live = (p.assets || []).map(U.assetById).filter(Boolean);

    var body = tab === 'work' ? tabWork(p, live)
      : tab === 'runs' ? tabRuns(p, runs)
      : tab === 'activity' ? tabActivity(p)
      : tabOverview(p, live, runs);

    return '<div class="wb"><div class="wb__main">' +
      '<header class="masthead masthead--project">' +
        '<div>' +
          '<p class="eyebrow">' + esc(U.PROJECT_LABEL[p.status]) + (p.launch ? ' · launches ' + esc(p.launch) : '') + '</p>' +
          '<h1 class="t-display">' + esc(p.name) + '</h1>' +
          '<p class="masthead__sub t-sm t-muted">' + esc(p.brief) + '</p>' +
        '</div>' +
        '<div class="masthead__end">' + faces(p.people || []) +
          '<button type="button" class="iconbtn" data-act="project-menu" data-arg="' + p.id + '" id="pmenu-trigger" aria-haspopup="dialog" aria-expanded="false" aria-controls="ws-popover" aria-label="Project actions">' +
          icon('more-horizontal', 'icon icon--lg') + '</button>' +
        '</div>' +
      '</header>' +
      '<nav class="tabs" aria-label="Project sections">' + TABS.map(function (t) {
        var on = t.id === tab;
        return '<a class="tab' + (on ? ' is-on' : '') + '" href="#/projects/' + p.id + '/' + t.id + '"' + (on ? ' aria-current="page"' : '') + '>' + esc(t.label) + '</a>';
      }).join('') + '</nav>' +
      '<div class="wb__tabbody">' + body + '</div>' +
      '</div></div>';
  };

  function tabOverview(p, live, runs) {
    var hero = live[0];
    var needs = live.filter(function (a) { return a.state === 'review' || a.state === 'changes'; });
    return (hero ? '<div class="phero"' + anno('proposed') + '>' +
        '<a class="phero__art" href="#/review/' + hero.id + '">' + frame(hero, { aspect: '16x9', version: true, state: true, duration: hero.kind === 'video' ? hero.spec.split('· ')[1] : null }) + '</a>' +
        '<div class="phero__meta">' +
          '<p class="eyebrow">The master</p>' +
          '<p class="t-h2">' + esc(hero.name) + '</p>' +
          '<p class="t-sm t-muted">' + esc(hero.note) + '</p>' +
          '<p class="phero__row">' + U.assetBadge(hero.state) + '<span class="t-xs t-muted">Version ' + hero.version + ' · ' + esc(hero.updated) + '</span></p>' +
          '<a class="btn btn--secondary btn--sm" href="#/review/' + hero.id + '">Open the review' + icon('arrow-right', 'icon icon--sm') + '</a>' +
        '</div></div>' : '') +

      (needs.length ? '<section class="band">' + U.bandHead('Waiting on a decision', null) +
        '<div class="alist">' + needs.map(assetRow).join('') + '</div></section>' : '') +

      '<section class="band">' + U.bandHead('The brief', null) +
        '<p class="prose">' + esc(p.brief) + '</p>' +
        '<dl class="dl--cols">' +
          '<div><dt>Stage</dt><dd>' + esc(U.PROJECT_LABEL[p.status]) + '</dd></div>' +
          (p.launch ? '<div><dt>Launch</dt><dd>' + esc(p.launch) + ' · ' + p.days_out + ' days</dd></div>' : '') +
          '<div><dt>Deliverables</dt><dd class="t-num">' + live.length + '</dd></div>' +
          '<div><dt>Spent so far</dt><dd class="t-num">' + money(p.spent) + '</dd></div>' +
        '</dl>' +
      '</section>' +

      '<section class="band"' + anno('existing', 'server-decided transitions') + '>' + U.bandHead('Where this project can go next', null) +
        '<p class="t-sm t-muted band__note">A project moves forward one stage at a time. Which moves are legal is decided by the server and read from the payload — the prototype never works it out for itself, and neither does the application.</p>' +
        '<div class="lifecycle">' + (p.legal_transitions || []).map(function (to) {
          var danger = to === 'archive';
          return '<button type="button" class="btn ' + (danger ? 'btn--ghost' : 'btn--secondary') + ' btn--sm" data-act="' +
            (danger ? 'archive-open' : 'transition') + '" data-arg="' + p.id + ':' + to + '">' +
            esc(danger ? 'Archive this project' : 'Move to ' + U.PROJECT_LABEL[to]) + '</button>';
        }).join('') + '</div>' +
      '</section>';
  }

  function tabWork(p, live) {
    if (!live.length) return U.empty('grid', 'No deliverables yet',
      'Deliverables appear here as production makes them. Everything keeps its versions, its notes and where it was derived from.',
      '<a class="btn btn--primary" href="#/dashboard">Start from a brief</a>');
    var stages = {};
    live.forEach(function (a) { (stages[a.stage] = stages[a.stage] || []).push(a); });
    return Object.keys(stages).map(function (s) {
      return '<section class="band">' + U.bandHead(s, null) +
        '<div class="agrid">' + stages[s].map(assetCard).join('') + '</div></section>';
    }).join('');
  }

  function assetCard(a) {
    return '<a class="acard" href="#/review/' + a.id + '">' +
      '<span class="acard__art">' + frame(a, { version: true, state: true, stack: (a.versions || []).length > 1 }) + '</span>' +
      '<span class="acard__name">' + esc(a.name) + '</span>' +
      '<span class="acard__meta t-xs t-muted">' + esc(a.spec) + '</span>' +
      '<span class="acard__state">' + U.assetBadge(a.state) + '</span>' +
      '</a>';
  }
  function assetRow(a) {
    var open = (a.comments || []).filter(function (x) { return x.open; }).length;
    return '<a class="arow" href="#/review/' + a.id + '">' +
      '<span class="arow__art">' + frame(a, { detail: 'thumb' }) + '</span>' +
      '<span class="arow__body"><span class="arow__name">' + esc(a.name) + '</span>' +
      '<span class="t-xs t-muted">Version ' + a.version + ' · ' + esc(a.updated) + (open ? ' · ' + plural(open, 'open note') : '') + '</span></span>' +
      '<span class="arow__end">' + U.assetBadge(a.state) + icon('chevron-right', 'icon icon--sm') + '</span></a>';
  }
  PO.assetCard = assetCard; PO.assetRow = assetRow;

  function tabRuns(p, runs) {
    if (!runs.length) return U.empty('activity', 'Nothing has run for this project',
      'Production runs appear here with every step, what each one cost and where it stopped for you.');
    return '<div class="rlist">' + runs.map(PO.runRow).join('') + '</div>';
  }

  function tabActivity(p) {
    var items = U.DATA.activity.filter(function (a) {
      return (a.link || '').indexOf('/runs/') === -1 || U.runsForProject(p.id).some(function (r) { return a.link.indexOf(r.id) !== -1; });
    });
    return '<ol class="feed" role="list">' + items.slice(0, 8).map(PO.feedItem).join('') + '</ol>';
  }
})();

/* ==========================================================================
   PRODUCTION — the runs list and one run
   "Run" is the user-facing noun. The queue underneath it is delivery
   machinery and is never shown: a job id in the interface would make the
   queue a public contract.
   ========================================================================== */
(function () {
  var U = PO.ui;
  var esc = U.esc, icon = U.icon, money = U.money, num = U.num, plural = U.plural, frame = U.frame, anno = U.anno;

  PO.runRow = function (r) {
    var p = U.projectById(r.project_id);
    var urgent = r.status === 'awaiting_approval' || r.status === 'failed';
    return '<a class="rrow' + (urgent ? ' is-urgent' : '') + '" href="#/runs/' + r.id + '">' +
      '<span class="rrow__mark rrow__mark--' + U.RUN_TONE[r.status] + '" aria-hidden="true"></span>' +
      '<span class="rrow__body">' +
        '<span class="rrow__title">' + esc(r.title) + '</span>' +
        '<span class="rrow__meta t-xs t-muted">' + esc(p ? p.name : 'No project') + ' · started ' + esc(r.started) +
          (r.finished ? ' · finished ' + esc(r.finished) : '') + '</span>' +
      '</span>' +
      '<span class="rrow__end">' +
        (r.cost ? '<span class="t-xs t-muted t-num">' + money(r.cost) + '</span>' : '') +
        U.runBadge(r.status) + icon('chevron-right', 'icon icon--sm') +
      '</span></a>';
  };

  PO.views.runs = function () {
    var all = U.runs();
    if (!all.length) {
      return '<div class="wb"><div class="wb__main">' +
        PO.masthead('Production', 'Every run, what it cost and where it stopped.') +
        U.empty('activity', 'Nothing has run yet',
          'When you start production from a plan, the run appears here with each step, its cost and every point it stops for you.',
          '<a class="btn btn--primary" href="#/dashboard">Start from a brief</a>') + '</div></div>';
    }
    var groups = [
      { label: 'Needs you', of: ['awaiting_approval', 'failed'], none: 'Nothing is waiting on you.' },
      { label: 'In flight', of: ['running', 'pending'], none: 'Nothing is running right now.' },
      { label: 'Finished', of: ['completed'], none: 'Nothing has finished yet.' }
    ];
    return '<div class="wb"><div class="wb__main">' +
      PO.masthead('Production', plural(all.length, 'run') + ' in ' + esc(U.DATA.workspace.name)) +
      U.governedNotices('quiet') +
      groups.map(function (g) {
        var rows = all.filter(function (r) { return g.of.indexOf(r.status) !== -1; });
        return '<section class="band">' + U.bandHead(g.label, null) +
          (rows.length ? '<div class="rlist">' + rows.map(PO.runRow).join('') + '</div>'
            : '<p class="band__none t-sm t-muted">' + esc(g.none) + '</p>') + '</section>';
      }).join('') +
      '</div></div>';
  };

  /* ------------------------------------------------------------- one run */
  PO.views.run = function (route) {
    var r = U.runById(route.id);
    if (!r) return PO.views.notfound({ name: 'run', id: route.id });
    var p = U.projectById(r.project_id);
    var s = U.server();
    var gateStep = r.steps.filter(function (x) { return x.status === 'awaiting_approval'; })[0];
    var out = r.output_asset ? U.assetById(r.output_asset) : null;

    return '<div class="wb wb--split">' +
      '<div class="wb__main">' +
        '<header class="masthead">' +
          '<div><p class="eyebrow">' + esc(p ? p.name : 'No project') + '</p>' +
          '<h1 class="t-display">' + esc(r.title) + '</h1></div>' +
          '<div class="masthead__end">' + U.runBadge(r.status) + '</div>' +
        '</header>' +

        stateBanner(r, gateStep, s) +

        (r.status === 'completed' && out
          ? '<section class="band">' + U.bandHead('What it produced', '#/review/' + out.id, 'Open it') +
              '<div class="runout">' +
                '<a class="runout__art" href="#/review/' + out.id + '">' + frame(out, { aspect: '4x5' }) + '</a>' +
                '<div class="runout__body">' +
                  '<p class="t-h3">' + esc(out.name) + '</p>' +
                  '<p class="t-sm t-muted">' + esc(out.note) + '</p>' +
                  '<p class="t-sm">' + esc(r.steps[2].detail) + '</p>' +
                  '<a class="btn btn--secondary btn--sm" href="#/review/' + out.id + '">Read the outline' + icon('arrow-right', 'icon icon--sm') + '</a>' +
                '</div></div></section>'
          : '') +

        '<section class="band"' + anno('existing', 'the real step record') + '>' + U.bandHead('Every step', null) +
          '<ol class="timeline" role="list">' + r.steps.map(function (st) { return timelineStep(st, r); }).join('') + '</ol>' +
        '</section>' +
      '</div>' +

      '<aside class="wb__side" aria-label="Run facts">' +
        '<div class="side">' +
          '<h2 class="eyebrow">This run</h2>' +
          '<dl class="side__facts">' +
            '<div><dt>Started</dt><dd>' + esc(r.started) + '</dd></div>' +
            (r.finished ? '<div><dt>Finished</dt><dd>' + esc(r.finished) + '</dd></div>' : '') +
            '<div><dt>Started by</dt><dd>' + esc(U.person(r.by).name) + '</dd></div>' +
            '<div><dt>Workflow</dt><dd>Project planning · version ' + r.version + '</dd></div>' +
            '<div><dt>Cost so far</dt><dd class="t-num">' + money(r.cost) + '</dd></div>' +
          '</dl>' +
          '<p class="t-xs t-muted side__note">Cost is metered per step as it completes. A step that never returned a completion is never billed.</p>' +
          '<details class="disclose"><summary>Technical detail</summary>' +
            '<dl class="side__facts side__facts--tight">' +
              '<div><dt>Tokens used</dt><dd class="t-num">' + num(r.tokens) + '</dd></div>' +
              '<div><dt>Provider</dt><dd>' + esc(U.DATA.providers[0].label) + '</dd></div>' +
              '<div><dt>Model</dt><dd class="t-mono t-xs">' + esc(U.DATA.providers[0].model) + '</dd></div>' +
            '</dl>' +
          '</details>' +
        '</div>' +
      '</aside>' +
    '</div>';
  };

  function stateBanner(r, gateStep, s) {
    var can = s.permissions.can_approve;
    if (r.status === 'awaiting_approval') {
      /* "Your approval" is only true for someone who can give it. A Member
         reading their own name in a sentence they cannot act on is the small
         lie that makes people distrust the big statements. */
      return U.notice('warn', 'shield-check',
        can ? 'One step is waiting for your approval.' : 'One step is waiting to be approved.',
        '<strong>' + esc(U.stepDef(gateStep.index).name) + '</strong> is the first step that calls an AI provider, so production stops here and asks. ' +
        'Approving releases <em>this step only</em> — the run stops again at the next gate.',
        can
          ? '<button type="button" class="btn btn--primary" data-act="approve-open" data-arg="' + r.id + '">Review and approve</button>'
          : '<span class="t-xs t-muted">' + esc(s.permissions.denied_reason || 'Your role cannot approve steps.') + '</span>');
    }
    if (r.status === 'failed') {
      return U.notice('bad', 'alert-triangle', r.failure ? r.failure.headline : 'This run stopped before it finished.',
        r.failure ? esc(r.failure.plain) : 'The run did not complete. Nothing after the failing step was executed.',
        '<button type="button" class="btn btn--secondary" data-act="failure-open" data-arg="' + r.id + '">What happened</button>' +
        '<button type="button" class="btn btn--primary" data-act="resume-open" data-arg="' + r.id + '">Resume</button>');
    }
    if (r.status === 'running') {
      return U.notice('info', 'spinner', 'Production is running.',
        (r.approved_note ? esc(r.approved_note) + ' ' : '') +
        'You can leave this screen — the run continues without it, and you will be told when it needs you.');
    }
    if (r.status === 'pending') {
      return U.notice('info', 'hourglass', 'Queued.',
        esc(r.queue_note || 'This run is waiting for a worker.') + ' Starting a run hands it to production and returns immediately; nothing executes inside the request that started it.');
    }
    return U.notice('ok', 'check-circle', 'Finished.',
      'Every step completed and the result was saved to the project. Only the planning workflow runs end to end today; nothing else on the plan was generated, and nothing else was billed.');
  }

  function timelineStep(st, r) {
    var def = U.stepDef(st.index);
    var ic = { completed: 'check', running: 'spinner', awaiting_approval: 'shield-check', failed: 'x', pending: 'clock' }[st.status] || 'clock';
    return '<li class="tlstep tlstep--' + st.status + '">' +
      '<span class="tlstep__marker" aria-hidden="true">' + icon(ic, 'icon icon--sm') + '</span>' +
      '<div class="tlstep__body">' +
        '<p class="tlstep__head"><span class="tlstep__name">' + esc(def.name) + '</span>' +
          U.badge(U.RUN_TONE[st.status] || 'neutral', U.RUN_LABEL[st.status] || st.status) +
          (def.requires_approval ? '<span class="tlstep__gate t-xs">' + icon('shield-check', 'icon icon--sm') + 'Approval gate</span>' : '') + '</p>' +
        '<p class="t-sm t-muted">' + esc(def.purpose) + '</p>' +
        (st.detail ? '<p class="tlstep__detail t-sm">' + esc(st.detail) + '</p>' : '') +
        (st.approved_by ? '<p class="t-xs t-muted">' + icon('check', 'icon icon--sm') + 'Approved by ' + esc(st.approved_by) + ' — this approval covered this step only.</p>' : '') +
        (st.status === 'failed' && r.failure ? stepFailureLog(r) : '') +
        '<p class="tlstep__facts t-xs t-muted">' +
          (st.duration ? esc(st.duration) : 'Not started') +
          (st.tokens ? ' · ' + num(st.tokens) + ' tokens · ' + money(st.cost) : (st.status === 'completed' ? ' · no AI call, nothing billed' : '')) +
        '</p>' +
        '<p class="tlstep__touch t-xs t-muted">' + esc(def.touches) + '</p>' +
      '</div></li>';
  }

  function stepFailureLog(r) {
    return '<div class="failbox">' +
      '<p class="t-sm"><strong>Why it stopped rather than retrying.</strong> ' + esc(r.failure.why_stopped) + '</p>' +
      '<p class="t-sm">' + esc(r.failure.billed) + '</p>' +
      '<details class="disclose"><summary>Show the attempt log</summary>' +
      '<pre class="log t-mono t-xs">' + esc(r.failure.technical) + '</pre></details></div>';
  }
})();

/* ==========================================================================
   REVIEW — the surface the thesis promises
   The work large, its versions behind it, notes pinned to the place they are
   about, and exactly one decision.
   ========================================================================== */
(function () {
  var U = PO.ui, C = PO.CAMPAIGN;
  var esc = U.esc, icon = U.icon, plural = U.plural, frame = U.frame, avatar = U.avatar;

  PO.views.review = function (route) {
    var a = U.assetById(route.id);
    if (!a) return PO.views.notfound({ name: 'review', id: route.id });
    var s = U.server();
    var open = (a.comments || []).filter(function (x) { return x.open; });
    var derived = U.assets().filter(function (x) { return x.from === a.id; });
    var src = a.from ? U.assetById(a.from) : null;
    var canDecide = s.permissions.can_approve;

    return '<div class="wb wb--split review"' + U.anno('proposed', 'versions, notes and approval on a deliverable') + '>' +
      '<div class="wb__main review__stage">' +
        '<header class="masthead masthead--tight">' +
          '<div><p class="eyebrow">' + esc(a.stage) + ' · version ' + a.version + '</p>' +
          '<h1 class="t-display">' + esc(a.name) + '</h1></div>' +
          '<div class="masthead__end">' + U.assetBadge(a.state) + '</div>' +
        '</header>' +

        '<div class="stagewrap">' +
          '<div class="stage__frame">' +
            frame(a, { aspect: a.doc === 'carousel' ? '1x1' : (a.doc ? '4x5' : a.aspect), cls: 'frame--stage', stack: (a.versions || []).length > 1 }) +
            (a.comments || []).map(function (cm, i) {
              return '<button type="button" class="pin' + (cm.open ? '' : ' is-done') + '" data-act="pin" data-arg="' + cm.id + '"' +
                ' style="left:' + cm.x + '%;top:' + cm.y + '%" aria-label="Note from ' + esc(U.person(cm.who).name) + ' at ' + esc(cm.at) + '">' +
                '<span class="pin__ring" aria-hidden="true"></span><span class="pin__n">' + (i + 1) + '</span></button>';
            }).join('') +
          '</div>' +
          '<p class="stage__caption t-xs t-muted">' + esc(a.spec) + ' · ' + esc(a.size) +
            (src ? ' · derived from <a href="#/review/' + src.id + '">' + esc(src.name) + '</a> at ' + esc(a.fromAt) : '') + '</p>' +
        '</div>' +

        (a.state === 'blocked'
          ? U.notice('bad', 'ban', 'This has not been cut yet.', esc(a.note))
          : '') +

        (derived.length
          ? '<section class="band">' + U.bandHead('Derived from this', null) +
            '<div class="agrid agrid--small">' + derived.map(PO.assetCard).join('') + '</div>' +
            '<p class="t-xs t-muted band__note">Changing this master is what these are waiting on. Nothing downstream is re-cut until it is approved.</p></section>'
          : '') +
      '</div>' +

      '<aside class="wb__side review__side" aria-label="Review">' +
        '<div class="side">' +
          '<h2 class="eyebrow">Decision</h2>' +
          (a.state === 'approved'
            ? '<div class="approved">' + icon('check-circle', 'icon icon--lg') +
              '<p class="t-sm"><strong>Approved</strong> by ' + esc(U.person(a.approvedBy).name) + ' · ' + esc(a.approvedAt) + '</p></div>'
            : canDecide
              ? '<div class="side__act">' +
                  '<button type="button" class="btn btn--primary btn--block" data-act="approve-asset" data-arg="' + a.id + '">' + icon('check', 'icon icon--sm') + 'Approve version ' + a.version + '</button>' +
                  '<button type="button" class="btn btn--secondary btn--block" data-act="request-changes" data-arg="' + a.id + '">Request changes</button>' +
                '</div>'
              : '<p class="t-sm t-muted">' + esc(s.permissions.denied_reason || 'Your role cannot approve work.') +
                ' You can still leave notes — they go to whoever can.</p>') +
          (a.state !== 'approved' && open.length
            ? '<p class="t-xs t-muted side__note">' + plural(open.length, 'note') + ' still open. Approving does not close them.</p>' : '') +

          '<h2 class="eyebrow side__h">Notes</h2>' +
          (a.comments && a.comments.length
            ? '<ol class="notes" role="list">' + a.comments.map(function (cm, i) {
                return '<li class="note' + (cm.open ? '' : ' is-done') + '" id="note-' + cm.id + '">' +
                  '<span class="note__n">' + (i + 1) + '</span>' +
                  '<div class="note__body">' +
                    '<p class="note__who">' + avatar(cm.who, 'sm') + '<span>' + esc(U.person(cm.who).name) + '</span>' +
                      '<span class="note__at t-xs t-muted">' + esc(cm.at) + '</span></p>' +
                    '<p class="note__text t-sm">' + esc(cm.text) + '</p>' +
                    '<p class="note__foot t-xs t-muted">' + esc(cm.when) +
                      (cm.open ? ' · <button type="button" class="linkbtn" data-act="note-resolve" data-arg="' + cm.id + '">Mark resolved</button>' : ' · resolved') + '</p>' +
                  '</div></li>';
              }).join('') + '</ol>'
            : '<p class="t-sm t-muted">No notes yet. Notes are pinned to the moment they are about.</p>') +
          '<div class="notenew">' +
            '<label class="u-sr-only" for="note-input">Add a note</label>' +
            '<textarea id="note-input" class="input input--area" rows="2" placeholder="Leave a note for whoever picks this up…"></textarea>' +
            '<button type="button" class="btn btn--secondary btn--sm" data-act="note-add" data-arg="' + a.id + '">Add note</button>' +
          '</div>' +

          '<h2 class="eyebrow side__h">Versions</h2>' +
          ((a.versions || []).length
            ? '<ol class="vers" role="list">' + a.versions.map(function (v, i) {
                return '<li class="ver' + (i === 0 ? ' is-current' : '') + '">' +
                  '<span class="ver__n">v' + v.n + '</span>' +
                  '<div><p class="t-sm">' + esc(v.note) + '</p>' +
                  '<p class="t-xs t-muted">' + esc(U.person(v.who).name) + ' · ' + esc(v.when) + (i === 0 ? ' · current' : '') + '</p></div>' +
                  (i === 0 ? '' : '<button type="button" class="linkbtn" data-act="ver-restore" data-arg="' + a.id + ':' + v.n + '">Restore</button>') +
                '</li>';
              }).join('') + '</ol>'
            : '<p class="t-sm t-muted">No versions yet.</p>') +
        '</div>' +
      '</aside>' +
    '</div>';
  };
})();

/* ==========================================================================
   STUDIO — cockpit template
   Where "editable" stops being a promise in a data model and becomes a
   control. The rail is what else is in the project, the canvas is the work,
   the inspector is what you can change and what changing it costs.
   ========================================================================== */
(function () {
  var U = PO.ui, C = PO.CAMPAIGN;
  var esc = U.esc, icon = U.icon, money = U.money, plural = U.plural, frame = U.frame;

  var BEATS = [
    { at: '0:00', label: 'Cold open', scene: 'flame' },
    { at: '0:14', label: 'The pan', scene: 'sear' },
    { at: '0:41', label: 'The flip', scene: 'flip' },
    { at: '1:06', label: 'The rise', scene: 'loaf' },
    { at: '1:28', label: 'The blade', scene: 'knife' },
    { at: '1:44', label: 'Title', scene: 'quote' }
  ];

  var SCRIPT_LINES = [
    { at: '0:00', who: 'AVERY (V.O.)', text: 'Everyone tells you to be gentle.' },
    { at: '0:06', who: 'AVERY (V.O.)', text: 'Nobody tells you the pan is the one thing in this kitchen that wants to be treated badly.' },
    { at: '0:14', who: 'ON SCREEN', text: 'Six techniques. Six episodes.' },
    { at: '0:41', who: 'AVERY (V.O.)', text: 'You want it hotter than you think. Then you leave it alone.' },
    { at: '1:44', who: 'ON SCREEN', text: 'Cook it scared. — 14 September' }
  ];

  PO.views.studio = function (route) {
    var list = U.assets();
    if (!list.length) {
      return '<div class="studio studio--empty">' + U.empty('scissors', 'Nothing to edit yet',
        'The studio opens on a deliverable. Prepare a plan, start production, and whatever it makes lands here where you can change it.',
        '<a class="btn btn--primary" href="#/dashboard">Start from a brief</a>', 'h1') + '</div>';
    }
    var a = (route.id && U.assetById(route.id)) || U.assetById('as_trailer') || list[0];
    var beat = PO.studioBeat == null ? 2 : PO.studioBeat;
    var isTimeline = a.kind === 'video' || a.kind === 'clip';

    return '<div class="studio"' + U.anno('proposed', 'no editing surface exists yet') + '>' +
      '<header class="studio__bar">' +
        '<div class="studio__id">' +
          '<span class="eyebrow">' + esc(a.stage) + '</span>' +
          '<h1 class="studio__name t-h1">' + esc(a.name) + '</h1>' +
          '<span class="studio__ver">v' + a.version + '</span>' + U.assetBadge(a.state) +
        '</div>' +
        '<div class="studio__acts">' +
          '<span class="studio__saved t-xs t-muted">' + icon('check', 'icon icon--sm') + 'All changes kept</span>' +
          '<a class="btn btn--secondary btn--sm" href="#/review/' + a.id + '">Open the review</a>' +
          '<button type="button" class="btn btn--primary btn--sm" data-act="regen-open" data-arg="' + a.id + '">Regenerate…</button>' +
        '</div>' +
      '</header>' +

      '<div class="studio__body">' +
        '<nav class="studio__rail" aria-label="Deliverables in this project">' +
          '<p class="eyebrow studio__railhead">This project</p>' +
          '<ul class="srail" role="list">' + list.slice(0, 9).map(function (x) {
            var on = x.id === a.id;
            return '<li><a class="srail__item' + (on ? ' is-on' : '') + '" href="#/studio/' + x.id + '"' + (on ? ' aria-current="page"' : '') + '>' +
              '<span class="srail__art">' + frame(x, { detail: 'thumb' }) + '</span>' +
              '<span class="srail__name">' + esc(x.short) + '</span>' +
              (x.state === 'changes' || x.state === 'review' ? '<span class="srail__dot" aria-hidden="true"></span>' : '') +
              '</a></li>';
          }).join('') + '</ul>' +
        '</nav>' +

        '<main class="studio__canvas">' +
          '<div class="canvas__frame">' +
            frame(isTimeline ? { scene: BEATS[beat].scene, aspect: a.aspect, lockup: beat === 5 ? 'end' : (beat === 0 ? 'title' : 'caption'),
                                 lockupTitle: C.brand, lockupEyebrow: C.season, caption: 'you want the pan hotter than you think' } : a,
                  { aspect: a.doc === 'carousel' ? '1x1' : (a.doc ? '4x5' : a.aspect), cls: 'frame--canvas' }) +
          '</div>' +
          (isTimeline
            ? '<div class="tl" role="group" aria-label="Timeline">' +
                '<div class="tl__track">' + BEATS.map(function (b, i) {
                  return '<button type="button" class="tlb' + (i === beat ? ' is-on' : '') + '" data-act="beat" data-arg="' + i + '" aria-pressed="' + (i === beat) + '">' +
                    '<span class="tlb__art">' + frame({ scene: b.scene, aspect: '16x9' }, { aspect: '16x9', detail: 'thumb' }) + '</span>' +
                    '<span class="tlb__at t-xs">' + esc(b.at) + '</span>' +
                    '<span class="tlb__label t-xs">' + esc(b.label) + '</span></button>';
                }).join('') + '</div>' +
                '<p class="tl__note t-xs t-muted">Six beats, cut from the same shoot. Selecting one shows the frame the derivatives are pulled from.</p>' +
              '</div>'
            : '') +
        '</main>' +

        '<aside class="studio__inspect" aria-label="Inspector">' +
          (isTimeline ? inspectorVideo(a, beat) : inspectorText(a)) +
        '</aside>' +
      '</div>' +
    '</div>';
  };

  function inspectorVideo(a, beat) {
    var b = BEATS[beat];
    var line = SCRIPT_LINES.filter(function (l) { return l.at === b.at; })[0] || SCRIPT_LINES[0];
    return '<section class="insp">' +
      '<h2 class="eyebrow">Beat ' + (beat + 1) + ' · ' + esc(b.at) + '</h2>' +
      '<p class="insp__title t-h3">' + esc(b.label) + '</p>' +
      '<label class="field"><span class="field__label">What is said here</span>' +
        '<textarea class="input input--area" rows="3">' + esc(line.text) + '</textarea>' +
        '<span class="field__hint t-xs t-muted">Editing the line re-times the captions and marks the master for a re-cut. Nothing regenerates until you ask.</span>' +
      '</label>' +
      '<label class="field"><span class="field__label">Direction for this shot</span>' +
        '<textarea class="input input--area" rows="2">Hold the pan two beats longer. Keep the rim light.</textarea>' +
      '</label>' +
      '<h2 class="eyebrow insp__h">If you regenerate this beat</h2>' +
      '<dl class="side__facts">' +
        '<div><dt>Estimated</dt><dd class="t-num">$0.18 – $0.44</dd></div>' +
        '<div><dt>Affects</dt><dd>This beat, the captions, and 2 derivatives</dd></div>' +
        '<div><dt>Approval</dt><dd>Yes — a re-cut of the master is gated</dd></div>' +
      '</dl>' +
      '<button type="button" class="btn btn--primary btn--block" data-act="regen-open" data-arg="' + a.id + '">Regenerate this beat…</button>' +
      '<p class="t-xs t-muted insp__note">You will see the cost and what it touches before anything runs.</p>' +
    '</section>';
  }

  function inspectorText(a) {
    return '<section class="insp">' +
      '<h2 class="eyebrow">Content</h2>' +
      '<div class="scriptedit" role="group" aria-label="Script lines">' +
        SCRIPT_LINES.map(function (l, i) {
          return '<div class="sline' + (i === 3 ? ' is-flagged' : '') + '">' +
            '<span class="sline__at t-mono t-xs">' + esc(l.at) + '</span>' +
            '<div class="sline__body"><p class="sline__who t-xs">' + esc(l.who) + '</p>' +
            '<p class="sline__text t-sm" contenteditable="false">' + esc(l.text) + '</p></div></div>';
        }).join('') +
      '</div>' +
      '<h2 class="eyebrow insp__h">Facts</h2>' +
      '<dl class="side__facts">' +
        '<div><dt>Format</dt><dd>' + esc(a.spec) + '</dd></div>' +
        '<div><dt>Version</dt><dd class="t-num">v' + a.version + '</dd></div>' +
        '<div><dt>Owner</dt><dd>' + esc(U.person(a.owner).name) + '</dd></div>' +
        '<div><dt>Updated</dt><dd>' + esc(a.updated) + '</dd></div>' +
      '</dl>' +
      '<button type="button" class="btn btn--primary btn--block" data-act="regen-open" data-arg="' + a.id + '">Rewrite with AI…</button>' +
      '<p class="t-xs t-muted insp__note">Editing by hand costs nothing and is never sent anywhere. Only regenerating calls a provider.</p>' +
    '</section>';
  }

  PO.studioBeat = 2;
  PO.BEATS = BEATS;
})();

/* ==========================================================================
   LIBRARY — cockpit template. Everything the workspace has made, plus the
   recipes that make more of it.
   ========================================================================== */
(function () {
  var U = PO.ui, C = PO.CAMPAIGN;
  var esc = U.esc, icon = U.icon, money = U.money, plural = U.plural, frame = U.frame;

  var FILTERS = [
    { id: 'all', label: 'Everything' },
    { id: 'moving', label: 'Video', of: ['video', 'clip'] },
    { id: 'still', label: 'Stills', of: ['image', 'sheet', 'carousel'] },
    { id: 'written', label: 'Written', of: ['script', 'newsletter', 'caption', 'outline'] },
    /* Paid work cuts across every medium — a pre-roll is video, a banner is a
       still, the copy is written — so it filters on what it is FOR, not on
       what it is made of. */
    { id: 'paid', label: 'Paid media', paid: true },
    { id: 'needs', label: 'Needs you', states: ['review', 'changes'] }
  ];
  PO.libFilter = 'all';

  PO.views.library = function (route) {
    var tab = route.tab === 'recipes' ? 'recipes' : 'assets';
    return '<div class="lib"' + U.anno('proposed', 'assets are project-scoped today') + '>' +
      '<header class="masthead">' +
        '<div><h1 class="t-display">Library</h1>' +
        '<p class="masthead__sub t-sm t-muted">' +
          (tab === 'recipes' ? 'Proven starting points. Each one fills the composer and shows you what it would make.'
            : 'Everything this workspace has made, with its versions and its notes.') + '</p></div>' +
      '</header>' +
      '<nav class="tabs" aria-label="Library sections">' +
        '<a class="tab' + (tab === 'assets' ? ' is-on' : '') + '" href="#/library/assets"' + (tab === 'assets' ? ' aria-current="page"' : '') + '>Work</a>' +
        '<a class="tab' + (tab === 'recipes' ? ' is-on' : '') + '" href="#/library/recipes"' + (tab === 'recipes' ? ' aria-current="page"' : '') + '>Recipes</a>' +
      '</nav>' +
      (tab === 'recipes' ? recipesTab() : assetsTab()) +
      '</div>';
  };

  function assetsTab() {
    var all = U.assets();
    if (!all.length) return U.empty('grid', 'Nothing here yet',
      'Everything production makes lands in the library — masters, derivatives, scripts, stills — each with its versions and where it came from.',
      '<a class="btn btn--primary" href="#/dashboard">Start from a brief</a>');
    var f = FILTERS.filter(function (x) { return x.id === PO.libFilter; })[0] || FILTERS[0];
    var list = all.filter(function (a) {
      if (f.of) return f.of.indexOf(a.kind) !== -1;
      if (f.paid) return !!a.paid;
      if (f.states) return f.states.indexOf(a.state) !== -1;
      return true;
    });
    return '<div class="lib__bar">' +
        '<div class="filters" role="group" aria-label="Filter the library">' + FILTERS.map(function (x) {
          var on = x.id === PO.libFilter;
          var n = x.of ? all.filter(function (a) { return x.of.indexOf(a.kind) !== -1; }).length
                : x.paid ? all.filter(function (a) { return !!a.paid; }).length
                : x.states ? all.filter(function (a) { return x.states.indexOf(a.state) !== -1; }).length : all.length;
          return '<button type="button" class="filter' + (on ? ' is-on' : '') + '" data-act="lib-filter" data-arg="' + x.id + '" aria-pressed="' + on + '">' +
            esc(x.label) + '<span class="filter__n">' + n + '</span></button>';
        }).join('') + '</div>' +
        '<p class="lib__count t-xs t-muted">' + plural(list.length, 'item') + ' · one campaign · ' + esc(C.title) + '</p>' +
      '</div>' +
      (list.length
        ? '<div class="agrid agrid--lib">' + list.map(function (a) {
            return '<a class="acard" href="#/review/' + a.id + '">' +
              '<span class="acard__art">' + frame(a, { version: true, state: true, stack: (a.versions || []).length > 1 }) + '</span>' +
              '<span class="acard__name">' + esc(a.name) + '</span>' +
              '<span class="acard__meta t-xs t-muted">' + (a.placement ? esc(a.placement) + ' · ' : '') + esc(a.spec) + '</span>' +
              '<span class="acard__state">' + U.assetBadge(a.state) +
                '<button type="button" class="linkbtn acard__more" data-act="asset-inspect" data-arg="' + a.id + '">Details</button></span>' +
              '</a>';
          }).join('') + '</div>'
        : U.empty('eye', 'Nothing matches that filter', 'Try a different one — everything is still here.'));
  }

  function recipesTab() {
    var M = PO.modes;
    return '<div class="rgrid">' + M.RECIPES.map(function (r) {
      var m = M.modeById(r.mode);
      var t = M.totals(M.outputsFor(r.mode, {}, {}));
      var master = m.outputs.filter(function (o) { return o.id === M.PRIMARY_BY_MODE[r.mode]; })[0] || m.outputs[0];
      return '<article class="rcard">' +
        '<span class="rcard__art">' + frame(M.artOf(master, m), { aspect: '16x9' }) + '</span>' +
        '<div class="rcard__body">' +
          '<p class="eyebrow">' + esc(m.full) + '</p>' +
          '<h2 class="t-h2">' + esc(r.name) + '</h2>' +
          '<p class="t-sm t-muted">' + esc(r.note) + '</p>' +
          '<p class="rcard__facts t-xs t-muted t-num">' + plural(t.count, 'deliverable') + ' · ' + money(t.low) + '–' + money(t.high) + ' · ' + plural(t.gates, 'approval') + '</p>' +
          '<button type="button" class="btn btn--secondary btn--sm" data-act="recipe" data-arg="' + r.id + '">Use this recipe' + icon('arrow-right', 'icon icon--sm') + '</button>' +
        '</div></article>';
    }).join('') + '</div>';
  }
})();

/* ==========================================================================
   ACTIVITY · ASSISTANT · AI SPEND
   ========================================================================== */
(function () {
  var U = PO.ui, C = PO.CAMPAIGN;
  var esc = U.esc, icon = U.icon, money = U.money, num = U.num, plural = U.plural, frame = U.frame, avatar = U.avatar, anno = U.anno;

  var KIND_IC = { version: 'upload', comment: 'message-square', review: 'eye', run: 'activity',
                  approval: 'check-circle', failure: 'alert-triangle', member: 'users' };

  PO.feedItem = function (a) {
    return '<li class="fitem fitem--' + a.kind + '">' +
      '<span class="fitem__mark" aria-hidden="true">' + icon(KIND_IC[a.kind] || 'activity', 'icon icon--sm') + '</span>' +
      '<div class="fitem__body">' +
        '<p class="fitem__line">' + (a.who ? '<strong>' + esc(U.person(a.who).name) + '</strong> ' : '<strong>Production</strong> ') +
          esc(a.what) + ' <a href="' + a.link + '">' + esc(a.target) + '</a></p>' +
        '<p class="t-xs t-muted">' + esc(a.detail) + '</p>' +
      '</div>' +
      '<span class="fitem__when t-xs t-muted">' + esc(a.when) + '</span>' +
    '</li>';
  };

  PO.views.activity = function () {
    var items = U.server().empty ? [] : U.DATA.activity;
    if (!items.length) {
      return '<div class="wb"><div class="wb__main">' + PO.masthead('Activity', 'Everything that has happened in this workspace.') +
        U.empty('history', 'Nothing has happened yet', 'Every version, note, approval and run appears here, with who did it and when.') +
        '</div></div>';
    }
    return '<div class="wb"><div class="wb__main">' +
      PO.masthead('Activity', 'Everything that has happened in ' + U.DATA.workspace.name + ', newest first.') +
      '<ol class="feed" role="list"' + anno('planned') + '>' + items.map(PO.feedItem).join('') + '</ol>' +
      '<p class="t-xs t-muted band__note"' + anno('planned') + '>Actions that change permissions, budgets or ownership are recorded separately and are kept even after the records they describe are deleted. That trail exists so it can outlive what it records.</p>' +
      '</div></div>';
  };

  /* --------------------------------------------------------------- assistant */
  var THREAD = [
    { who: 'user', text: 'What is actually blocking the season two trailer?' },
    { who: 'ai', text: 'Two things, and only one of them is yours.\n\nThe master is at version 4 and out for review with Noor. Diego left a note at 00:41 asking you to hold the flip two beats longer — that note is still open.\n\nThe 30-second cut and Six Techniques are both waiting on the master’s colour lock, so neither is queued behind a machine. They are queued behind a decision.',
      cites: [{ label: 'Season Two — Trailer', href: '#/review/as_trailer' }, { label: 'Trailer — 30 second cut', href: '#/review/as_b30' }] },
    { who: 'user', text: 'Draft a reply to Diego.' },
    { who: 'ai', text: 'Here is a draft. It is a draft — I have not sent anything, and I cannot: posting a note on your behalf is an action you approve, not one I take.\n\n“Agreed on the flip. Holding it two beats puts the title card past 1:46, which is fine — the end plate has room. Re-cutting tonight, v5 in the morning.”',
      act: { label: 'Put this in the note box', href: '#/review/as_trailer' } }
  ];

  PO.views.assistant = function () {
    return '<div class="wb wb--split">' +
      '<div class="wb__main chat"' + U.anno('existing', 'AI chat ships today') + '>' +
        PO.masthead('Assistant', 'It can read this workspace, and it says what it is not allowed to do.') +
        '<ol class="thread" role="list">' + THREAD.map(function (m) {
          if (m.who === 'user') return '<li class="turn turn--you"><span class="turn__who">' + avatar(U.server().user.id, 'sm') + '</span>' +
            '<div class="bubble bubble--you"><p>' + esc(m.text) + '</p></div></li>';
          return '<li class="turn turn--ai"><span class="turn__who turn__who--ai" aria-hidden="true">' + icon('zap', 'icon icon--sm') + '</span>' +
            '<div class="bubble">' + m.text.split('\n\n').map(function (p) { return '<p>' + esc(p) + '</p>'; }).join('') +
            (m.cites ? '<p class="cites">' + m.cites.map(function (ct) { return '<a class="cite" href="' + ct.href + '">' + icon('corner-down-right', 'icon icon--sm') + esc(ct.label) + '</a>'; }).join('') + '</p>' : '') +
            (m.act ? '<p class="bubble__act"><a class="btn btn--secondary btn--sm" href="' + m.act.href + '">' + esc(m.act.label) + '</a></p>' : '') +
            '</div></li>';
        }).join('') + '</ol>' +
        '<div class="chat__composer">' +
          '<label class="u-sr-only" for="chat-input">Ask the assistant</label>' +
          '<textarea id="chat-input" class="input input--area" rows="2" placeholder="Ask about this workspace…"></textarea>' +
          '<button type="button" class="btn btn--primary" data-act="chat-send">Send' + icon('send', 'icon icon--sm') + '</button>' +
        '</div>' +
      '</div>' +
      '<aside class="wb__side" aria-label="What the assistant can do">' +
        '<div class="side">' +
          '<h2 class="eyebrow">What it can see</h2>' +
          '<ul class="ticks"><li>' + icon('check', 'icon icon--sm') + 'Projects, deliverables, versions and notes in this workspace</li>' +
          '<li>' + icon('check', 'icon icon--sm') + 'Runs, their steps and what each one cost</li>' +
          '<li>' + icon('check', 'icon icon--sm') + 'This conversation</li></ul>' +
          '<h2 class="eyebrow side__h">What it will not do without you</h2>' +
          '<ul class="ticks ticks--no"><li>' + icon('x', 'icon icon--sm') + 'Approve a step or a version</li>' +
          '<li>' + icon('x', 'icon icon--sm') + 'Start production or spend money</li>' +
          '<li>' + icon('x', 'icon icon--sm') + 'Send, post or publish anything</li>' +
          '<li>' + icon('x', 'icon icon--sm') + 'Delete anything</li></ul>' +
          '<p class="t-xs t-muted side__note">It drafts and it explains. Every action with a consequence outside this workspace is yours to take.</p>' +
        '</div>' +
      '</aside>' +
    '</div>';
  };

  /* -------------------------------------------------------------- ai spend */
  PO.views.spend = function () {
    var b = U.budgetView(), s = U.server();
    var rows = s.empty ? [] : U.DATA.spend;
    var byDay = [8, 22, 14, 41, 96, 34, 12, 62, 28, 47, 18, 71, 39, 24];
    var peak = Math.max.apply(null, byDay);
    return '<div class="lib">' +
      PO.masthead('AI spend', 'What this workspace has spent, what stops it, and how to stop it now.') +
      U.governedNotices('quiet') +

      '<div class="spendtop">' +
        '<section class="spendcard spendcard--wide"' + anno('existing') + '>' +
          '<h2 class="eyebrow">This period · ' + esc(b.period) + '</h2>' +
          '<p class="spendcard__figure t-display">' + money(b.spent) + '</p>' +
          '<p class="t-sm t-muted">of ' + money(b.limit) + ' · ' + money(b.remaining) + ' left</p>' +
          '<div class="meter"><span class="meter__fill meter__fill--' + (b.over ? 'bad' : b.pct > 80 ? 'warn' : 'ok') + '" style="width:' + b.pct + '%"></span></div>' +
          '<div class="spark" role="img" aria-label="Daily spend for the last fourteen days, peaking at ' + money(peak) + '">' +
            byDay.map(function (v) { return '<span class="spark__bar" style="height:' + Math.max(6, Math.round((v / peak) * 100)) + '%"></span>'; }).join('') +
          '</div>' +
          '<p class="t-xs t-muted">Last fourteen days. The spike is the key-art generation on 19 August.</p>' +
        '</section>' +

        '<section class="spendcard"' + anno('existing') + '>' +
          '<h2 class="eyebrow">What stops a runaway</h2>' +
          '<ul class="ticks ticks--tight">' +
            '<li>' + icon('check', 'icon icon--sm') + 'A monthly ceiling for the workspace</li>' +
            '<li>' + icon('check', 'icon icon--sm') + 'A breaker that trips on repeated provider failure</li>' +
            '<li>' + icon('check', 'icon icon--sm') + 'At most 3 attempts per provider, across at most 2 providers</li>' +
            '<li>' + icon('check', 'icon icon--sm') + 'A hard ceiling on steps, wall-clock time and tokens per run</li>' +
          '</ul>' +
          '<p class="t-xs t-muted">Every one of these fails loudly. None of them degrades quietly into a larger bill.</p>' +
        '</section>' +

        '<section class="spendcard spendcard--stop">' +
          '<h2 class="eyebrow">Stop everything</h2>' +
          '<p class="t-sm">Pauses every AI call in this workspace immediately. Work already saved is untouched, and runs in flight are allowed to finish the step they are on rather than being cut off mid-draft.</p>' +
          '<button type="button" class="btn btn--danger btn--block" data-act="killswitch">' + icon('ban', 'icon icon--sm') + 'Pause all AI spend</button>' +
          '<p class="t-xs t-muted">Reversible from this screen. It does not need a deploy and it does not need us.</p>' +
        '</section>' +
      '</div>' +

      '<section class="band">' + U.bandHead('Providers', '#/settings/providers', 'Manage') +
        '<div class="provs">' + U.DATA.providers.map(function (pv) {
          return '<div class="prov">' +
            '<span class="prov__role">' + U.badge(pv.role === 'Primary' ? 'info' : 'neutral', pv.role) + '</span>' +
            '<span class="prov__name t-h3">' + esc(pv.label) + '</span>' +
            '<span class="prov__meta t-xs t-muted">' + esc(pv.model) + ' · key ending ' + esc(pv.last_four) + '</span>' +
            '<span class="prov__health">' + U.badge('ok', 'Healthy', 'check-circle') + '</span>' +
          '</div>';
        }).join('') + '</div>' +
        '<p class="t-xs t-muted band__note">These are your own provider keys. Calls are billed to your provider account, the key is encrypted before it is stored, and it is never sent to the browser.</p>' +
      '</section>' +

      '<section class="band">' + U.bandHead('Recent spend', null) +
        (rows.length
          ? '<div class="tablewrap"><table class="table"><caption class="u-sr-only">Recent AI spend</caption><thead><tr>' +
            '<th scope="col">When</th><th scope="col">What</th><th scope="col">Provider</th><th scope="col" class="num">Tokens</th><th scope="col" class="num">Cost</th></tr></thead><tbody>' +
            rows.map(function (x) {
              return '<tr' + anno(x.kind) + '><td>' + esc(x.when) + '</td>' +
                '<td>' + (x.run ? '<a href="#/runs/' + x.run + '">' + esc(x.surface) + '</a>' : esc(x.surface)) + '</td>' +
                '<td>' + esc(x.provider) + '<span class="t-muted t-xs"> · ' + esc(x.model) + '</span></td>' +
                '<td class="num t-num">' + (x.tokens ? num(x.tokens) : '—') + '</td>' +
                '<td class="num t-num">' + money(x.cost) + '</td></tr>';
            }).join('') + '</tbody></table></div>'
          : '<p class="band__none t-sm t-muted">Nothing has been spent yet.</p>') +
      '</section>' +
    '</div>';
  };
})();

/* ==========================================================================
   SETTINGS — focus template, six sections
   ========================================================================== */
(function () {
  var U = PO.ui;
  var esc = U.esc, icon = U.icon, money = U.money, plural = U.plural, anno = U.anno, avatar = U.avatar;

  var SECTIONS = [
    { id: 'profile', label: 'Profile', ic: 'user' },
    { id: 'workspace', label: 'Workspace', ic: 'layers' },
    { id: 'members', label: 'People', ic: 'users' },
    { id: 'providers', label: 'AI providers', ic: 'zap' },
    { id: 'notifications', label: 'Notifications', ic: 'bell' },
    { id: 'billing', label: 'Plan and billing', ic: 'wallet' },
    { id: 'security', label: 'Security and data', ic: 'shield-check' }
  ];

  PO.views.settings = function (route) {
    var tab = route.tab || 'profile';
    if (!SECTIONS.filter(function (x) { return x.id === tab; }).length) tab = 'profile';
    var body = ({ profile: secProfile, workspace: secWorkspace, members: secMembers, providers: secProviders,
                  notifications: secNotifications, billing: secBilling, security: secSecurity })[tab]();
    return '<div class="settings">' +
      '<nav class="settings__nav" aria-label="Settings sections">' +
        '<p class="eyebrow settings__navhead">Settings</p>' +
        '<ul role="list">' + SECTIONS.map(function (x) {
          var on = x.id === tab;
          return '<li><a class="snav' + (on ? ' is-on' : '') + '" href="#/settings/' + x.id + '"' + (on ? ' aria-current="page"' : '') + '>' +
            icon(x.ic, 'icon icon--sm') + esc(x.label) + '</a></li>';
        }).join('') + '</ul>' +
      '</nav>' +
      '<div class="settings__body focus">' + body + '</div>' +
    '</div>';
  };

  function head(title, sub) {
    return '<header class="sethead"><h1 class="t-display">' + esc(title) + '</h1>' +
      '<p class="t-sm t-muted">' + esc(sub) + '</p></header>';
  }
  function card(title, note, body, foot) {
    return '<section class="setcard">' +
      '<div class="setcard__head"><h2 class="t-h2">' + esc(title) + '</h2>' +
      (note ? '<p class="t-sm t-muted">' + note + '</p>' : '') + '</div>' +
      '<div class="setcard__body">' + body + '</div>' +
      (foot ? '<div class="setcard__foot">' + foot + '</div>' : '') + '</section>';
  }
  function field(id, label, value, hint, type) {
    return '<div class="field"><label class="field__label" for="' + id + '">' + esc(label) + '</label>' +
      '<input class="input" id="' + id + '" type="' + (type || 'text') + '" value="' + esc(value) + '"' +
      (hint ? ' aria-describedby="' + id + '-h"' : '') + '>' +
      (hint ? '<p class="field__hint t-xs t-muted" id="' + id + '-h">' + hint + '</p>' : '') + '</div>';
  }
  PO.setCard = card; PO.setField = field;

  function secProfile() {
    var u = U.server().user;
    return head('Profile', 'How you appear to everyone else in this workspace.') +
      card('You', null,
        '<div class="profrow">' + avatar(u.id, 'lg') +
          '<div class="profrow__body">' + field('p-name', 'Display name', u.name, 'Shown on every note, approval and version you make.') +
          field('p-email', 'Email', u.email, 'Used to sign in. Changing it asks you to confirm from both addresses.', 'email') + '</div></div>',
        '<button type="button" class="btn btn--primary" data-act="save" data-arg="Profile">Save changes</button>') +
      card('Appearance', 'The interface follows your system by default.',
        '<div class="segset" role="group" aria-label="Theme">' +
          ['system', 'light', 'dark'].map(function (t) {
            var on = (PO.theme() || 'system') === t;
            return '<button type="button" class="seg' + (on ? ' is-on' : '') + '" data-act="theme" data-arg="' + t + '" aria-pressed="' + on + '">' +
              icon(t === 'light' ? 'sun' : t === 'dark' ? 'moon' : 'monitor', 'icon icon--sm') + esc(t.charAt(0).toUpperCase() + t.slice(1)) + '</button>';
          }).join('') + '</div>');
  }

  function secWorkspace() {
    var w = U.DATA.workspace, s = U.server();
    var locked = !s.permissions.can_manage_members;
    return head('Workspace', 'The tenant boundary. Everything inside it is isolated from every other workspace.') +
      card('Name', null, field('w-name', 'Workspace name', w.name, 'Shown in the rail and on every invitation.'),
        locked ? '<p class="t-sm t-muted">' + esc(s.permissions.denied_reason) + '</p>'
               : '<button type="button" class="btn btn--primary" data-act="save" data-arg="Workspace name">Save changes</button>') +
      card('Isolation', 'What "workspace" actually guarantees.',
        '<ul class="ticks">' +
          '<li>' + icon('check', 'icon icon--sm') + 'Every record is filtered by workspace at the database, not only in the application.</li>' +
          '<li>' + icon('check', 'icon icon--sm') + 'Access to one workspace never implies access to another, even for the same person.</li>' +
          '<li>' + icon('check', 'icon icon--sm') + 'Your provider keys, budget and spend belong to this workspace alone.</li>' +
          '<li>' + icon('check', 'icon icon--sm') + 'Support cannot read across workspaces without a separate, logged path.</li>' +
        '</ul>' +
        '<dl class="dl--cols"><div><dt>Created</dt><dd>' + esc(w.created) + '</dd></div>' +
        '<div><dt>People</dt><dd class="t-num">' + U.DATA.members.length + '</dd></div>' +
        '<div><dt>Projects</dt><dd class="t-num">' + U.DATA.projects.length + '</dd></div></dl>') +
      card('Other workspaces', null,
        '<p class="t-sm t-muted"' + anno('planned') + '>You belong to one workspace. Belonging to several, and moving between them, is designed and approved but not built yet — so no switcher is shown rather than one that does nothing.</p>');
  }

  function secMembers() {
    var s = U.server(), can = s.permissions.can_manage_members;
    var ROLE_NOTE = {
      owner: 'Everything, including transferring ownership and deleting the workspace.',
      admin: 'Everything except ownership and deletion. Can approve, set budgets and manage people.',
      member: 'Can create, edit, start production and resume a stopped run. Cannot approve, set budgets or manage people.'
    };
    return head('People', 'Who is in this workspace and what each of them can do.') +
      card('Members', '<span' + anno('planned', 'invitations and role changes') + '>Adding people by email, and changing what they can do, are approved and scheduled.</span>',
        '<ul class="mlist" role="list">' + U.DATA.members.map(function (m) {
          return '<li class="mrow">' + avatar(m.id) +
            '<div class="mrow__body"><p class="mrow__name">' + esc(m.name) +
              (m.id === s.user.id ? ' <span class="t-xs t-muted">(you)</span>' : '') + '</p>' +
              '<p class="t-xs t-muted">' + esc(m.email) + ' · ' + esc(m.craft) + ' · joined ' + esc(m.joined) + '</p></div>' +
            '<span class="mrow__role">' + U.badge(m.role === 'owner' ? 'info' : m.role === 'admin' ? 'warn' : 'neutral', m.role.charAt(0).toUpperCase() + m.role.slice(1)) + '</span>' +
            (can && m.role !== 'owner'
              ? '<button type="button" class="linkbtn" data-act="member-menu" data-arg="' + m.id + '">Change</button>'
              : '') + '</li>';
        }).join('') + '</ul>',
        can ? '<button type="button" class="btn btn--secondary" data-act="invite-open">' + icon('plus', 'icon icon--sm') + 'Invite someone</button>'
            : '<p class="t-sm t-muted">' + esc(s.permissions.denied_reason) + '</p>') +
      card('What each role can do', null,
        '<dl class="roles">' + ['owner', 'admin', 'member'].map(function (r) {
          return '<div><dt>' + esc(r.charAt(0).toUpperCase() + r.slice(1)) + '</dt><dd>' + esc(ROLE_NOTE[r]) + '</dd></div>';
        }).join('') + '</dl>');
  }

  function secProviders() {
    var s = U.server(), can = s.permissions.can_manage_budget;
    return head('AI providers', 'Your own keys, your own provider bill, and a fallback so one outage is not an outage here.') +
      card('Configured keys', '<span' + anno('existing') + '>A key is encrypted before it is stored and is never sent back to the browser. Only its last four characters are ever shown again.</span>',
        '<ul class="mlist" role="list">' + U.DATA.providers.map(function (p) {
          return '<li class="mrow"><span class="mrow__ic">' + icon('zap', 'icon icon--lg') + '</span>' +
            '<div class="mrow__body"><p class="mrow__name">' + esc(p.label) + ' <span class="t-xs t-muted">· ' + esc(p.role) + '</span></p>' +
            '<p class="t-xs t-muted">Key ending ' + esc(p.last_four) + ' · added ' + esc(p.added) + ' · ' + esc(p.model) + '</p></div>' +
            '<span class="mrow__role">' + U.badge('ok', 'Healthy', 'check-circle') + '</span>' +
            (can ? '<button type="button" class="linkbtn" data-act="provider-open" data-arg="' + p.id + '">Replace</button>' : '') + '</li>';
        }).join('') + '</ul>',
        can ? '<button type="button" class="btn btn--secondary" data-act="provider-open" data-arg="new">' + icon('plus', 'icon icon--sm') + 'Add a provider</button>'
            : '<p class="t-sm t-muted">' + esc(s.permissions.denied_reason) + '</p>') +
      card('Fallback order', 'A critical workflow never depends on one provider being up.',
        '<ol class="order" role="list">' + U.DATA.providers.map(function (p, i) {
          return '<li><span class="order__n">' + (i + 1) + '</span><span>' + esc(p.label) + ' · ' + esc(p.model) + '</span></li>';
        }).join('') + '</ol>' +
        '<p class="t-xs t-muted">At most three attempts each, then the run stops and tells you. It never keeps trying.</p>');
  }

  function secNotifications() {
    var ROWS = [
      { id: 'approval', label: 'A step needs my approval', note: 'The one that stops production until you answer.', inapp: true, email: true },
      { id: 'review', label: 'Work is sent to me for review', note: '', inapp: true, email: true },
      { id: 'note', label: 'Someone leaves a note on my work', note: '', inapp: true, email: false },
      { id: 'failed', label: 'A run stops', note: 'Including why, and whether anything was billed.', inapp: true, email: true },
      { id: 'budget', label: 'Spend passes 80% of the ceiling', note: '', inapp: true, email: true },
      { id: 'done', label: 'A run finishes', note: '', inapp: true, email: false }
    ];
    return head('Notifications', 'What reaches you, and where.') +
      card('Per event', '<span' + anno('planned') + '>The notification domain is approved and scheduled. This is what it will control.</span>',
        '<div class="tablewrap"><table class="table"><thead><tr><th scope="col">Tell me when</th>' +
        '<th scope="col" class="num">In app</th><th scope="col" class="num">Email</th></tr></thead><tbody>' +
        ROWS.map(function (r) {
          return '<tr><td><p>' + esc(r.label) + '</p>' + (r.note ? '<p class="t-xs t-muted">' + esc(r.note) + '</p>' : '') + '</td>' +
            '<td class="num">' + toggle('n-' + r.id + '-a', r.inapp, r.label + ' in app') + '</td>' +
            '<td class="num">' + toggle('n-' + r.id + '-e', r.email, r.label + ' by email') + '</td></tr>';
        }).join('') + '</tbody></table></div>',
        '<button type="button" class="btn btn--primary" data-act="save" data-arg="Notification preferences">Save changes</button>') +
      card('Quiet hours', null,
        '<p class="t-sm t-muted">Between 20:00 and 08:00 nothing but an approval that is blocking production will reach you by email.</p>' +
        toggle('n-quiet', true, 'Quiet hours'));
  }
  function toggle(id, on, label) {
    return '<button type="button" class="switch" id="' + id + '" data-act="toggle" aria-pressed="' + !!on + '">' +
      '<span class="switch__track" aria-hidden="true"><span class="switch__thumb"></span></span>' +
      '<span class="u-sr-only">' + esc(label) + '</span></button>';
  }

  function secBilling() {
    var b = U.budgetView(), s = U.server(), can = s.permissions.can_manage_budget;
    return head('Plan and billing', 'What you pay us, and what you pay your AI providers. They are not the same bill.') +
      card('Your plan', '<span' + anno('planned') + '>Subscriptions and invoices are the last thing on the plan, deliberately: the product has to be worth paying for first.</span>',
        '<div class="planrow"><div><p class="t-h2">Studio</p>' +
        '<p class="t-sm t-muted">Unlimited projects, four seats, your own provider keys.</p></div>' +
        '<p class="planrow__price t-display">$48<span class="t-sm t-muted">/month</span></p></div>' +
        '<p class="t-xs t-muted">Renews 4 September. Cancelling takes effect at the end of the period and is available right here — never by writing to us.</p>',
        '<button type="button" class="btn btn--secondary" data-act="save" data-arg="Plan change">Change plan</button>' +
        '<button type="button" class="btn btn--ghost" data-act="cancel-plan">Cancel plan</button>') +
      card('AI spend ceiling', '<span' + anno('existing') + '>This is your provider spend, billed to your own account. We do not mark it up and we do not take a share.</span>',
        '<div class="field"><span class="field__label">Monthly ceiling</span>' +
        '<p class="ceiling t-display t-num">' + money(b.limit) + '</p>' +
        '<p class="field__hint t-xs t-muted">' + money(b.spent) + ' used this period. When the ceiling is reached, new work stops and says so.</p></div>',
        can ? '<button type="button" class="btn btn--secondary" data-act="ceiling-open">Change the ceiling</button>' +
              '<a class="btn btn--ghost" href="#/spend">See every charge</a>'
            : '<p class="t-sm t-muted">' + esc(s.permissions.denied_reason) + '</p>') +
      card('Invoices', null,
        '<div class="tablewrap"><table class="table"><thead><tr><th scope="col">Date</th><th scope="col">Period</th><th scope="col" class="num">Amount</th><th scope="col"></th></tr></thead><tbody>' +
        [['4 Aug 2026', 'Aug 2026', 48], ['4 Jul 2026', 'Jul 2026', 48], ['4 Jun 2026', 'Jun 2026', 48]].map(function (r) {
          return '<tr><td>' + esc(r[0]) + '</td><td>' + esc(r[1]) + '</td><td class="num t-num">' + money(r[2]) + '</td>' +
            '<td class="num"><button type="button" class="linkbtn" data-act="invoice" data-arg="' + esc(r[1]) + '">Receipt</button></td></tr>';
        }).join('') + '</tbody></table></div>');
  }

  function secSecurity() {
    var s = U.server(), owner = s.permissions.role === 'owner';
    return head('Security and data', 'It is your data. These are the controls that make that sentence true.') +
      card('Sign-in', null,
        '<ul class="mlist" role="list">' +
          '<li class="mrow"><span class="mrow__ic">' + icon('lock', 'icon icon--lg') + '</span>' +
          '<div class="mrow__body"><p class="mrow__name">Password</p><p class="t-xs t-muted">Last changed 2 June 2026</p></div>' +
          '<button type="button" class="linkbtn" data-act="save" data-arg="Password change">Change</button></li>' +
          '<li class="mrow"><span class="mrow__ic">' + icon('shield-check', 'icon icon--lg') + '</span>' +
          '<div class="mrow__body"><p class="mrow__name">Two-step verification</p><p class="t-xs t-muted">Not enabled</p></div>' +
          '<button type="button" class="linkbtn" data-act="save" data-arg="Two-step verification">Set up</button></li>' +
        '</ul>') +
      card('Your data', '<span' + anno('existing', 'export and erasure exist in the API') + '>Export takes everything. Deletion means deletion, with two stated exceptions.</span>',
        '<ul class="ticks">' +
          '<li>' + icon('check', 'icon icon--sm') + 'An export contains every record this workspace holds, in a format you can read without us.</li>' +
          '<li>' + icon('check', 'icon icon--sm') + 'A deletion request completes across every live system within 30 days, and you can see its progress.</li>' +
          '<li>' + icon('alert-circle', 'icon icon--sm') + '<strong>Encrypted backups age out</strong> on their own schedule rather than being individually purged. That window is short, and it is a stated exception rather than a quiet one.</li>' +
          '<li>' + icon('alert-circle', 'icon icon--sm') + '<strong>The audit trail is kept</strong> on its own schedule. It exists to outlive what it records, which is the whole point of having one.</li>' +
        '</ul>',
        '<button type="button" class="btn btn--secondary" data-act="export-open">Export everything</button>') +
      card('Danger', null,
        '<div class="danger">' +
          '<div><p class="t-h3">Delete this workspace</p>' +
          '<p class="t-sm t-muted">Removes every project, deliverable, version, note and run. Four people lose access immediately. This cannot be undone.</p></div>' +
          (owner
            ? '<button type="button" class="btn btn--danger" data-act="delete-ws">Delete workspace…</button>'
            : '<p class="t-sm t-muted">Only the owner can delete a workspace.</p>') +
        '</div>');
  }
})();

/* ==========================================================================
   AUTHENTICATION AND FIRST USE — focus template, no application chrome
   Nothing here is submitted anywhere. There is no network in this file.
   ========================================================================== */
(function () {
  var U = PO.ui, C = PO.CAMPAIGN;
  var esc = U.esc, icon = U.icon, frame = U.frame, money = U.money;

  function gate(title, sub, body, foot) {
    return '<div class="gate">' +
      '<div class="gate__panel">' +
        '<a class="gate__brand" href="#/dashboard"><span class="mark" aria-hidden="true"></span>Project<b>One</b></a>' +
        '<h1 class="gate__title t-display">' + esc(title) + '</h1>' +
        '<p class="gate__sub t-sm t-muted">' + esc(sub) + '</p>' +
        body +
        (foot ? '<div class="gate__foot">' + foot + '</div>' : '') +
      '</div>' +
      '<aside class="gate__art" aria-hidden="true">' +
        frame({ scene: 'sear', aspect: '16x9', lockup: 'title', lockupTitle: C.brand, lockupEyebrow: C.season }, { aspect: '16x9', cls: 'frame--gate' }) +
        '<p class="gate__quote t-display">One idea. <em>The whole production.</em></p>' +
      '</aside>' +
    '</div>';
  }

  PO.views.signin = function () {
    return gate('Welcome back', 'Sign in to Avery Kim Studio.',
      '<form class="gate__form" data-act="signin-submit" novalidate>' +
        PO.setField('si-email', 'Email', 'avery@averykim.studio', null, 'email') +
        '<div class="field"><label class="field__label" for="si-pw">Password</label>' +
        '<input class="input" id="si-pw" type="password" value="prototype" autocomplete="off" aria-describedby="si-pw-h">' +
        '<p class="field__hint t-xs t-muted" id="si-pw-h">This is a design prototype. Nothing is sent anywhere and no account exists.</p></div>' +
        '<button type="submit" class="btn btn--primary btn--lg btn--block" data-act="signin-submit">Sign in</button>' +
      '</form>',
      '<p class="t-sm t-muted">Invited to a workspace? <a href="#/join">Accept the invitation</a>.</p>');
  };

  PO.views.join = function () {
    return gate('Noor invited you to Avery Kim Studio', 'You will join as an Editor. That means you can create, edit and start production — approving work and changing budgets stay with an owner or admin.',
      '<form class="gate__form" data-act="signin-submit" novalidate>' +
        PO.setField('j-name', 'Your name', 'Diego Salas') +
        PO.setField('j-email', 'Email', 'diego@averykim.studio', null, 'email') +
        '<div class="field"><label class="field__label" for="j-pw">Choose a password</label>' +
        '<input class="input" id="j-pw" type="password" value="" autocomplete="off" aria-describedby="j-pw-h">' +
        '<p class="field__hint t-xs t-muted" id="j-pw-h">At least twelve characters. This is a design prototype — nothing is sent anywhere.</p></div>' +
        '<button type="submit" class="btn btn--primary btn--lg btn--block" data-act="signin-submit">Join the workspace</button>' +
      '</form>',
      '<p class="t-sm t-muted">Already have an account? <a href="#/signin">Sign in</a>.</p>');
  };

  /* ------------------------------------------------------------- first use */
  var STEPS = [
    { id: 1, title: 'Name the workspace', sub: 'A workspace is the boundary. Everything inside it — projects, keys, spend, people — is isolated from every other one.' },
    { id: 2, title: 'Connect a provider', sub: 'ProjectOne uses your own AI keys, so the provider bills you directly and we never mark it up. A second provider is a fallback, not a requirement.' },
    { id: 3, title: 'Set a ceiling', sub: 'A monthly limit ProjectOne will not spend past. You can move it whenever you like — the point is that there is one from the first minute.' }
  ];
  PO.welcomeStep = 1;

  PO.views.welcome = function () {
    var n = PO.welcomeStep;
    var s = STEPS[n - 1];
    var body =
      n === 1 ? PO.setField('ob-ws', 'Workspace name', 'Avery Kim Studio', 'You can change this at any time.')
      : n === 2 ? '<div class="obprov">' +
          ['Anthropic', 'OpenAI'].map(function (p, i) {
            return '<div class="obprov__row"><span class="obprov__ic">' + icon('zap', 'icon icon--lg') + '</span>' +
              '<div><p class="mrow__name">' + esc(p) + '</p><p class="t-xs t-muted">' + (i ? 'Optional — used only if the first is unavailable.' : 'Your primary provider.') + '</p></div>' +
              '<button type="button" class="btn btn--secondary btn--sm" data-act="provider-open" data-arg="' + p.toLowerCase() + '">' + (i ? 'Add' : 'Connect') + '</button></div>';
          }).join('') +
          '<p class="t-xs t-muted">A key is encrypted before it is stored and is never sent back to the browser.</p></div>'
      : '<div class="obceil">' +
          '<div class="segset" role="group" aria-label="Monthly ceiling">' +
            ['$100', '$500', '$2,000'].map(function (v, i) {
              return '<button type="button" class="seg' + (i === 2 ? ' is-on' : '') + '" data-act="noop" aria-pressed="' + (i === 2) + '">' + esc(v) + '</button>';
            }).join('') + '</div>' +
          '<p class="t-sm t-muted">Whatever you pick, three things are already true: every run has a hard step and time ceiling, every provider call is capped at three attempts, and a breaker trips on repeated failure. The ceiling is the outer bound, not the only one.</p></div>';

    return '<div class="gate gate--wizard">' +
      '<div class="gate__panel">' +
        '<a class="gate__brand" href="#/dashboard"><span class="mark" aria-hidden="true"></span>Project<b>One</b></a>' +
        '<ol class="wsteps" role="list">' + STEPS.map(function (x) {
          return '<li class="wstep' + (x.id === n ? ' is-on' : x.id < n ? ' is-done' : '') + '">' +
            '<span class="wstep__n">' + (x.id < n ? icon('check', 'icon icon--sm') : x.id) + '</span>' +
            '<span class="wstep__label t-xs">' + esc(x.title) + '</span></li>';
        }).join('') + '</ol>' +
        '<h1 class="gate__title t-display">' + esc(s.title) + '</h1>' +
        '<p class="gate__sub t-sm t-muted">' + esc(s.sub) + '</p>' +
        '<div class="gate__form">' + body + '</div>' +
        '<div class="gate__foot gate__foot--row">' +
          (n > 1 ? '<button type="button" class="btn btn--ghost" data-act="wiz" data-arg="' + (n - 1) + '">Back</button>' : '<span></span>') +
          (n < 3
            ? '<button type="button" class="btn btn--primary" data-act="wiz" data-arg="' + (n + 1) + '">Continue' + icon('arrow-right', 'icon icon--sm') + '</button>'
            : '<button type="button" class="btn btn--primary" data-act="wiz-done">Start creating' + icon('arrow-right', 'icon icon--sm') + '</button>') +
        '</div>' +
      '</div>' +
      '<aside class="gate__art" aria-hidden="true">' +
        frame({ scene: 'flame', aspect: '16x9', lockup: 'end' }, { aspect: '16x9', cls: 'frame--gate' }) +
        '<p class="gate__quote t-display">Nothing runs until you say so.</p>' +
      '</aside>' +
    '</div>';
  };

  /* ------------------------------------------------------------- not found */
  PO.views.notfound = function (route) {
    var what = route.name === 'project' ? 'project' : route.name === 'run' ? 'run' : route.name === 'review' ? 'deliverable' : 'page';
    return '<div class="focus">' +
      U.empty('alert-circle', 'We could not find that ' + what,
        'It may have been deleted, or it may belong to a workspace you are not in. Those two look identical here on purpose — telling them apart would leak whether someone else’s record exists.',
        '<a class="btn btn--primary" href="#/dashboard">Back to Home</a>' +
        '<button type="button" class="btn btn--secondary" data-act="palette">Search everything</button>', 'h1') +
      '</div>';
  };

  /* ------------------------------------------------------------- skeletons
     A loading state is a shape, not a spinner: the same layout, greyed, so
     nothing jumps when the content lands. */
  PO.ui.skeletonFor = function (name) {
    var s = U.skel;
    var block = function (n, w, h) { var o = ''; for (var i = 0; i < n; i++) o += s(w, h); return o; };
    if (name === 'dashboard') {
      return '<div class="cockpit is-loading" role="status" aria-busy="true"><h1 class="u-sr-only">Loading Home</h1>' +
        '<div class="cockpit__head"><div style="flex:1 1 100%">' + s('18rem', '0.75rem') + s('26rem', '2.25rem') + '</div></div>' +
        '<div class="cockpit__work"><div class="composer">' + s('100%', '2.25rem') + s('70%', '0.75rem') + s('100%', '7rem') + s('100%', '2rem') + '</div>' +
        '<div class="outcome">' + s('40%', '0.75rem') + s('100%', '10rem') + s('100%', '3rem') + '</div></div>' +
        '<div class="cockpit__zones">' + block(3, '100%', '6rem') + '</div></div>';
    }
    return '<div class="focus" role="status" aria-busy="true"><h1 class="u-sr-only">Loading this screen</h1>' +
      s('14rem', '2rem') + s('100%', '1rem') + s('86%', '1rem') +
      '<div class="skelgrid">' + block(6, '100%', '8rem') + '</div></div>';
  };
})();

/* ==========================================================================
   OVERLAYS — popovers, drawers, modals

   Rules that hold for every one of them:
   - Escape closes it and focus returns to whatever opened it.
   - A destructive or spending confirmation focuses the safe choice first and
     ignores a backdrop click, because a mis-click should never spend money.
   - Autofocus lands on the content, never on the footer's Close button.
   ========================================================================== */
(function () {
  var U = PO.ui, C = PO.CAMPAIGN, M = PO.modes, c = PO.composer;
  var esc = U.esc, icon = U.icon, money = U.money, plural = U.plural, frame = U.frame, anno = U.anno, avatar = U.avatar;

  function head(title, id) {
    return '<header class="overlay__head"><h2 class="t-h2" id="' + id + '">' + esc(title) + '</h2>' +
      '<button type="button" class="iconbtn" data-act="close" data-arg="' + (id === 'modal-title' ? 'modal' : 'drawer') + '" aria-label="Close">' +
      icon('x', 'icon icon--lg') + '</button></header>';
  }
  function foot(html) { return '<footer class="overlay__foot">' + html + '</footer>'; }
  PO.oHead = head; PO.oFoot = foot;

  /* ---------------------------------------------------------------- popovers */
  PO.pop = {
    ws: function () {
      var s = U.server();
      return '<div class="popover__head"><p class="t-h3">' + esc(U.DATA.workspace.name) + '</p>' +
        '<p class="t-xs t-muted">Your role: ' + esc(s.permissions.role.charAt(0).toUpperCase() + s.permissions.role.slice(1)) + '</p></div>' +
        '<a class="menuitem" href="#/settings/workspace" data-act="close-popover">' + icon('layers', 'icon icon--sm') + 'Workspace settings</a>' +
        '<a class="menuitem" href="#/settings/members" data-act="close-popover">' + icon('users', 'icon icon--sm') + 'People and roles</a>' +
        '<a class="menuitem" href="#/settings/billing" data-act="close-popover">' + icon('wallet', 'icon icon--sm') + 'Plan and billing</a>' +
        '<p class="popover__foot t-xs t-muted"' + anno('planned') + '>You belong to one workspace. Moving between several is designed and approved, and not built yet.</p>';
    },
    user: function () {
      var u = U.server().user;
      return '<div class="popover__head"><p class="t-h3">' + esc(u.name) + '</p><p class="t-xs t-muted">' + esc(u.email) + '</p></div>' +
        '<a class="menuitem" href="#/settings/profile" data-act="close-popover">' + icon('user', 'icon icon--sm') + 'Profile</a>' +
        '<a class="menuitem" href="#/settings/security" data-act="close-popover">' + icon('shield-check', 'icon icon--sm') + 'Security and data</a>' +
        '<a class="menuitem" href="#/spec" data-act="close-popover">' + icon('grid', 'icon icon--sm') + 'Design components</a>' +
        '<a class="menuitem menuitem--danger" href="#/signin" data-act="close-popover">' + icon('log-out', 'icon icon--sm') + 'Sign out</a>';
    },
    theme: function () {
      var cur = PO.theme() || 'system';
      return ['system', 'light', 'dark'].map(function (t) {
        return '<button type="button" class="menuitem' + (cur === t ? ' is-on' : '') + '" data-act="theme" data-arg="' + t + '" aria-pressed="' + (cur === t) + '">' +
          icon(t === 'light' ? 'sun' : t === 'dark' ? 'moon' : 'monitor', 'icon icon--sm') +
          esc(t === 'system' ? 'Match my system' : t.charAt(0).toUpperCase() + t.slice(1)) +
          (cur === t ? icon('check', 'icon icon--sm menuitem__tick') : '') + '</button>';
      }).join('');
    },
    notif: function () {
      var items = U.attentionItems();
      if (!items.length) return '<div class="popover__head"><p class="t-h3">Nothing needs you</p></div>' +
        '<p class="popover__foot t-sm t-muted">When a step needs approving, work is sent to you, or a run stops, it appears here first.</p>';
      return '<div class="popover__head"><p class="t-h3">' + plural(items.length, 'thing') + ' need you</p></div>' +
        items.slice(0, 5).map(function (i) {
          return '<a class="menuitem menuitem--stack" href="' + i.href + '" data-act="close-popover">' +
            '<span class="menuitem__title">' + esc(i.title) + '</span>' +
            '<span class="t-xs t-muted">' + esc(i.why) + '</span></a>';
        }).join('') +
        '<a class="menuitem menuitem--foot" href="#/runs" data-act="close-popover">See everything' + icon('chevron-right', 'icon icon--sm') + '</a>';
    },
    /* One value, its alternatives, and the sentence that keeps it from
       reading as a commitment. Multi-select stays open while you tick; single
       select closes on the choice, because the choice is the whole errand. */
    ess: function (key) {
      var m = M.modeById(c.mode), fd = M.essField(c.mode, key);
      if (!fd) return '';
      var cur = M.essValue(c.mode, key);
      if (!fd.multi) {
        return '<div class="popover__head"><p class="t-h3">' + esc(fd.label) + '</p>' +
          '<p class="t-xs t-muted">For ' + esc(m.full.toLowerCase()) + '</p></div>' +
          fd.opts.map(function (opt) {
            var on = opt === cur;
            return '<button type="button" class="menuitem' + (on ? ' is-on' : '') + '" data-act="ess-set" data-arg="' + esc(key) + '|' + esc(opt) + '" aria-pressed="' + on + '">' +
              esc(opt) + (on ? icon('check', 'icon icon--sm menuitem__tick') : '') + '</button>';
          }).join('') +
          '<p class="popover__foot t-xs t-muted">Nothing here is locked in. The plan restates all four before anything runs, and you can still stop there.</p>';
      }
      var paid = c.mode === 'campaign';
      return '<div class="popover__head"><p class="t-h3">' + esc(fd.label) + '</p>' +
        '<p class="t-xs t-muted">' + (paid ? 'Each one adds its own placements — and its own cost — to the plan.' : 'Where this is meant to land.') + '</p></div>' +
        fd.opts.map(function (id) {
          var x = M.chanById(id), on = cur.indexOf(id) !== -1;
          return '<button type="button" class="menuitem menuitem--stack' + (on ? ' is-on' : '') + '" data-act="ess-toggle" data-arg="' + esc(key) + '|' + esc(id) + '" aria-pressed="' + on + '">' +
            '<span class="menuitem__title">' + esc(x ? x.label : id) + (on ? icon('check', 'icon icon--sm menuitem__tick') : '') + '</span>' +
            (paid && x && x.paid ? '<span class="t-xs t-muted">' + esc(x.paid) + '</span>' : '') + '</button>';
        }).join('') +
        '<p class="popover__foot t-xs t-muted">' +
        (paid ? 'These are advertisements you are making. ProjectOne does not buy media or place them for you.'
              : 'Nothing is published from here. Destinations describe the format, not an account.') + '</p>';
    },
    dest: function () {
      return '<div class="popover__head"><p class="t-h3">Where is this going?</p></div>' +
        M.DESTINATIONS.map(function (dst) {
          var on = dst.id === c.dest;
          return '<button type="button" class="menuitem menuitem--stack' + (on ? ' is-on' : '') + '" data-act="dest" data-arg="' + dst.id + '" aria-pressed="' + on + '">' +
            '<span class="menuitem__title">' + esc(dst.label) + (on ? icon('check', 'icon icon--sm menuitem__tick') : '') + '</span>' +
            '<span class="t-xs t-muted">' + esc(dst.note) + '</span></button>';
        }).join('') +
        '<p class="popover__foot t-xs t-muted">The destination changes what gets made and what shape it is in. It never publishes anything.</p>';
    }
  };

  /* ------------------------------------------------------------ nav drawer */
  PO.navDrawer = function () {
    return '<div class="navdrawer__inner">' +
      '<header class="overlay__head"><span class="brand"><span class="mark" aria-hidden="true"></span>Project<b>One</b></span>' +
      '<button type="button" class="iconbtn" data-act="close" data-arg="navdrawer" aria-label="Close navigation">' + icon('x', 'icon icon--lg') + '</button></header>' +
      '<nav aria-label="Primary"><ul class="rail__group" id="navdrawer-nav" role="list"></ul></nav>' +
      '</div>';
  };

  /* ------------------------------------------------------- pickers and forms */
  PO.modal = {
    ref: function () {
      return head('Attach a reference', 'modal-title') +
        '<div class="overlay__body">' +
          '<p class="t-sm t-muted">Something already in this workspace. ProjectOne reads it and works from it.</p>' +
          '<ul class="picklist" role="list">' + M.REF_LIBRARY.map(function (r, i) {
            var on = c.ref === r.id;
            return '<li><button type="button" class="pick' + (on ? ' is-on' : '') + '" data-act="ref-pick" data-arg="' + r.id + '"' +
              (i === 0 ? ' data-autofocus' : '') + ' aria-pressed="' + on + '">' +
              '<span class="pick__ic">' + icon(r.kind, 'icon icon--lg') + '</span>' +
              '<span class="pick__body"><span class="pick__name">' + esc(r.name) + '</span>' +
              '<span class="t-xs t-muted">' + esc(r.meta) + '</span></span>' +
              (on ? icon('check', 'icon') : '') + '</button></li>';
          }).join('') + '</ul>' +
          '<p class="t-xs t-muted">Uploading is part of the real product. In this prototype nothing is read from your machine and nothing leaves the page.</p>' +
        '</div>' + foot('<button type="button" class="btn btn--secondary" data-act="close" data-arg="modal">Done</button>');
    },
    ctx: function () {
      return head('Use a project as context', 'modal-title') +
        '<div class="overlay__body">' +
          '<p class="t-sm t-muted">The new work inherits that project’s audience, voice and existing deliverables.</p>' +
          '<ul class="picklist" role="list">' + U.projects().map(function (p, i) {
            var on = c.project === p.id;
            return '<li><button type="button" class="pick' + (on ? ' is-on' : '') + '" data-act="ctx-pick" data-arg="' + p.id + '"' +
              (i === 0 ? ' data-autofocus' : '') + ' aria-pressed="' + on + '">' +
              '<span class="pick__art">' + frame({ scene: p.scene, aspect: '16x9' }, { aspect: '16x9', detail: 'thumb' }) + '</span>' +
              '<span class="pick__body"><span class="pick__name">' + esc(p.name) + '</span>' +
              '<span class="t-xs t-muted">' + esc(p.brief.split('.')[0]) + '.</span></span>' +
              (on ? icon('check', 'icon') : '') + '</button></li>';
          }).join('') + '</ul>' +
        '</div>' + foot('<button type="button" class="btn btn--secondary" data-act="close" data-arg="modal">Done</button>');
    },
    add: function () {
      var m = M.modeById(c.plan ? c.plan.mode : c.mode);
      var p = c.plan;
      var chans = M.essField(m.id, 'channels') ? M.essValue(m.id, 'channels', p ? p.ess : c.ess) : null;
      var gone = m.outputs.filter(function (o) {
        if (!(p ? p.removed : c.removed)[o.id]) return false;
        /* Not offered here if its channel is off: it is not missing from the
           plan, it was never on it. The channel itself is where it comes back. */
        if (!o.channel) return true;
        return chans && (o.channel === '*' ? chans.length > 0 : chans.indexOf(o.channel) !== -1);
      });
      return head('Add something back', 'modal-title') +
        '<div class="overlay__body">' +
          (gone.length
            ? '<ul class="picklist" role="list">' + gone.map(function (o, i) {
                return '<li><button type="button" class="pick" data-act="deliv-add" data-arg="' + o.id + '"' + (i === 0 ? ' data-autofocus' : '') + '>' +
                  '<span class="pick__art">' + frame(M.artOf(o, m), { aspect: o.art.aspect || '16x9', detail: 'thumb' }) + '</span>' +
                  '<span class="pick__body"><span class="pick__name">' + esc(o.name) + '</span>' +
                  '<span class="t-xs t-muted">' + esc(o.ai) + '</span></span>' +
                  '<span class="t-sm t-num">' + money(o.low * o.n) + '–' + money(o.high * o.n) + '</span></button></li>';
              }).join('') + '</ul>'
            : '<p class="t-sm t-muted" data-autofocus tabindex="-1">Nothing has been removed from this plan. Everything the workflow produces is still on it.</p>') +
        '</div>' + foot('<button type="button" class="btn btn--secondary" data-act="close" data-arg="modal">Done</button>');
    },
    start: function () {
      var p = c.plan; if (!p) return '';
      var m = M.modeById(p.mode);
      var list = M.outputsFor(p.mode, p.removed, p.ess);
      var present = {}; list.forEach(function (o) { present[o.id] = true; });
      var t = M.totals(list.filter(function (o) { return PO.plan.statusOf(o, present) === 'ready'; }));
      var b = U.budgetView();
      return head('Start production', 'modal-title') +
        '<div class="overlay__body">' +
          '<p class="t-sm">This starts the planning step and stops at the first approval. Nothing is published anywhere.</p>' +
          '<dl class="confirm">' +
            '<div><dt>Estimated cost</dt><dd class="t-num">' + money(t.low) + ' – ' + money(t.high) + '</dd></div>' +
            '<div><dt>Left this month</dt><dd class="t-num">' + money(b.remaining) + ' of ' + money(b.limit) + '</dd></div>' +
            '<div><dt>Stops for you</dt><dd class="t-num">' + plural(t.gates, 'time') + '</dd></div>' +
          '</dl>' +
          '<p class="t-xs t-muted">An estimate drawn from ' + esc(U.DATA.estimate.basis) + ' — not a quote. You are billed for what is actually used, per step, as each one completes.</p>' +
        '</div>' +
        foot('<button type="button" class="btn btn--secondary" data-act="close" data-arg="modal" data-autofocus>Not yet</button>' +
             '<button type="button" class="btn btn--primary" data-act="start-confirm">Start production</button>');
    },
    resume: function (runId) {
      return head('Resume this run', 'modal-title') +
        '<div class="overlay__body">' +
          '<p class="t-sm">Production picks up from the last step that completed. Everything before it is kept.</p>' +
          '<div class="warnbox">' + icon('alert-triangle', 'icon icon--lg') +
            '<p class="t-sm"><strong>The interrupted step may run against the provider a second time.</strong> If the provider was already called and billed before the interruption, that charge has happened and nothing here can undo it. ProjectOne treats provider work as happening <em>at least once</em>, never exactly once — which is exactly why resuming is a decision you make rather than something that happens on its own.</p></div>' +
          '<p class="t-xs t-muted">Estimated for the remaining steps: ' + money(0.04) + ' – ' + money(0.14) + '.</p>' +
        '</div>' +
        foot('<button type="button" class="btn btn--secondary" data-act="close" data-arg="modal" data-autofocus>Not now</button>' +
             '<button type="button" class="btn btn--primary" data-act="resume-confirm" data-arg="' + runId + '">Resume production</button>');
    },
    regen: function (assetId) {
      var a = U.assetById(assetId) || {};
      return head('Regenerate', 'modal-title') +
        '<div class="overlay__body">' +
          '<p class="t-sm">This calls a provider and costs money. Editing by hand does not.</p>' +
          '<dl class="confirm">' +
            '<div><dt>Estimated cost</dt><dd class="t-num">$0.18 – $0.44</dd></div>' +
            '<div><dt>Replaces</dt><dd>' + esc(a.name || 'this deliverable') + ' at version ' + (a.version || 1) + '</dd></div>' +
            '<div><dt>Also affects</dt><dd>Captions and 2 derivatives, which are marked for a re-cut</dd></div>' +
            '<div><dt>Approval</dt><dd>Yes — a new version of a master is gated</dd></div>' +
          '</dl>' +
          '<p class="t-xs t-muted">The current version is kept. Regenerating adds v' + ((a.version || 1) + 1) + ' beside it rather than overwriting it.</p>' +
        '</div>' +
        foot('<button type="button" class="btn btn--secondary" data-act="close" data-arg="modal" data-autofocus>Cancel</button>' +
             '<button type="button" class="btn btn--primary" data-act="regen-confirm" data-arg="' + assetId + '">Regenerate</button>');
    },
    archive: function (projectId) {
      var p = U.projectById(projectId) || {};
      return head('Archive this project?', 'modal-title') +
        '<div class="overlay__body">' +
          '<p class="t-sm"><strong>' + esc(p.name) + '</strong> stops appearing in your live work and stays listed under Archived. Nothing is deleted — every deliverable, version and note is kept.</p>' +
          '<p class="t-sm t-muted">Archiving is not deleting. You archive work you want the record of; you delete work that was a mistake.</p>' +
        '</div>' +
        foot('<button type="button" class="btn btn--secondary" data-act="close" data-arg="modal" data-autofocus>Keep it live</button>' +
             '<button type="button" class="btn btn--danger" data-act="archive-confirm" data-arg="' + projectId + '">Archive project</button>');
    },
    invite: function () {
      return head('Invite someone', 'modal-title') +
        '<div class="overlay__body">' +
          '<div class="field"><label class="field__label" for="inv-email">Email</label>' +
          '<input class="input" id="inv-email" type="email" placeholder="name@studio.com" data-autofocus></div>' +
          '<fieldset class="fieldset"><legend class="field__label">Role</legend>' +
            [['admin', 'Admin', 'Everything except ownership and deleting the workspace.'],
             ['member', 'Member', 'Create, edit, start production, resume a stopped run. Cannot approve or change budgets.']].map(function (r, i) {
              return '<label class="radio"><input type="radio" name="inv-role" value="' + r[0] + '"' + (i ? ' checked' : '') + '>' +
                '<span><span class="radio__label">' + esc(r[1]) + '</span><span class="t-xs t-muted">' + esc(r[2]) + '</span></span></label>';
            }).join('') + '</fieldset>' +
          '<p class="t-xs t-muted">They receive one email. Nothing is shared with them until they accept.</p>' +
        '</div>' +
        foot('<button type="button" class="btn btn--secondary" data-act="close" data-arg="modal">Cancel</button>' +
             '<button type="button" class="btn btn--primary" data-act="invite-send">Send invitation</button>');
    },
    provider: function (id) {
      var known = U.DATA.providers.filter(function (p) { return p.id === id; })[0];
      return head(known ? 'Replace the ' + known.label + ' key' : 'Add a provider', 'modal-title') +
        '<div class="overlay__body">' +
          (known ? '' : '<div class="field"><label class="field__label" for="pk-prov">Provider</label>' +
            '<select class="input" id="pk-prov"><option>Anthropic</option><option>OpenAI</option></select></div>') +
          '<div class="field"><label class="field__label" for="pk-key">API key</label>' +
          '<input class="input t-mono" id="pk-key" type="password" placeholder="Paste your key" autocomplete="off" data-autofocus aria-describedby="pk-h">' +
          '<p class="field__hint t-xs t-muted" id="pk-h">Encrypted before it is stored, and never sent back to the browser. Only the last four characters are ever shown again.</p></div>' +
          (known ? '<p class="t-sm t-muted">Replacing it takes effect on the next call. The current key stops working immediately.</p>' : '') +
          '<p class="t-xs t-muted">This is a design prototype. Do not paste a real key — nothing here stores or transmits anything.</p>' +
        '</div>' +
        foot('<button type="button" class="btn btn--secondary" data-act="close" data-arg="modal">Cancel</button>' +
             '<button type="button" class="btn btn--primary" data-act="provider-save">Save key</button>');
    },
    ceiling: function () {
      var b = U.budgetView();
      return head('Monthly AI ceiling', 'modal-title') +
        '<div class="overlay__body">' +
          '<div class="field"><label class="field__label" for="cl-amt">Ceiling</label>' +
          '<input class="input t-num" id="cl-amt" type="text" value="' + money(b.limit) + '" data-autofocus aria-describedby="cl-h">' +
          '<p class="field__hint t-xs t-muted" id="cl-h">' + money(b.spent) + ' used this period. Setting a ceiling below what is already used stops new work immediately.</p></div>' +
          '<p class="t-sm t-muted">This is your provider spend, on your own key. It is not a ProjectOne charge and we take no share of it.</p>' +
        '</div>' +
        foot('<button type="button" class="btn btn--secondary" data-act="close" data-arg="modal">Cancel</button>' +
             '<button type="button" class="btn btn--primary" data-act="ceiling-save">Save ceiling</button>');
    },
    exportData: function () {
      return head('Export everything', 'modal-title') +
        '<div class="overlay__body">' +
          '<p class="t-sm">A complete copy of this workspace: projects, deliverables, every version, notes, runs, spend records and members.</p>' +
          '<ul class="ticks">' +
            '<li>' + icon('check', 'icon icon--sm') + 'Readable without ProjectOne.</li>' +
            '<li>' + icon('check', 'icon icon--sm') + 'Prepared in the background — you are told when it is ready.</li>' +
            '<li>' + icon('check', 'icon icon--sm') + 'The link expires, so an old email cannot be used to reach your data later.</li>' +
          '</ul>' +
        '</div>' +
        foot('<button type="button" class="btn btn--secondary" data-act="close" data-arg="modal">Cancel</button>' +
             '<button type="button" class="btn btn--primary" data-act="export-start" data-autofocus>Prepare my export</button>');
    },
    deleteWs: function () {
      return head('Delete this workspace?', 'modal-title') +
        '<div class="overlay__body">' +
          '<div class="warnbox warnbox--bad">' + icon('alert-triangle', 'icon icon--lg') +
            '<p class="t-sm"><strong>This cannot be undone.</strong> Four people lose access immediately. Every project, deliverable, version, note and run is removed across all live systems within 30 days. Encrypted backups age out on their own short schedule, and the audit trail is kept — both are stated exceptions, not oversights.</p></div>' +
          '<div class="field"><label class="field__label" for="del-confirm">Type the workspace name to confirm</label>' +
          '<input class="input" id="del-confirm" type="text" placeholder="' + esc(U.DATA.workspace.name) + '" autocomplete="off"></div>' +
          '<p class="t-sm t-muted">Consider <button type="button" class="linkbtn" data-act="export-open">exporting everything</button> first.</p>' +
        '</div>' +
        foot('<button type="button" class="btn btn--secondary" data-act="close" data-arg="modal" data-autofocus>Keep my workspace</button>' +
             '<button type="button" class="btn btn--danger" data-act="delete-ws-confirm">Delete permanently</button>');
    },
    killswitch: function () {
      return head('Pause all AI spend?', 'modal-title') +
        '<div class="overlay__body">' +
          '<p class="t-sm">Every AI call in this workspace stops immediately. Runs in flight finish the step they are on rather than being cut off mid-draft; nothing new starts.</p>' +
          '<p class="t-sm t-muted">Work already saved is untouched. You can lift this from the same screen — it does not need a deploy, and it does not need us.</p>' +
        '</div>' +
        foot('<button type="button" class="btn btn--secondary" data-act="close" data-arg="modal" data-autofocus>Cancel</button>' +
             '<button type="button" class="btn btn--danger" data-act="killswitch-confirm">Pause all AI spend</button>');
    }
  };

  /* -------------------------------------------------------------- drawers */
  PO.drawer = {
    approval: function (runId) {
      var r = U.runById(runId);
      if (!r) return '';
      var st = r.steps.filter(function (x) { return x.status === 'awaiting_approval'; })[0];
      if (!st) return head('Nothing to approve', 'drawer-title') +
        '<div class="overlay__body"><p class="t-sm">This run is no longer waiting on an approval — it has moved on since this panel was opened.</p></div>' +
        foot('<button type="button" class="btn btn--secondary" data-act="close" data-arg="drawer" data-autofocus>Close</button>');
      var def = U.stepDef(st.index);
      return head('Approve one step', 'drawer-title') +
        '<div class="overlay__body">' +
          '<p class="eyebrow">Step ' + (st.index + 1) + ' of ' + r.steps.length + ' · ' + esc(r.title) + '</p>' +
          '<h3 class="t-h2">' + esc(def.name) + '</h3>' +
          '<dl class="confirm">' +
            '<div><dt>What it does</dt><dd>' + esc(def.purpose) + '</dd></div>' +
            '<div><dt>What it touches</dt><dd>' + esc(def.touches) + '</dd></div>' +
            '<div><dt>Estimated cost</dt><dd class="t-num">' + money(U.DATA.estimate.low) + ' – ' + money(U.DATA.estimate.high) + '</dd></div>' +
          '</dl>' +
          '<div class="warnbox">' + icon('shield-check', 'icon icon--lg') +
            '<p class="t-sm"><strong>This approval covers this step and nothing else.</strong> It is spent the moment the step is admitted, and it cannot be reused. If the run reaches another gated step it stops again and asks you again.</p></div>' +
          '<p class="t-xs t-muted">Approving is recorded against your name and kept in the workspace’s trail.</p>' +
        '</div>' +
        foot('<button type="button" class="btn btn--secondary" data-act="close" data-arg="drawer" data-autofocus>Not now</button>' +
             '<button type="button" class="btn btn--primary" data-act="approve-confirm" data-arg="' + r.id + '">Approve this step</button>');
    },
    failure: function (runId) {
      var r = U.runById(runId);
      if (!r || !r.failure) return '';
      return head('What happened', 'drawer-title') +
        '<div class="overlay__body">' +
          '<p class="t-h3">' + esc(r.failure.headline) + '</p>' +
          '<p class="t-sm">' + esc(r.failure.plain) + '</p>' +
          '<div class="warnbox">' + icon('shield-check', 'icon icon--lg') +
            '<p class="t-sm">' + esc(r.failure.why_stopped) + '</p></div>' +
          '<p class="t-sm">' + esc(r.failure.billed) + '</p>' +
          '<details class="disclose"><summary>Show the attempt log</summary>' +
          '<pre class="log t-mono t-xs">' + esc(r.failure.technical) + '</pre></details>' +
        '</div>' +
        foot('<button type="button" class="btn btn--secondary" data-act="close" data-arg="drawer" data-autofocus>Close</button>' +
             '<button type="button" class="btn btn--primary" data-act="resume-open" data-arg="' + r.id + '">Resume production</button>');
    },
    asset: function (id) {
      var a = U.assetById(id); if (!a) return '';
      var src = a.from ? U.assetById(a.from) : null;
      return head(a.name, 'drawer-title') +
        '<div class="overlay__body">' +
          '<div class="drawer__art">' + frame(a, { aspect: a.doc === 'carousel' ? '1x1' : (a.doc ? '4x5' : a.aspect) }) + '</div>' +
          '<dl class="confirm">' +
            '<div><dt>Format</dt><dd>' + esc(a.spec) + '</dd></div>' +
            '<div><dt>Size</dt><dd>' + esc(a.size) + '</dd></div>' +
            '<div><dt>Version</dt><dd class="t-num">v' + a.version + ' of ' + ((a.versions || []).length || 1) + '</dd></div>' +
            '<div><dt>State</dt><dd>' + U.assetBadge(a.state) + '</dd></div>' +
            '<div><dt>Owner</dt><dd>' + esc(U.person(a.owner).name) + '</dd></div>' +
            (src ? '<div><dt>Derived from</dt><dd><a href="#/review/' + src.id + '">' + esc(src.name) + '</a> · ' + esc(a.fromAt) + '</dd></div>' : '') +
          '</dl>' +
          '<p class="t-sm t-muted">' + esc(a.note) + '</p>' +
        '</div>' +
        foot('<button type="button" class="btn btn--secondary" data-act="close" data-arg="drawer">Close</button>' +
             '<a class="btn btn--secondary" href="#/studio/' + a.id + '" data-act="close" data-arg="drawer">Open in studio</a>' +
             '<a class="btn btn--primary" href="#/review/' + a.id + '" data-act="close" data-arg="drawer">Open the review</a>');
    }
  };

  /* -------------------------------------------------------- command palette
     Everything reachable, by name, from anywhere. Cmd/Ctrl-K. */
  function paletteItems() {
    var out = [];
    U.NAV.forEach(function (n) { out.push({ label: n.label, note: 'Go to', href: n.href, ic: n.icon }); });
    out.push({ label: 'Creation plan', note: 'Go to', href: '#/plan', ic: 'file-text' });
    out.push({ label: 'Recipes', note: 'Go to', href: '#/library/recipes', ic: 'book' });
    out.push({ label: 'Design components', note: 'Go to', href: '#/spec', ic: 'grid' });
    U.projects().forEach(function (p) { out.push({ label: p.name, note: 'Project', href: '#/projects/' + p.id, ic: 'layers' }); });
    U.assets().forEach(function (a) { out.push({ label: a.name, note: 'Deliverable · v' + a.version, href: '#/review/' + a.id, ic: 'eye' }); });
    U.runs().forEach(function (r) { out.push({ label: r.title, note: 'Run · ' + U.RUN_LABEL[r.status], href: '#/runs/' + r.id, ic: 'activity' }); });
    ['profile', 'workspace', 'members', 'providers', 'notifications', 'billing', 'security'].forEach(function (t) {
      out.push({ label: 'Settings — ' + t.charAt(0).toUpperCase() + t.slice(1), note: 'Go to', href: '#/settings/' + t, ic: 'sliders' });
    });
    return out;
  }
  PO.paletteItems = paletteItems;

  PO.modal.palette = function (q) {
    q = (q || '').toLowerCase();
    var items = paletteItems().filter(function (i) { return !q || i.label.toLowerCase().indexOf(q) !== -1 || i.note.toLowerCase().indexOf(q) !== -1; });
    return '<div class="palette">' +
      '<div class="palette__search">' + icon('search', 'icon icon--lg') +
        '<label class="u-sr-only" for="pal-input">Search everything</label>' +
        '<input class="palette__input" id="pal-input" type="text" placeholder="Search projects, deliverables, runs and screens…" value="' + esc(q) + '" data-autofocus autocomplete="off">' +
        '<button type="button" class="iconbtn" data-act="close" data-arg="modal" aria-label="Close search">' + icon('x', 'icon icon--lg') + '</button>' +
      '</div>' +
      '<div class="palette__list" role="listbox" aria-label="Results">' +
        (items.length
          ? items.slice(0, 10).map(function (i) {
              return '<a class="pal" href="' + i.href + '" role="option" aria-selected="false" data-act="palette-go" data-arg="' + i.href + '">' +
                icon(i.ic, 'icon icon--sm') + '<span class="pal__label">' + esc(i.label) + '</span>' +
                '<span class="pal__note t-xs t-muted">' + esc(i.note) + '</span></a>';
            }).join('')
          : '<p class="pal__none t-sm t-muted">Nothing matches “' + esc(q) + '”.</p>') +
      '</div>' +
      '<p class="palette__foot t-xs t-muted">' + plural(items.length, 'result') + ' · Esc to close</p>' +
    '</div>';
  };
})();

/* ==========================================================================
   ACTIONS

   One delegated listener drives all of them, so a screen can be re-rendered
   wholesale without ever rebinding anything. Every action either changes
   state and re-renders, opens an overlay, or navigates. None of them decides
   whether it is allowed to — that is read from the payload before the control
   is rendered at all.
   ========================================================================== */
(function () {
  var U = PO.ui, C = PO.CAMPAIGN, M = PO.modes, c = PO.composer;
  var esc = U.esc, money = U.money, plural = U.plural;
  var A = PO.actions;

  function reRender(focus) { U.refresh(focus); }
  function shot(name) { U.toast(name + ' is a design prototype — this shows the shape of the interaction, not a saved change.', 'info'); }

  /* ------------------------------------------------------------- composer */
  A['mode'] = function (id) { c.mode = id; c.selected = null; reRender('[data-act="mode"][data-arg="' + id + '"]'); };
  A['try'] = function (i) {
    c.prompt = M.modeById(c.mode).examples[Number(i)] || '';
    reRender('#composer-input');
  };
  A['out'] = function (id) { c.selected = id; reRender('#outcome-back'); };
  A['out-back'] = function () {
    var was = c.selected; c.selected = null;
    reRender('[data-act="out"][data-arg="' + was + '"]');
  };
  A['ref-open'] = function () { U.openDialog('modal', PO.modal.ref()); };
  A['ref-pick'] = function (id) { c.ref = (c.ref === id ? null : id); U.closeDialog('modal'); reRender('[data-act="ref-open"], .chip--on'); };
  A['ref-clear'] = function () { c.ref = null; reRender('[data-act="ref-open"]'); };
  A['ctx-open'] = function () { U.openDialog('modal', PO.modal.ctx()); };
  A['ctx-pick'] = function (id) { c.project = (c.project === id ? null : id); U.closeDialog('modal'); reRender('[data-act="ctx-open"], .chip--on'); };
  A['ctx-clear'] = function () { c.project = null; reRender('[data-act="ctx-open"]'); };
  A['dest-open'] = function () { U.showPopover('dest-popover', 'dest-trigger', PO.pop.dest()); };
  A['ess'] = function (key) { U.showPopover('ess-popover', 'ess-' + key, PO.pop.ess(key)); };
  A['ess-set'] = function (arg) {
    var bits = String(arg).split('|');
    M.essSet(c.mode, bits[0], bits.slice(1).join('|'));
    U.closePopover(false);
    reRender('#ess-' + bits[0]);
  };
  A['ess-toggle'] = function (arg) {
    var bits = String(arg).split('|'), key = bits[0], id = bits[1];
    var cur = M.essValue(c.mode, key);
    var at = cur.indexOf(id);
    if (at === -1) cur.push(id); else cur.splice(at, 1);
    M.essSet(c.mode, key, cur);
    /* The popover stays open — ticking three channels should be three presses,
       not three round trips — but the page behind it has to move, because the
       deliverables and the cost just changed. Close, re-render, re-open, and
       put the caret back on the row that was pressed. */
    U.closePopover(false);
    reRender(null);
    U.showPopover('ess-popover', 'ess-' + key, PO.pop.ess(key));
    var back = document.querySelector('#ess-popover [data-arg="' + key + '|' + id + '"]');
    if (back) back.focus();
  };
  A['dest'] = function (id) { c.dest = id; U.closePopover(false); reRender('#dest-trigger'); };

  A['prepare'] = function () {
    if (!c.prompt.trim()) return;
    var ref = c.ref ? M.REF_LIBRARY.filter(function (r) { return r.id === c.ref; })[0] : null;
    /* Snapshot, not a live reference: editing Home after preparing a plan
       must not silently rewrite the plan you are looking at. */
    var snap = {}; snap[c.mode] = {};
    M.essFields(c.mode).forEach(function (fd) { snap[c.mode][fd.key] = M.essValue(c.mode, fd.key); });
    c.plan = { mode: c.mode, prompt: c.prompt, ref: c.ref, refName: ref ? ref.name : null,
               project: c.project, dest: c.dest, removed: {}, ess: snap };
    U.go('#/plan');
  };

  A['recipe'] = function (id) {
    var r = M.RECIPES.filter(function (x) { return x.id === id; })[0];
    if (!r) return;
    c.mode = r.mode; c.prompt = r.prompt; c.ref = r.ref; c.dest = r.dest; c.selected = null;
    U.closeDialog('modal');
    if (U.state.route.name !== 'dashboard') U.go('#/dashboard');
    else reRender('#composer-input');
    U.toast('“' + r.name + '” loaded. Everything is still yours to change.', 'ok');
  };

  /* ----------------------------------------------------------------- plan */
  A['deliv-remove'] = function (id) {
    if (!c.plan) return;
    c.plan.removed[id] = true;
    reRender('[data-act="deliv-add-open"]');
    U.toast('Removed. Anything that depended on it is now shown as unbuildable rather than quietly dropped.', 'info');
  };
  A['deliv-add-open'] = function () { U.openDialog('modal', PO.modal.add()); };
  A['deliv-add'] = function (id) {
    if (!c.plan) return;
    delete c.plan.removed[id];
    U.closeDialog('modal');
    reRender('[data-act="deliv-add-open"]');
    U.toast('Added back to the plan.', 'ok');
  };
  A['start-open'] = function () { U.openDialog('modal', PO.modal.start()); };
  A['start-confirm'] = function () {
    U.closeDialog('modal');
    var id = 'r_' + (U.state.nextRunId++);
    var p = c.plan || {};
    var proj = p.project || 'p_kc2';
    U.state.runs.unshift({
      id: id, title: PO.plan.goalLine(p.prompt || 'New production').slice(0, 52), project_id: proj,
      workflow: 'project_planning', version: 1, status: 'pending', started: 'Just now', finished: null,
      tokens: 0, cost: 0, by: U.server().user.id,
      queue_note: 'Handed to production. Starting a run returns immediately — nothing executes inside the request that started it.',
      steps: [
        { index: 0, status: 'pending', detail: null, tokens: null, cost: null, started: null, finished: null, duration: null },
        { index: 1, status: 'pending', detail: null, tokens: null, cost: null, started: null, finished: null, duration: null },
        { index: 2, status: 'pending', detail: null, tokens: null, cost: null, started: null, finished: null, duration: null }
      ]
    });
    U.go('#/runs/' + id);
    U.toast('Production started. It runs without this screen open.', 'ok');
    PO.simulateStart(id);
  };

  /* ------------------------------------------------------------ approvals */
  A['approve-open'] = function (id) {
    var r = U.runById(id);
    if (!r || r.status !== 'awaiting_approval') { U.toast('That run is no longer waiting for an approval.', 'info'); return; }
    U.openDialog('drawer', PO.drawer.approval(id));
  };
  A['approve-confirm'] = function (id) {
    var r = U.runById(id);
    U.closeDialog('drawer');
    if (!r || r.status !== 'awaiting_approval') { U.toast('That approval was already used.', 'info'); return; }
    var st = r.steps.filter(function (x) { return x.status === 'awaiting_approval'; })[0];
    st.status = 'running'; st.started = 'Just now';
    st.approved_by = U.server().user.name + ' just now';
    r.status = 'running';
    r.approved_note = 'Planning agent approved by ' + U.server().user.name + '.';
    U.go('#/runs/' + id);
    U.toast('Approved — this step only. The run stops again at the next gate.', 'ok');
    PO.simulateAfterApproval(id);
  };
  A['failure-open'] = function (id) { U.openDialog('drawer', PO.drawer.failure(id)); };
  A['resume-open'] = function (id) {
    var r = U.runById(id);
    if (!r || r.status !== 'failed') { U.toast('That run is not in a state that can be resumed.', 'info'); return; }
    U.closeDialog('drawer');
    U.openDialog('modal', PO.modal.resume(id));
  };
  A['resume-confirm'] = function (id) {
    var r = U.runById(id);
    U.closeDialog('modal');
    if (!r || r.status !== 'failed') { U.toast('That run has already moved on.', 'info'); return; }
    r.status = 'pending';
    r.steps[1].status = 'pending'; r.steps[1].detail = null;
    r.queue_note = 'Resumed. Production picks up from the last step that completed.';
    delete r.failure;
    U.go('#/runs/' + id);
    U.toast('Resumed. It picks up from the last step that completed.', 'ok');
    PO.simulateStart(id, true);
  };

  /* -------------------------------------------------------------- project */
  A['transition'] = function (arg) {
    var parts = String(arg).split(':');
    var p = U.projectById(parts[0]);
    if (!p) return;
    p.status = parts[1];
    p.legal_transitions = ({ idea: ['planning', 'archive'], planning: ['generation', 'archive'],
      generation: ['review', 'archive'], review: ['editing', 'archive'], editing: ['approval', 'archive'],
      approval: ['publishing', 'archive'], publishing: ['analytics', 'archive'], analytics: ['archive'], archive: ['idea'] })[parts[1]] || ['archive'];
    reRender('.lifecycle .btn');
    U.toast(p.name + ' moved to ' + U.PROJECT_LABEL[parts[1]] + '.', 'ok');
  };
  A['archive-open'] = function (arg) { U.openDialog('modal', PO.modal.archive(String(arg).split(':')[0]), { focus: '[data-autofocus]' }); };
  A['archive-confirm'] = function (id) {
    var p = U.projectById(id); if (!p) return;
    p.status = 'archive'; p.legal_transitions = ['idea'];
    U.closeDialog('modal');
    U.go('#/projects');
    U.toast(p.name + ' archived. Nothing was deleted.', 'ok');
  };
  A['project-menu'] = function (id) {
    U.showPopover('ws-popover', 'pmenu-trigger',
      '<a class="menuitem" href="#/studio" data-act="close-popover">' + U.icon('scissors', 'icon icon--sm') + 'Open the studio</a>' +
      '<a class="menuitem" href="#/projects/' + id + '/activity" data-act="close-popover">' + U.icon('history', 'icon icon--sm') + 'Project activity</a>' +
      '<button type="button" class="menuitem" data-act="save" data-arg="Duplicate project">' + U.icon('copy', 'icon icon--sm') + 'Duplicate</button>' +
      '<button type="button" class="menuitem menuitem--danger" data-act="archive-open" data-arg="' + id + '">' + U.icon('inbox', 'icon icon--sm') + 'Archive project…</button>');
  };

  /* --------------------------------------------------------------- review */
  A['pin'] = function (id) {
    var el = document.getElementById('note-' + id);
    if (!el) return;
    el.scrollIntoView({ block: 'nearest', behavior: 'auto' });
    el.classList.add('is-flash');
    setTimeout(function () { el.classList.remove('is-flash'); }, 900);
    var btn = el.querySelector('button');
    if (btn) btn.focus(); else el.setAttribute('tabindex', '-1'), el.focus();
  };
  A['note-resolve'] = function (id) {
    U.assets().forEach(function (a) {
      (a.comments || []).forEach(function (cm) { if (cm.id === id) cm.open = false; });
    });
    reRender('#note-' + id + ' .linkbtn, .notenew textarea');
    U.toast('Note resolved.', 'ok');
  };
  A['note-add'] = function (id) {
    var box = document.getElementById('note-input');
    var text = box ? box.value.trim() : '';
    if (!text) { if (box) box.focus(); U.toast('Write the note first — an empty one helps nobody.', 'info'); return; }
    var a = U.assetById(id); if (!a) return;
    a.comments = a.comments || [];
    a.comments.push({ id: 'c' + Date.now(), who: U.server().user.id, at: 'General', when: 'Just now',
      x: 50, y: 50, open: true, text: text });
    reRender('#note-input');
    U.toast('Note added. Whoever picks this up will see it pinned to the work.', 'ok');
  };
  A['approve-asset'] = function (id) {
    var a = U.assetById(id); if (!a) return;
    a.state = 'approved';
    a.approvedBy = U.server().user.id; a.approvedAt = 'Just now';
    reRender('.review__side .btn, .approved');
    U.toast(a.name + ' approved at version ' + a.version + '.', 'ok');
  };
  A['request-changes'] = function (id) {
    var a = U.assetById(id); if (!a) return;
    a.state = 'changes';
    var box = document.getElementById('note-input');
    reRender('#note-input');
    U.toast('Marked as needing changes. Add a note saying what, so nobody has to guess.', 'info');
  };
  A['ver-restore'] = function (arg) {
    var parts = String(arg).split(':');
    var a = U.assetById(parts[0]); if (!a) return;
    U.toast('Restoring v' + parts[1] + ' would add it as a new version rather than overwriting v' + a.version + '. Nothing is ever lost.', 'info');
  };
  A['asset-inspect'] = function (id, el, e) { U.openDialog('drawer', PO.drawer.asset(id)); };

  /* --------------------------------------------------------------- studio */
  A['beat'] = function (i) { PO.studioBeat = Number(i); reRender('[data-act="beat"][data-arg="' + i + '"]'); };
  A['regen-open'] = function (id) { U.openDialog('modal', PO.modal.regen(id), { focus: '[data-autofocus]' }); };
  A['regen-confirm'] = function (id) {
    var a = U.assetById(id);
    U.closeDialog('modal');
    if (!a) return;
    a.version += 1;
    a.state = 'review';
    a.versions = ([{ n: a.version, when: 'Just now', who: U.server().user.id, note: 'Regenerated from the studio.' }]).concat(a.versions || []);
    a.updated = 'Just now';
    reRender('.studio__acts .btn--primary');
    U.toast('Version ' + a.version + ' created and sent for review. v' + (a.version - 1) + ' is still there.', 'ok');
  };

  /* -------------------------------------------------------------- library */
  A['lib-filter'] = function (id) { PO.libFilter = id; reRender('[data-act="lib-filter"][data-arg="' + id + '"]'); };

  /* ------------------------------------------------------------- assistant */
  A['chat-send'] = function () {
    var box = document.getElementById('chat-input');
    var t = box ? box.value.trim() : '';
    if (!t) { if (box) box.focus(); return; }
    if (box) box.value = '';
    U.toast('In the real product this reaches the assistant. Here the conversation is fixed, so the answers stay honest.', 'info');
  };

  /* ---------------------------------------------------------------- spend */
  A['killswitch'] = function () { U.openDialog('modal', PO.modal.killswitch(), { focus: '[data-autofocus]' }); };
  A['killswitch-confirm'] = function () {
    U.closeDialog('modal');
    U.state.scenario = 'breaker';
    var sel = document.getElementById('scenario'); if (sel) sel.value = 'breaker';
    U.render();
    U.toast('All AI spend paused for this workspace.', 'ok');
  };

  /* ------------------------------------------------------------- settings */
  A['save'] = function (what) { U.toast((what || 'Changes') + ' saved.', 'ok'); };
  A['toggle'] = function (arg, el) {
    var on = el.getAttribute('aria-pressed') === 'true';
    el.setAttribute('aria-pressed', String(!on));
  };
  A['invite-open'] = function () { U.openDialog('modal', PO.modal.invite()); };
  A['invite-send'] = function () {
    var box = document.getElementById('inv-email');
    var v = box ? box.value.trim() : '';
    if (!v) { if (box) box.focus(); U.toast('An email address is needed to send an invitation.', 'info'); return; }
    U.closeDialog('modal');
    U.toast('Invitation sent to ' + v + '. They see nothing until they accept.', 'ok');
  };
  A['member-menu'] = function (id) {
    var m = U.DATA.members.filter(function (x) { return x.id === id; })[0];
    U.toast('Changing ' + (m ? m.name + '’s' : 'a') + ' role, and removing someone, are both here in the real product — and both are recorded in the trail.', 'info');
  };
  A['provider-open'] = function (id) { U.openDialog('modal', PO.modal.provider(id === 'new' ? null : id)); };
  A['provider-save'] = function () {
    var box = document.getElementById('pk-key');
    U.closeDialog('modal');
    U.toast('Key stored, encrypted. Only its last four characters are shown again.', 'ok');
  };
  A['ceiling-open'] = function () { U.openDialog('modal', PO.modal.ceiling()); };
  A['ceiling-save'] = function () { U.closeDialog('modal'); U.toast('Monthly ceiling updated.', 'ok'); };
  A['invoice'] = function (p) { U.toast('The ' + p + ' receipt opens as a PDF in the real product.', 'info'); };
  A['cancel-plan'] = function () { U.toast('Cancelling takes effect at the end of the period, and it is right here rather than hidden behind an email.', 'info'); };
  A['export-open'] = function () { U.closeDialog('modal'); U.openDialog('modal', PO.modal.exportData(), { focus: '[data-autofocus]' }); };
  A['export-start'] = function () { U.closeDialog('modal'); U.toast('Preparing your export. You will be told when it is ready.', 'ok'); };
  A['delete-ws'] = function () { U.openDialog('modal', PO.modal.deleteWs(), { focus: '[data-autofocus]' }); };
  A['delete-ws-confirm'] = function () {
    var box = document.getElementById('del-confirm');
    if (!box || box.value.trim() !== U.DATA.workspace.name) {
      if (box) box.focus();
      U.toast('Type the workspace name exactly to confirm. This is the one thing that cannot be undone.', 'bad');
      return;
    }
    U.closeDialog('modal');
    U.toast('In the real product this begins a 30-day erasure you can watch. Nothing was deleted here.', 'info');
  };

  /* ------------------------------------------------------------ auth flow */
  A['signin-submit'] = function () { U.go('#/welcome'); };
  A['wiz'] = function (n) { PO.welcomeStep = Number(n); U.render(); };
  A['wiz-done'] = function () { PO.welcomeStep = 1; U.go('#/dashboard'); U.toast('Welcome. Write one brief and see what it becomes.', 'ok'); };

  /* --------------------------------------------------------------- chrome */
  A['close'] = function (which) { U.closeDialog(which || 'modal'); };
  A['close-popover'] = function () { U.closePopover(false); };
  A['retry'] = function () {
    U.state.scenario = 'normal';
    var sel = document.getElementById('scenario'); if (sel) sel.value = 'normal';
    U.render(); U.toast('Connected.', 'ok');
  };
  A['noop'] = function (a, el) {
    if (!el) return;
    var group = el.parentNode ? el.parentNode.querySelectorAll('[aria-pressed]') : [];
    Array.prototype.forEach.call(group, function (g) { g.setAttribute('aria-pressed', 'false'); g.classList.remove('is-on'); });
    el.setAttribute('aria-pressed', 'true'); el.classList.add('is-on');
  };
  A['palette'] = function () { U.openDialog('modal', PO.modal.palette(''), { focus: '#pal-input' }); };
  A['palette-go'] = function (href) { U.closeDialog('modal'); U.go(href); };

  A['ws-menu'] = function () { U.showPopover('ws-popover', 'ws-trigger', PO.pop.ws()); };
  A['user-menu'] = function () { U.showPopover('user-popover', 'user-trigger', PO.pop.user()); };
  A['theme-menu'] = function () { U.showPopover('theme-popover', 'theme-trigger', PO.pop.theme()); };
  A['notif-menu'] = function () { U.showPopover('notif-popover', 'notif-trigger', PO.pop.notif()); };
  A['nav-open'] = function () {
    U.openDialog('navdrawer', PO.navDrawer());
    PO.core.renderRail();
  };

  /* ------------------------------------------------------------- the theme */
  PO.theme = function () {
    try { return localStorage.getItem('po-theme') || 'system'; } catch (e) { return 'system'; }
  };
  A['theme'] = function (val) {
    try { if (val === 'system') localStorage.removeItem('po-theme'); else localStorage.setItem('po-theme', val); } catch (e) {}
    PO.applyTheme();
    U.closePopover(false);
    if (U.state.route.name === 'settings') U.refresh('[data-act="theme"][data-arg="' + val + '"]');
    else PO.core.renderNotifBadge();
  };
  PO.applyTheme = function () {
    var t = PO.theme();
    var root = document.documentElement;
    if (t === 'system') root.removeAttribute('data-theme');
    else root.setAttribute('data-theme', t);
    var ic = document.getElementById('theme-icon');
    if (ic) ic.innerHTML = '<use href="#i-' + (t === 'light' ? 'sun' : t === 'dark' ? 'moon' : 'monitor') + '"/>';
  };

  /* --------------------------------------------------- the simulated worker
     Timing only. The step sequence, the gate and the step record mirror what
     the backend actually does; how fast it happens here does not. */
  function sim(fn, ms) { U.state.simTimers.push(setTimeout(fn, ms)); }
  function announce(msg) {
    var el = document.getElementById('run-live');
    if (el) el.textContent = msg;
  }
  function advance(runId, mutate, note, kind, ms) {
    sim(function () {
      var r = U.runById(runId); if (!r) return;
      mutate(r);
      if (note) { U.toast(note, kind || 'info'); announce(note); }
      /* Only re-render if the user is still looking at this run; otherwise the
         worker would rip the screen out from under whatever they moved on to. */
      if (U.state.route.name === 'run' && U.state.route.id === runId) {
        var active = document.activeElement;
        var sel = active && active.dataset && active.dataset.act ? '[data-act="' + active.dataset.act + '"]' : null;
        U.refresh(sel);
      } else {
        PO.core.renderRail(); PO.core.renderNotifBadge();
      }
    }, ms);
  }
  PO.simulateStart = function (runId, resumed) {
    advance(runId, function (r) {
      r.status = 'running'; r.steps[0].status = 'running'; r.steps[0].started = 'Just now';
    }, 'Validating the brief.', 'info', 1600);
    advance(runId, function (r) {
      r.steps[0].status = 'completed'; r.steps[0].duration = '0.5s';
      r.steps[0].detail = 'Brief, target format and audience all present.';
      r.steps[1].status = 'awaiting_approval';
      r.status = 'awaiting_approval';
    }, 'One step needs your approval before it calls a provider.', 'info', 4200);
  };
  PO.simulateAfterApproval = function (runId) {
    advance(runId, function (r) {
      r.steps[1].status = 'completed'; r.steps[1].duration = '1m 47s';
      r.steps[1].tokens = 7240; r.steps[1].cost = 0.118;
      r.steps[1].detail = 'Drafted a six-part outline with a hook per part and a suggested shooting order.';
      r.steps[2].status = 'running'; r.tokens = 7240; r.cost = 0.118;
    }, 'The plan is drafted. Running the quality check.', 'info', 3400);
    advance(runId, function (r) {
      r.steps[2].status = 'completed'; r.steps[2].duration = '0.7s';
      r.steps[2].detail = 'Score 0.88. Flagged one gap: no troubleshooting section.';
      r.status = 'completed'; r.finished = 'Just now'; r.output_asset = 'as_outline';
    }, 'Finished. The plan was saved to the project.', 'ok', 5600);
  };
})();

/* ==========================================================================
   COMPONENTS — the specimen sheet
   Prototype-only. Every specimen here is LIVE: it toggles, opens or reports
   what it is. A sheet full of buttons that do nothing is the dark pattern the
   rest of this prototype refuses, and it does not get an exemption for being
   documentation.
   ========================================================================== */
(function () {
  var U = PO.ui;
  var esc = U.esc, icon = U.icon, frame = U.frame;

  var SEMANTIC = ['background', 'surface', 'surface-raised', 'nav-surface', 'nav-surface-raised',
    'text-on-nav', 'text-on-nav-muted', 'accent-on-nav', 'border', 'border-strong', 'text', 'text-muted',
    'accent', 'accent-hover', 'accent-fill', 'accent-contrast', 'success', 'warning', 'danger',
    'danger-contrast', 'skeleton', 'focus-ring'];
  var ICONS = ['home', 'layers', 'scissors', 'grid', 'activity', 'history', 'message-circle', 'wallet', 'sliders',
    'bell', 'chevron-down', 'chevron-right', 'chevron-left', 'arrow-left', 'arrow-right', 'corner-down-right',
    'menu', 'x', 'check', 'check-circle', 'alert-triangle', 'alert-circle', 'info', 'clock', 'hourglass',
    'spinner', 'play', 'film', 'image', 'refresh', 'shield-check', 'sun', 'moon', 'monitor', 'user', 'users',
    'plus', 'file-text', 'lock', 'ban', 'zap', 'inbox', 'log-out', 'eye', 'book', 'search', 'send', 'paperclip',
    'pencil', 'copy', 'trash', 'upload', 'download', 'more-horizontal', 'message-square', 'mail', 'flag'];

  function sec(title, note, body) {
    var id = 'sp-' + title.toLowerCase().replace(/[^a-z]+/g, '-');
    return '<section class="band" aria-labelledby="' + id + '">' +
      '<div class="band__head"><h2 class="eyebrow" id="' + id + '">' + esc(title) + '</h2></div>' +
      (note ? '<p class="t-sm t-muted band__note">' + note + '</p>' : '') +
      '<div class="spec__body">' + body + '</div></section>';
  }

  PO.views.spec = function () {
    return '<div class="lib spec">' +
      PO.masthead('Components', 'The contracts every screen in this prototype is built from. Prototype-only — this is not a product surface.') +

      sec('Colour roles', 'Roles, shown against the surface each one is legal on. An isolated swatch tells you nothing about a pair that has to pass a contrast bar.',
        '<div class="swatches">' + SEMANTIC.map(function (t) {
          var onNav = t.indexOf('nav') !== -1 || t === 'accent-on-nav';
          return '<div class="swatch' + (onNav ? ' swatch--nav' : '') + '">' +
            '<span class="swatch__chip" style="background:var(--color-' + t + ')"></span>' +
            '<span class="swatch__name t-mono t-xs">' + esc(t) + '</span></div>';
        }).join('') + '</div>') +

      sec('Type', 'The display face is bounded: it is used at the two largest sizes and never for body copy, labels or controls.',
        '<div class="typespec">' +
          '<p class="t-display-hero">What will we create today?</p>' +
          '<p class="t-display">One idea. The whole production.</p>' +
          '<p class="t-h1">Section heading</p><p class="t-h2">Sub heading</p><p class="t-h3">Minor heading</p>' +
          '<p class="t-body">Body copy sits at sixteen pixels with generous leading, because this product is read as much as it is clicked.</p>' +
          '<p class="t-sm t-muted">Small, muted — the supporting line under almost everything.</p>' +
          '<p class="eyebrow">Eyebrow · the quiet band label</p>' +
        '</div>') +

      sec('Buttons', 'Every specimen below is live. Pressing one reports what it is rather than doing nothing.',
        '<div class="row row--wrap">' +
          ['primary', 'secondary', 'ghost', 'danger'].map(function (k) {
            return '<button type="button" class="btn btn--' + k + '" data-act="save" data-arg="The ' + k + ' button">' + esc(k.charAt(0).toUpperCase() + k.slice(1)) + '</button>';
          }).join('') +
          '<button type="button" class="btn btn--primary" disabled>Disabled</button>' +
          '<button type="button" class="btn btn--primary btn--lg" data-act="palette">Large' + icon('arrow-right', 'icon') + '</button>' +
          '<button type="button" class="btn btn--secondary btn--sm" data-act="save" data-arg="The small button">Small</button>' +
        '</div>') +

      sec('Status', 'Colour never carries meaning alone — every one of these has a word, and most have a shape too.',
        '<div class="row row--wrap">' + [['ok', 'Approved'], ['warn', 'Needs you'], ['bad', 'Stopped'], ['info', 'Running'], ['neutral', 'Queued']].map(function (b) {
          return U.badge(b[0], b[1]);
        }).join('') + '</div>') +

      sec('Media frames', 'Everything generated is drawn, at the aspect it is actually delivered in.',
        '<div class="row row--wrap framespec">' +
          ['16x9', '9x16', '1x1', '4x5'].map(function (a) {
            return '<figure><span class="frame frame--' + a + '" style="width:' + (a === '9x16' ? '5rem' : a === '16x9' ? '11rem' : '7rem') + '">' +
              PO.art.still(a === '9x16' ? 'sear' : a === '1x1' ? 'over' : a === '4x5' ? 'loaf' : 'sear', a, { detail: 'thumb' }) +
              '</span><figcaption class="t-xs t-muted">' + esc(a.replace('x', ':')) + '</figcaption></figure>';
          }).join('') +
          '<figure><span class="frame frame--4x5" style="width:7rem">' + PO.art.doc('script', {}) + '</span>' +
          '<figcaption class="t-xs t-muted">Written work — ivory, never ink</figcaption></figure>' +
        '</div>') +

      sec('Notices', 'Four tones. The border, the icon and the first sentence all carry the same message.',
        U.notice('info', 'info', 'Informational.', 'Something you should know, that is not asking anything of you.') +
        U.notice('ok', 'check-circle', 'Finished.', 'It worked, and here is what it produced.') +
        U.notice('warn', 'shield-check', 'One step needs your approval.', 'Production has stopped here and is waiting.') +
        U.notice('bad', 'alert-triangle', 'It stopped.', 'What happened, what it cost, and what you can do next.')) +

      sec('Empty', 'Never the same shape as an error. An empty state offers the next step; an error explains a failure.',
        U.empty('inbox', 'Nothing here yet', 'An empty state says what would be here and how to make some.',
          '<button type="button" class="btn btn--primary" data-act="save" data-arg="The empty-state action">The action that fills it</button>')) +

      sec('Overlays', 'Escape closes every one of them, and focus returns to whatever opened it.',
        '<div class="row row--wrap">' +
          '<button type="button" class="btn btn--secondary" data-act="approve-open" data-arg="r_1042">Approval drawer</button>' +
          '<button type="button" class="btn btn--secondary" data-act="failure-open" data-arg="r_1039">Failure drawer</button>' +
          '<button type="button" class="btn btn--secondary" data-act="asset-inspect" data-arg="as_trailer">Asset inspector</button>' +
          '<button type="button" class="btn btn--secondary" data-act="ref-open">Picker modal</button>' +
          '<button type="button" class="btn btn--secondary" data-act="palette">Command palette</button>' +
          '<button type="button" class="btn btn--secondary" data-act="killswitch">Destructive confirm</button>' +
        '</div>') +

      sec('Icons', 'One coherent 24×24 stroke set. No emoji is used as an interface icon anywhere in this product.',
        '<div class="iconsheet">' + ICONS.map(function (n) {
          return '<span class="iconcell" title="' + esc(n) + '">' + icon(n, 'icon icon--lg') + '<span class="t-xs t-muted">' + esc(n) + '</span></span>';
        }).join('') + '</div>') +

      sec('Motion', 'Under 250ms, and every one of them is disabled entirely when the system asks for reduced motion.',
        '<dl class="dl--cols">' +
          '<div><dt>Fast · 120ms</dt><dd>Hover, press, focus</dd></div>' +
          '<div><dt>Base · 180ms</dt><dd>Route change, panel open, outcome update</dd></div>' +
          '<div><dt>Slow · 260ms</dt><dd>Drawer and sheet travel only</dd></div>' +
        '</dl>');
  };
})();

/* ==========================================================================
   BOOT
   ========================================================================== */
(function () {
  var U = PO.ui;

  PO.bootExtras = function () {
    PO.applyTheme();

    var sel = document.getElementById('scenario');
    if (sel) {
      sel.innerHTML = Object.keys(U.SCENARIOS).map(function (k) {
        return '<option value="' + k + '">Scenario: ' + U.esc(U.SCENARIOS[k].label) + '</option>';
      }).join('');
      sel.value = U.state.scenario;
      sel.addEventListener('change', function () {
        U.state.scenario = sel.value;
        U.closeAllDialogs();
        U.render();
      });
    }

    var anno = document.getElementById('anno-toggle');
    if (anno) anno.addEventListener('click', function () {
      var on = anno.getAttribute('aria-pressed') === 'true';
      anno.setAttribute('aria-pressed', String(!on));
      document.documentElement.setAttribute('data-annotations', !on ? 'on' : 'off');
      var legend = document.getElementById('annolegend');
      if (legend) legend.hidden = on;
    });

    /* The composer's field is the one input whose value must survive a
       re-render, so it is read on every keystroke and written back on render. */
    document.addEventListener('input', function (e) {
      if (e.target && e.target.id === 'composer-input') {
        var was = !!PO.composer.prompt.trim();
        PO.composer.prompt = e.target.value;
        var now = !!PO.composer.prompt.trim();
        var cta = document.getElementById('composer-cta');
        if (cta) cta.disabled = !(now && U.startGate().ok);
        /* Only re-render when the suggestions have to appear or disappear. */
        if (was !== now) {
          var pos = e.target.selectionStart;
          U.refresh('#composer-input');
          var el = document.getElementById('composer-input');
          if (el) { el.focus(); try { el.setSelectionRange(pos, pos); } catch (err) {} }
        }
      }
      if (e.target && e.target.id === 'pal-input') {
        var q = e.target.value;
        var host = document.getElementById('modal');
        if (!host) return;
        var pos2 = e.target.selectionStart;
        host.innerHTML = PO.modal.palette(q);
        var input = document.getElementById('pal-input');
        if (input) { input.focus(); try { input.setSelectionRange(pos2, pos2); } catch (err) {} }
      }
    });

    /* Grow the composer with its content — but ONLY where the page is free to
       grow with it. Inside the one-viewport lock the field is already
       stretched by the grid, and re-measuring it here would fight the layout
       every keystroke. */
    document.addEventListener('input', function (e) {
      if (!e.target || e.target.id !== 'composer-input') return;
      if (window.matchMedia('(min-width: 64rem) and (min-height: 40rem)').matches) return;
      var ta = e.target;
      ta.style.height = 'auto';
      ta.style.height = Math.max(96, Math.min(320, ta.scrollHeight)) + 'px';
    });
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', PO.boot);
  else PO.boot();
})();
