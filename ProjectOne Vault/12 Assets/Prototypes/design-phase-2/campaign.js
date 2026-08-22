/* ==========================================================================
   ProjectOne — the campaign layer

   THIS IS NOT THE APPLICATION. Everything here is invented.

   Two jobs, and only two:

   1. ONE fictional campaign, rich enough that Home, the plan, the studio, the
      library, a run, a review and a project all describe the same piece of
      work. A prototype where every screen shows different fake data reads as
      a folder of mockups. A prototype where they agree reads as a product.

   2. The artwork. Every generated deliverable in this prototype is drawn, not
      photographed and not faked with a grey box. It is all original SVG with
      no external request, no raster asset and no third-party mark.

   HOW THE ARTWORK WORKS, because it is the load-bearing idea:

   A campaign is shot once and cut many ways. So each scene is defined ONCE,
   in a canonical 1600x900 space, inside <defs>. Every derivative is the same
   scene under a different `viewBox` — a real crop of the real master, exactly
   as a real derivative is. A 9:16 teaser is not a different picture; it is
   this picture, cropped to the pan and re-typeset. That is the product thesis
   rendered in pixels, and it costs one <use> element per instance.

   Consequences worth stating:
   - Zero duplicate ids, however many frames are on screen.
   - The palette is LITERAL, never a theme token. A photograph does not
     change colour when the interface goes dark, and neither does this.
   ========================================================================== */
(function () {
  'use strict';

  var PO = (window.PO = window.PO || {});

  /* ======================================================================
     THE CAMPAIGN

     Avery Kim Studio makes cooking shows. Season two of Kitchen Confidence
     is the piece of work this whole prototype is about.
     ====================================================================== */
  PO.CAMPAIGN = {
    id: 'camp_kc2',
    project_id: 'p_kc2',
    brand: 'Kitchen Confidence',
    season: 'Season Two',
    title: 'Kitchen Confidence — Season Two',
    idea: 'Six techniques people are afraid of. Six episodes. No fear.',
    tagline: 'Cook it scared.',
    audience: 'Home cooks who own the pans but not the nerve',
    tone: 'Warm, practical, no mysticism',
    palette: 'Ember and ivory. Real kitchen light, no gloss.',
    launch: '14 September',
    episodes: [
      { n: 1, title: 'The Sear', technique: 'Cast iron, hot and dry' },
      { n: 2, title: 'The Rise', technique: 'A starter you cannot kill' },
      { n: 3, title: 'The Break', technique: 'Emulsions that hold' },
      { n: 4, title: 'The Bone', technique: 'Stock without the fuss' },
      { n: 5, title: 'The Blade', technique: 'One knife, four cuts' },
      { n: 6, title: 'The Fire', technique: 'Live flame indoors' }
    ],
    people: [
      { id: 'u_avery', name: 'Avery Kim', initials: 'AK', role: 'Creator', you: true },
      { id: 'u_noor', name: 'Noor Haddad', initials: 'NH', role: 'Producer' },
      { id: 'u_diego', name: 'Diego Salas', initials: 'DS', role: 'Editor' },
      { id: 'u_priya', name: 'Priya Raman', initials: 'PR', role: 'Design' }
    ]
  };

  /* ======================================================================
     THE WORK ITSELF

     Ten pieces of work, at ten different points in their life. Versions,
     reviewers, open notes, blockers, provenance back to the frame they were
     cut from. A prototype that shows only finished work shows nothing about
     production, which is the half of the thesis nobody else builds.

     `state` is one of: approved | review | changes | draft | queued | blocked
     ====================================================================== */
  PO.ASSETS = [
    {
      id: 'as_trailer', name: 'Season Two — Trailer', short: 'Trailer',
      kind: 'video', scene: 'sear', aspect: '16x9', lockup: 'title',
      lockupTitle: 'Kitchen Confidence', lockupEyebrow: 'Season Two',
      spec: '1920 × 1080 · 1:52', size: '412 MB', master: true,
      version: 4, state: 'review', owner: 'u_diego', reviewer: 'u_noor',
      updated: '2 hours ago', stage: 'Master',
      note: 'The cut everything else is derived from. Colour lock is what the rest are waiting on.',
      versions: [
        { n: 4, when: 'Today, 11:20', who: 'u_diego', note: 'Reworked the flip at 00:41 and pulled the title card back two beats.' },
        { n: 3, when: 'Yesterday, 16:05', who: 'u_diego', note: 'First pass at the ember grade. Changes requested by Noor.' },
        { n: 2, when: '18 Aug', who: 'u_diego', note: 'Assembly from the approved script.' },
        { n: 1, when: '16 Aug', who: 'u_avery', note: 'Generated cut from the trailer script.' }
      ],
      comments: [
        { id: 'c1', who: 'u_diego', at: '00:41', when: '2 hours ago', x: 34, y: 62, open: true,
          text: 'The flip lands two frames early — it reads as a cut, not a flip. Hold the pan a beat longer.' },
        { id: 'c2', who: 'u_noor', at: '01:34', when: '1 hour ago', x: 72, y: 30, open: true,
          text: 'Title card comes in on top of the sizzle. Let the room be quiet for a second before we ask for anything.' },
        { id: 'c3', who: 'u_priya', at: '00:12', when: 'Yesterday', x: 20, y: 44, open: false,
          text: 'Rim light on the pan is doing all the work here. Keep it.' }
      ]
    },
    {
      id: 'as_b30', name: 'Trailer — 30 second cut', short: '30s cut',
      kind: 'video', scene: 'flip', aspect: '16x9', lockup: 'title',
      lockupTitle: 'Cook it scared.', lockupEyebrow: 'Season Two · 0:30',
      spec: '1920 × 1080 · 0:30', size: '— not built', version: 1, state: 'blocked',
      from: 'as_trailer', fromAt: 'the master, 00:00–00:30', owner: 'u_diego',
      updated: 'Waiting', stage: 'Derivative',
      note: 'Cannot be cut until the master colour lock is approved. It is not queued behind a machine — it is queued behind a decision.',
      versions: [], comments: []
    },
    {
      id: 'as_sear', name: 'The Sear — vertical teaser', short: 'The Sear',
      kind: 'clip', scene: 'sear', aspect: '9x16', lockup: 'caption',
      caption: 'you want the pan hotter than you think',
      spec: '1080 × 1920 · 0:22', size: '88 MB', version: 2, state: 'changes',
      from: 'as_trailer', fromAt: '00:38–01:00', owner: 'u_diego', reviewer: 'u_diego',
      updated: 'Yesterday', stage: 'Derivative',
      note: 'Cut from the master at 00:38. Captions burned in.',
      versions: [
        { n: 2, when: 'Yesterday, 17:40', who: 'u_diego', note: 'Recut against master v3.' },
        { n: 1, when: '17 Aug', who: 'u_avery', note: 'First vertical pull.' }
      ],
      comments: [
        { id: 'c4', who: 'u_diego', at: '00:09', when: 'Yesterday', x: 50, y: 78, open: true,
          text: 'Caption covers the rim light. Move the burn-in up 90px or lose the second line.' }
      ]
    },
    {
      id: 'as_rise', name: 'The Rise — vertical teaser', short: 'The Rise',
      kind: 'clip', scene: 'loaf', aspect: '9x16', lockup: 'caption',
      caption: 'a starter you genuinely cannot kill',
      spec: '1080 × 1920 · 0:18', size: '74 MB', version: 1, state: 'review',
      from: 'as_trailer', fromAt: '01:06–01:24', owner: 'u_diego', reviewer: 'u_noor',
      updated: '4 hours ago', stage: 'Derivative',
      note: 'Cut from the master at 01:06.',
      versions: [{ n: 1, when: 'Today, 09:40', who: 'u_diego', note: 'First pull against master v4.' }],
      comments: []
    },
    {
      id: 'as_carousel', name: 'Six Techniques — carousel', short: 'Carousel',
      kind: 'carousel', doc: 'carousel', slideN: '04', docTitle: 'The Bone',
      spec: '1080 × 1350 · 6 slides', size: '4.2 MB', version: 1, state: 'review',
      from: 'as_keyart', fromAt: 'the key art set', owner: 'u_priya', reviewer: 'u_avery',
      updated: 'Today, 08:15', stage: 'Social',
      note: 'One slide per technique, built on the key art system.',
      versions: [{ n: 1, when: 'Today, 08:15', who: 'u_priya', note: 'First deck.' }],
      comments: [
        { id: 'c5', who: 'u_priya', at: 'Slide 4', when: '3 hours ago', x: 46, y: 40, open: true,
          text: 'Slide 4 is the only one with a hand in it. Either all six or none — right now it reads like a different deck wandered in.' }
      ]
    },
    {
      id: 'as_keyart', name: 'Season key art', short: 'Key art',
      kind: 'image', scene: 'flame', aspect: '16x9', lockup: 'title',
      lockupTitle: 'Kitchen Confidence', lockupEyebrow: 'Season Two',
      spec: '2400 × 1350', size: '3.1 MB', version: 2, state: 'approved',
      owner: 'u_priya', approvedBy: 'u_avery', approvedAt: '19 Aug, 14:22',
      updated: '19 Aug', stage: 'Design',
      note: 'The plate every other title treatment is built from.',
      versions: [
        { n: 2, when: '19 Aug, 14:02', who: 'u_priya', note: 'Dropped the second line, widened the rule.' },
        { n: 1, when: '18 Aug', who: 'u_priya', note: 'First direction.' }
      ],
      comments: []
    },
    {
      id: 'as_titles', name: 'Episode title cards', short: 'Title cards',
      kind: 'image', scene: 'knife', aspect: '16x9', lockup: 'episode',
      lockupTitle: 'The Blade', lockupEyebrow: 'One knife, four cuts', slideN: '5',
      spec: '1920 × 1080 · 6 cards', size: '9.4 MB', version: 3, state: 'approved',
      from: 'as_keyart', fromAt: 'the key art system', owner: 'u_priya',
      approvedBy: 'u_avery', approvedAt: '20 Aug, 10:04',
      updated: '20 Aug', stage: 'Design',
      note: 'Six cards, one per episode, on the key art system.',
      versions: [
        { n: 3, when: '20 Aug', who: 'u_priya', note: 'Numerals moved to the ember.' },
        { n: 2, when: '19 Aug', who: 'u_priya', note: 'Type scale corrected for mobile.' },
        { n: 1, when: '18 Aug', who: 'u_priya', note: 'First set.' }
      ],
      comments: []
    },
    {
      id: 'as_script', name: 'Trailer script', short: 'Script',
      kind: 'script', doc: 'script', docTitle: 'COLD OPEN — THE PAN',
      docLine: 'Everyone tells you to be gentle.', docFlag: true, page: '3',
      spec: '640 words · 3 pages', size: '18 KB', version: 6, state: 'approved',
      owner: 'u_avery', approvedBy: 'u_noor', approvedAt: '16 Aug, 09:30',
      updated: '16 Aug', stage: 'Script',
      note: 'Approved with one open note against line 42.',
      versions: [
        { n: 6, when: '16 Aug, 09:12', who: 'u_avery', note: 'Softened the safety claim on line 42.' },
        { n: 5, when: '15 Aug', who: 'u_avery', note: 'Tightened the cold open.' }
      ],
      comments: [
        { id: 'c6', who: 'u_noor', at: 'Line 42', when: '16 Aug', x: 30, y: 52, open: true,
          text: 'Change “kills every bacterium” to “gets the surface past the safe temperature”. The first is a claim we cannot make and I will not sign it.' }
      ]
    },
    {
      id: 'as_email', name: 'Season announcement — email', short: 'Email',
      kind: 'newsletter', doc: 'email', docTitle: 'Season two starts 14 September',
      spec: '600px · 1 send', size: '46 KB', version: 1, state: 'draft',
      from: 'as_script', fromAt: 'the trailer script', owner: 'u_avery',
      updated: '30 minutes ago', stage: 'Drafts',
      note: 'Draft. Nothing is scheduled and nothing is sent from here.',
      versions: [{ n: 1, when: 'Today, 10:50', who: 'u_avery', note: 'First draft from the script.' }],
      comments: []
    },
    {
      id: 'as_caps', name: 'Trailer captions', short: 'Captions',
      kind: 'caption', scene: 'sear', aspect: '16x9', lockup: 'caption',
      caption: 'six techniques. six episodes. no fear.',
      spec: 'SRT · English · 1:52', size: '11 KB', version: 2, state: 'approved',
      from: 'as_trailer', fromAt: 'the master audio', owner: 'u_diego',
      approvedBy: 'u_noor', approvedAt: '20 Aug, 16:40',
      updated: '20 Aug', stage: 'Master',
      note: 'Timed against master v3. Re-times automatically if the master changes length.',
      versions: [
        { n: 2, when: '20 Aug', who: 'u_diego', note: 'Re-timed against v3.' },
        { n: 1, when: '19 Aug', who: 'u_diego', note: 'First transcription.' }
      ],
      comments: []
    },
    {
      id: 'as_selects', name: 'Season two — selects', short: 'Selects',
      kind: 'sheet', doc: 'sheet', pick: 2, kill: 6, roll: 'ROLL 04',
      docTitle: 'KITCHEN CONFIDENCE — S2 SELECTS',
      spec: '10 frames · contact sheet', size: '2.8 MB', version: 1, state: 'approved',
      owner: 'u_diego', approvedBy: 'u_avery', approvedAt: '18 Aug',
      updated: '18 Aug', stage: 'Master',
      note: 'The frames the master was cut from. One ringed, one killed.',
      versions: [{ n: 1, when: '18 Aug', who: 'u_diego', note: 'Marked up after the assembly.' }],
      comments: []
    },

    /* ---------------------------------------------------------- paid media
       Advertisements the creator is making, from the same master. They are
       campaign deliverables like any other: versioned, reviewed, approved,
       and cut from the frame the trailer was cut from. `paid: true` is what
       groups them; `kind` stays the medium so the medium filters stay true. */
    {
      id: 'as_ad_meta', name: 'Meta feed ad — Six techniques', short: 'Meta feed ad',
      kind: 'image', paid: true, placement: 'Meta feed', scene: 'plate', aspect: '4x5', lockup: 'ad', ad: 'meta',
      headline: 'Six techniques. No fear.', cta: 'Watch the trailer', lockupEyebrow: 'Kitchen Confidence',
      spec: '1080 × 1350 · 2 variants', size: '2.4 MB', version: 2, state: 'review',
      from: 'as_keyart', fromAt: 'the key art plate', owner: 'u_priya', reviewer: 'u_avery',
      updated: '40 minutes ago', stage: 'Paid media',
      note: 'The paid version of the announcement. Same crop rules as the organic post, different words and one button.',
      versions: [
        { n: 2, when: 'Today, 10:35', who: 'u_priya', note: 'Shortened the headline and moved the button off the crust.' },
        { n: 1, when: 'Yesterday, 15:10', who: 'u_priya', note: 'First paid cut from the key art.' }
      ],
      comments: [
        { id: 'c9', who: 'u_avery', at: 'Headline', when: '20 minutes ago', x: 26, y: 68, open: true,
          text: 'Six techniques reads as a listicle. Try the tagline as the headline and let the technique count be the subhead.' }
      ]
    },
    {
      id: 'as_ad_story', name: 'Story and Reels ad — The Sear', short: 'Story ad',
      kind: 'clip', paid: true, placement: 'Instagram Story / Reels', scene: 'flip', aspect: '9x16', lockup: 'ad', ad: 'story',
      headline: 'Cook it scared.', cta: 'Watch now', lockupEyebrow: 'Kitchen Confidence',
      spec: '1080 × 1920 · 0:15', size: '31 MB', version: 1, state: 'approved',
      from: 'as_sear', fromAt: 'the vertical teaser, 00:04–00:19', owner: 'u_diego',
      approvedBy: 'u_noor', approvedAt: '20 Aug, 17:05', updated: '20 Aug', stage: 'Paid media',
      note: 'Fifteen seconds, safe areas respected, sound off by default.',
      versions: [{ n: 1, when: '20 Aug, 16:50', who: 'u_diego', note: 'Cut down from the teaser with the CTA end plate.' }],
      comments: []
    },
    {
      id: 'as_ad_tiktok', name: 'TikTok ad — hotter than you think', short: 'TikTok ad',
      kind: 'clip', paid: true, placement: 'TikTok in-feed', scene: 'hands', aspect: '9x16', lockup: 'ad', ad: 'tiktok',
      headline: 'Hotter than you think.', cta: 'See the season', lockupEyebrow: 'Kitchen Confidence',
      spec: '1080 × 1920 · 0:21', size: '38 MB', version: 1, state: 'draft',
      from: 'as_trailer', fromAt: 'the master, 01:02–01:23', owner: 'u_diego',
      updated: '15 minutes ago', stage: 'Paid media',
      note: 'Draft. Hook is in the first second; the platform version of the same cut, not a reformat of it.',
      versions: [{ n: 1, when: 'Today, 11:44', who: 'u_diego', note: 'First in-feed variation.' }],
      comments: []
    },
    {
      id: 'as_ad_preroll', name: 'YouTube pre-roll — 15 seconds', short: 'Pre-roll',
      kind: 'video', paid: true, placement: 'YouTube pre-roll', scene: 'flame', aspect: '16x9', lockup: 'ad', ad: 'preroll',
      headline: 'Season Two. 14 September.', cta: 'Subscribe', lockupEyebrow: 'Kitchen Confidence',
      spec: '1920 × 1080 · 0:15 · skippable', size: '44 MB', version: 1, state: 'changes',
      from: 'as_trailer', fromAt: 'the master, 00:00–00:15', owner: 'u_diego', reviewer: 'u_noor',
      updated: 'Today, 09:50', stage: 'Paid media',
      note: 'Skippable. The first five seconds have to work without the rest.',
      versions: [{ n: 1, when: 'Today, 09:30', who: 'u_diego', note: 'Pulled the opening fifteen from the master.' }],
      comments: [
        { id: 'c10', who: 'u_noor', at: '00:04', when: '1 hour ago', x: 58, y: 34, open: true,
          text: 'The date lands after the skip button appears. Move it to 00:03 or it is only ever seen by people who were going to watch anyway.' }
      ]
    },
    {
      id: 'as_ad_display', name: 'Display banner set', short: 'Banners',
      kind: 'image', paid: true, placement: 'Display network', scene: 'sear', aspect: '8x1', lockup: 'ad', ad: 'display', unit: [728, 90],
      headline: 'Cook it scared.', cta: 'Watch', lockupEyebrow: 'Kitchen Confidence',
      spec: '5 sizes · 728×90, 300×250, 160×600, 320×50, 970×250', size: '620 KB', version: 1, state: 'draft',
      from: 'as_keyart', fromAt: 'the key art plate', owner: 'u_priya',
      updated: 'Today, 08:40', stage: 'Paid media',
      sizes: [
        { label: '728 × 90', aspect: '8x1', unit: [728, 90], scene: 'sear' },
        { label: '300 × 250', aspect: '6x5', unit: [300, 250], scene: 'plate' },
        { label: '160 × 600', aspect: '4x15', unit: [160, 600], scene: 'flame' },
        { label: '320 × 50', aspect: '8x1', unit: [320, 50], scene: 'spice' },
        { label: '970 × 250', aspect: '21x9', unit: [970, 250], scene: 'flip' }
      ],
      note: 'One plate, five sizes. Each is a real crop of the same frame, not a squeeze of it.',
      versions: [{ n: 1, when: 'Today, 08:40', who: 'u_priya', note: 'First set across the five sizes.' }],
      comments: []
    },
    {
      id: 'as_ad_copy', name: 'Paid copy and CTA variants', short: 'Ad copy',
      kind: 'sheet', paid: true, placement: 'All placements',
      scene: 'quote', aspect: '16x9', lockup: 'ad', ad: 'copy',
      headline: 'Six techniques. No fear.', cta: 'Watch the trailer',
      headlineB: 'Cook it scared.', ctaB: 'Watch now', lockupEyebrow: 'Kitchen Confidence',
      spec: '8 headlines · 4 CTAs', size: '14 KB', version: 3, state: 'review',
      from: 'as_script', fromAt: 'the trailer script', owner: 'u_avery', reviewer: 'u_noor',
      updated: 'Today, 10:05', stage: 'Paid media',
      note: 'Eight headlines and four calls to action, one marked as the control. Nothing here is scheduled or bought from ProjectOne.',
      versions: [
        { n: 3, when: 'Today, 10:05', who: 'u_avery', note: 'Cut the two that promised results.' },
        { n: 2, when: 'Yesterday', who: 'u_avery', note: 'Added the four CTA variants.' },
        { n: 1, when: '19 Aug', who: 'u_avery', note: 'First set from the script.' }
      ],
      comments: []
    },
    {
      id: 'as_outline', name: 'Season two — production outline', short: 'Outline',
      kind: 'outline', doc: 'outline', docEyebrow: 'PRODUCTION OUTLINE',
      docTitle: 'Six techniques, six episodes',
      spec: '6 sections · 1 page', size: '9 KB', version: 1, state: 'approved',
      owner: 'u_avery', approvedBy: 'u_avery', approvedAt: '10 Aug, 14:22',
      updated: '10 Aug', stage: 'Plan',
      note: 'What the planning agent returned, after the quality check.',
      versions: [{ n: 1, when: '10 Aug, 14:22', who: 'u_avery', note: 'Returned by the planning agent.' }],
      comments: []
    }
  ];

  PO.assetById = function (id) {
    for (var i = 0; i < PO.ASSETS.length; i++) if (PO.ASSETS[i].id === id) return PO.ASSETS[i];
    return null;
  };
  PO.personById = function (id) {
    var p = PO.CAMPAIGN.people;
    for (var i = 0; i < p.length; i++) if (p[i].id === id) return p[i];
    return { id: id, name: 'Someone', initials: '?', role: '' };
  };

  /* ======================================================================
     SCENE DEFINITIONS

     Canonical space is 1600 x 900. `focus` is the point every crop centres
     on, so a vertical teaser keeps the subject instead of the tablecloth.
     ====================================================================== */
  var SCENE_META = {
    sear:  { focus: [770, 470], label: 'The sear — wide' },
    over:  { focus: [800, 430], label: 'Overhead — the crust' },
    loaf:  { focus: [820, 470], label: 'The rise — low key' },
    flame: { focus: [800, 560], label: 'Live flame — under the pan' },
    knife: { focus: [800, 470], label: 'One knife — macro' },
    flip:  { focus: [740, 470], label: 'The flip — in the air' },
    spice: { focus: [856, 500], label: 'Seasoning — macro' },
    hands: { focus: [740, 570], label: 'Hands at work' },
    plate: { focus: [896, 500], label: 'Plated — the result' },
    quote: { focus: [700, 450], label: 'Editorial plate' }
  };

  var DEFS = [
    /* One warm pool of light doing all the work, and a vignette eating the
       corners. Every scene is graded the same way, which is why they read as
       one shoot rather than four drawings. */
    '<radialGradient id="g-pool" cx="0.5" cy="0.5" r="0.5">',
    '<stop offset="0" stop-color="#FFC482" stop-opacity="0.5"/><stop offset="0.45" stop-color="#C9772F" stop-opacity="0.2"/><stop offset="1" stop-color="#8A4A18" stop-opacity="0"/>',
    '</radialGradient>',

    '<radialGradient id="g-vignette" cx="0.5" cy="0.46" r="0.74">',
    '<stop offset="0" stop-color="#060504" stop-opacity="0"/><stop offset="0.58" stop-color="#060504" stop-opacity="0.16"/><stop offset="1" stop-color="#060504" stop-opacity="0.8"/>',
    '</radialGradient>',

    '<linearGradient id="g-scrim-left" x1="0" y1="0" x2="1" y2="0">',
    '<stop offset="0" stop-color="#0A0806" stop-opacity="0.82"/><stop offset="0.55" stop-color="#0A0806" stop-opacity="0.38"/><stop offset="1" stop-color="#0A0806" stop-opacity="0"/>',
    '</linearGradient>',

    '<radialGradient id="g-soft" cx="0.5" cy="0.5" r="0.5">',
    '<stop offset="0" stop-color="#050403" stop-opacity="0.72"/><stop offset="0.5" stop-color="#050403" stop-opacity="0.34"/><stop offset="1" stop-color="#050403" stop-opacity="0"/>',
    '</radialGradient>',

    '<radialGradient id="g-ember" cx="0.5" cy="0.5" r="0.5">',
    '<stop offset="0" stop-color="#FF7A34" stop-opacity="0.68"/><stop offset="0.42" stop-color="#E2511F" stop-opacity="0.3"/><stop offset="1" stop-color="#E2511F" stop-opacity="0"/>',
    '</radialGradient>',
    '<linearGradient id="g-flame" x1="0" y1="1" x2="0" y2="0">',
    '<stop offset="0" stop-color="#FFF0D0" stop-opacity="0.96"/>',
    '<stop offset="0.32" stop-color="#FF9046" stop-opacity="0.92"/>',
    '<stop offset="0.68" stop-color="#E2511F" stop-opacity="0.62"/>',
    '<stop offset="1" stop-color="#E2511F" stop-opacity="0"/>',
    '</linearGradient>',
    '<radialGradient id="g-ember-hot" cx="0.5" cy="0.5" r="0.5">',
    '<stop offset="0" stop-color="#FFE3B4" stop-opacity="0.95"/><stop offset="0.35" stop-color="#FF9046" stop-opacity="0.55"/><stop offset="1" stop-color="#FF9046" stop-opacity="0"/>',
    '</radialGradient>',

    '<linearGradient id="g-iron" x1="0.1" y1="0" x2="0.7" y2="1">',
    '<stop offset="0" stop-color="#2B2521"/><stop offset="0.4" stop-color="#141110"/><stop offset="1" stop-color="#0A0908"/>',
    '</linearGradient>',

    /* The crust is the brightest object in every frame. It is the only thing
       in the kitchen that is actually emitting, so it gets the widest range. */
    '<radialGradient id="g-crust" cx="0.4" cy="0.3" r="0.78">',
    '<stop offset="0" stop-color="#FFD692"/><stop offset="0.3" stop-color="#E29B45"/><stop offset="0.62" stop-color="#A85C1B"/><stop offset="0.88" stop-color="#5E2E0A"/><stop offset="1" stop-color="#38190400"/>',
    '</radialGradient>',
    '<radialGradient id="g-crust-2" cx="0.42" cy="0.34" r="0.74">',
    '<stop offset="0" stop-color="#FFE0A6"/><stop offset="0.34" stop-color="#E9A64E"/><stop offset="0.7" stop-color="#9E5417"/><stop offset="1" stop-color="#4A2207"/>',
    '</radialGradient>',

    '<linearGradient id="g-steam" x1="0" y1="1" x2="0" y2="0">',
    '<stop offset="0" stop-color="#FFE7C2" stop-opacity="0.62"/><stop offset="0.5" stop-color="#FFE7C2" stop-opacity="0.24"/><stop offset="1" stop-color="#FFE7C2" stop-opacity="0"/>',
    '</linearGradient>',

    '<linearGradient id="g-steel" x1="0" y1="0" x2="0.15" y2="1">',
    '<stop offset="0" stop-color="#5A544C"/><stop offset="0.4" stop-color="#2A2622"/><stop offset="1" stop-color="#100E0D"/>',
    '</linearGradient>',

    '<linearGradient id="g-walnut" x1="0" y1="0" x2="0.25" y2="1">',
    '<stop offset="0" stop-color="#48301D"/><stop offset="0.55" stop-color="#2C1C10"/><stop offset="1" stop-color="#160D07"/>',
    '</linearGradient>',

    /* Haze in the light beam. Two stops and the room gets air in it. */
    '<linearGradient id="g-haze" x1="0" y1="0" x2="0.6" y2="1">',
    '<stop offset="0" stop-color="#FFD9A0" stop-opacity="0.14"/><stop offset="1" stop-color="#FFD9A0" stop-opacity="0"/>',
    '</linearGradient>',

    '<linearGradient id="g-scrim" x1="0" y1="0" x2="0" y2="1">',
    '<stop offset="0" stop-color="#0A0806" stop-opacity="0"/><stop offset="0.45" stop-color="#0A0806" stop-opacity="0.38"/><stop offset="1" stop-color="#0A0806" stop-opacity="0.82"/>',
    '</linearGradient>',
    '<linearGradient id="g-scrim-full" x1="0" y1="0" x2="0.3" y2="1">',
    '<stop offset="0" stop-color="#0A0806" stop-opacity="0.34"/><stop offset="1" stop-color="#0A0806" stop-opacity="0.72"/>',
    '</linearGradient>',

    /* Skin, in a kitchen lit by one warm source. Hands are drawn as
       silhouettes with a lit edge for the same reason the pan is: a filled
       shape reads as a hand, a rendered one reads as a waxwork. */
    '<linearGradient id="g-skin" x1="0.2" y1="0" x2="0.8" y2="1">',
    '<stop offset="0" stop-color="#7A5740"/><stop offset="0.45" stop-color="#452F20"/><stop offset="1" stop-color="#1E1409"/>',
    '</linearGradient>',

    /* Glazed ceramic. The one ivory object in a campaign shot on ink, so it
       carries the whole tonal contrast of the plated frame by itself. */
    '<radialGradient id="g-ceramic" cx="0.36" cy="0.28" r="0.86">',
    '<stop offset="0" stop-color="#FBF4E6"/><stop offset="0.42" stop-color="#E4D8C0"/><stop offset="0.76" stop-color="#B9A88C"/><stop offset="1" stop-color="#6E624F"/>',
    '</radialGradient>',

    '<linearGradient id="g-page" x1="0" y1="0" x2="0.4" y2="1">',
    '<stop offset="0" stop-color="#FFFDF8"/><stop offset="1" stop-color="#F1EADC"/>',
    '</linearGradient>'
  ].join('');

  /* ---------------------------------------------------------------- scenes

     Every scene is built the same way, in this order, because that is the
     order light actually arrives in:

       base darkness -> the pool -> haze -> contact shadow -> the subject in
       silhouette -> what is emitting -> the rim light -> speculars -> vignette

     The rim light is the load-bearing step. A dark shape on a dark ground is
     a blob; the same shape with one bright edge is a photograph.
     ---------------------------------------------------------------------- */

  function steam(x, y, drift, w, o) {
    return '<path d="M' + x + ' ' + y +
      ' C' + (x - 34) + ' ' + (y - 110) + ',' + (x + 46) + ' ' + (y - 156) + ',' + (x + drift) + ' ' + (y - 250) +
      ' C' + (x + drift - 40) + ' ' + (y - 330) + ',' + (x + drift + 38) + ' ' + (y - 372) + ',' + (x + drift + 6) + ' ' + (y - 452) + '"' +
      ' fill="none" stroke="url(#g-steam)" stroke-width="' + w + '" stroke-linecap="round" opacity="' + o + '"/>';
  }
  function motes(list) {
    var out = '<g fill="#FFE7C2">';
    for (var i = 0; i < list.length; i++) {
      out += '<circle cx="' + list[i][0] + '" cy="' + list[i][1] + '" r="' + list[i][2] + '" opacity="' + list[i][3] + '"/>';
    }
    return out + '</g>';
  }

  /* A hand. Fingers are separate capsules with real gaps between them, because
     a single closed blob reads as a mitten at any size below a hundred pixels —
     and the gaps are what the rim light gets to describe. Built as a function
     so the two hands in a frame are the same hand from two angles rather than
     two different drawings that happen to be near each other. */
  function hand(cx, cy, rot, sc, flip) {
    var lens = [1.0, 1.14, 1.06, 0.86], i, out;
    out = '<g transform="translate(' + cx + ' ' + cy + ') rotate(' + rot + ') scale(' +
      (flip ? -sc : sc) + ' ' + sc + ')">';
    out += '<path d="M-104 30 C-104 -34 -64 -76 0 -76 C66 -76 106 -34 106 30 L106 260 L-104 260 Z" fill="url(#g-skin)"/>';
    out += '<rect x="-168" y="-16" width="46" height="164" rx="23" transform="rotate(-40 -145 66)" fill="url(#g-skin)"/>';
    for (i = 0; i < 4; i++) {
      out += '<rect x="' + (-88 + i * 56) + '" y="' + Math.round(-76 - 156 * lens[i]) +
        '" width="46" height="' + Math.round(156 * lens[i] + 110) + '" rx="23" fill="url(#g-skin)"/>';
    }
    /* the lit edge: one arc over each fingertip and a knuckle line across */
    out += '<g fill="none" stroke="#E8B27A" stroke-width="9" stroke-linecap="round" opacity="0.72">';
    for (i = 0; i < 4; i++) {
      var fx = -88 + i * 56, ft = Math.round(-76 - 156 * lens[i]) + 23;
      out += '<path d="M' + (fx + 2) + ' ' + ft + ' A23 23 0 0 1 ' + (fx + 44) + ' ' + ft + '"/>';
    }
    out += '</g>';
    out += '<path d="M-92 -34 C-40 -58 44 -58 98 -34" fill="none" stroke="#C08A52" stroke-width="7" opacity="0.42" stroke-linecap="round"/>';
    out += '<path d="M-150 8 C-176 46 -170 96 -140 126" fill="none" stroke="#E8B27A" stroke-width="8" opacity="0.6" stroke-linecap="round"/>';
    return out + '</g>';
  }

  var SC_SEAR =
    '<g id="sc-sear">' +
      '<rect width="1600" height="900" fill="#100D0B"/>' +
      '<ellipse cx="700" cy="400" rx="900" ry="640" fill="url(#g-pool)"/>' +
      /* the counter catching the pool, no hard horizon */
      '<ellipse cx="740" cy="740" rx="1100" ry="300" fill="#C9772F" opacity="0.12"/>' +
      '<path d="M0 900 L0 300 L620 130 L1600 300 L1600 900 Z" fill="url(#g-haze)"/>' +
      steam(716, 462, -34, 20, 0.85) + steam(812, 446, 42, 15, 0.7) + steam(762, 472, 4, 11, 0.5) +
      '<ellipse cx="806" cy="662" rx="470" ry="86" fill="url(#g-soft)"/>' +
      '<ellipse cx="640" cy="644" rx="330" ry="74" fill="url(#g-ember)"/>' +
      /* handle, then body — the join disappears behind the rim */
      '<path d="M1040 486 C1168 462 1288 438 1418 420 L1432 470 C1306 490 1188 518 1062 548 Z" fill="#0C0A09"/>' +
      '<path d="M1046 490 C1172 466 1290 444 1414 426" fill="none" stroke="#C79A62" stroke-width="5" opacity="0.5" stroke-linecap="round"/>' +
      '<ellipse cx="770" cy="540" rx="346" ry="144" fill="#0A0908"/>' +
      '<ellipse cx="770" cy="532" rx="330" ry="132" fill="url(#g-iron)"/>' +
      '<ellipse cx="770" cy="540" rx="292" ry="108" fill="#080706"/>' +
      /* what is cooking — the only bright object, with a real char edge */
      '<ellipse cx="772" cy="538" rx="256" ry="94" fill="#2A1204"/>' +
      '<path d="M520 536 C520 486 632 448 772 448 C918 448 1026 486 1026 538 C1026 590 914 630 772 630 C630 630 520 590 520 536 Z" fill="url(#g-crust-2)"/>' +
      '<g fill="#3A1A05" opacity="0.5"><ellipse cx="880" cy="574" rx="86" ry="24"/><ellipse cx="668" cy="580" rx="58" ry="18"/><ellipse cx="806" cy="486" rx="44" ry="13"/></g>' +
      '<g fill="#FFE8BC" opacity="0.72"><ellipse cx="676" cy="508" rx="46" ry="14" opacity="0.42"/><ellipse cx="640" cy="546" rx="14" ry="5"/><ellipse cx="710" cy="578" rx="9" ry="4"/><ellipse cx="858" cy="504" rx="11" ry="4"/></g>' +
      /* the rim light. This one stroke is what makes it read as a photograph. */
      '<path d="M442 522 A330 132 0 0 1 1098 522" fill="none" stroke="#FFCE8E" stroke-width="7" opacity="0.9" stroke-linecap="round"/>' +
      '<path d="M500 486 A330 132 0 0 1 760 402" fill="none" stroke="#FFF1D6" stroke-width="5" opacity="0.55" stroke-linecap="round"/>' +
      '<ellipse cx="622" cy="638" rx="132" ry="28" fill="url(#g-ember-hot)"/>' +
      /* one herb, in shadow, because a real set has a detail you did not need */
      '<g fill="#141A0E" opacity="0.9">' +
        '<path d="M1006 604 C1046 574 1102 570 1136 586 C1098 616 1042 620 1006 604 Z"/>' +
        '<path d="M1064 634 C1092 606 1140 600 1170 612 C1140 640 1094 646 1064 634 Z"/>' +
      '</g>' +
      '<path d="M1012 600 C1052 572 1104 568 1134 584" fill="none" stroke="#8FA36A" stroke-width="3" opacity="0.55"/>' +
      motes([[430, 300, 4, 0.4], [1180, 250, 3, 0.3], [1310, 520, 3, 0.22], [300, 560, 3, 0.25], [980, 210, 4, 0.22]]) +
      '<rect width="1600" height="900" fill="url(#g-vignette)"/>' +
    '</g>';

  var SC_OVER =
    '<g id="sc-over">' +
      '<rect width="1600" height="900" fill="#0E0C0A"/>' +
      '<ellipse cx="640" cy="300" rx="880" ry="760" fill="url(#g-pool)"/>' +
      /* the surface itself, seen straight down */
      '<g opacity="0.16" stroke="#C9772F" stroke-width="3">' +
        '<path d="M0 210 L1600 150"/><path d="M0 470 L1600 420"/><path d="M0 740 L1600 700"/>' +
      '</g>' +
      '<ellipse cx="812" cy="470" rx="400" ry="378" fill="url(#g-soft)"/>' +
      '<circle cx="800" cy="440" r="316" fill="#0A0908"/>' +
      '<circle cx="800" cy="440" r="296" fill="url(#g-iron)"/>' +
      '<circle cx="800" cy="440" r="258" fill="#080706"/>' +
      '<circle cx="800" cy="440" r="228" fill="#2A1204"/>' +
      '<circle cx="800" cy="440" r="222" fill="url(#g-crust)"/>' +
      '<path d="M690 348 C762 424 842 458 918 532" fill="none" stroke="#3A1A05" stroke-width="16" opacity="0.55" stroke-linecap="round"/>' +
      '<path d="M914 342 C846 420 764 452 690 528" fill="none" stroke="#3A1A05" stroke-width="16" opacity="0.55" stroke-linecap="round"/>' +
      '<circle cx="800" cy="440" r="222" fill="none" stroke="#4A2207" stroke-width="18" opacity="0.4"/>' +
      '<g fill="#3A1A05" opacity="0.42"><ellipse cx="906" cy="546" rx="86" ry="42" transform="rotate(-18 906 546)"/><ellipse cx="662" cy="558" rx="62" ry="30"/><ellipse cx="694" cy="316" rx="54" ry="26"/></g>' +
      '<g fill="#6E3409" opacity="0.3"><circle cx="856" cy="380" r="17"/><circle cx="742" cy="512" r="13"/><circle cx="890" cy="470" r="10"/><circle cx="646" cy="424" r="11"/></g>' +
      '<ellipse cx="716" cy="368" rx="76" ry="54" fill="#FFE8BC" opacity="0.24"/>' +
      '<g fill="#FFE8BC" opacity="0.5"><ellipse cx="700" cy="352" rx="12" ry="8"/><ellipse cx="766" cy="330" rx="8" ry="6"/></g>' +
      /* rim arc on the lit side only */
      '<path d="M566 296 A300 300 0 0 1 940 168" fill="none" stroke="#FFCE8E" stroke-width="8" opacity="0.85" stroke-linecap="round"/>' +
      '<path d="M508 520 A300 300 0 0 0 640 682" fill="none" stroke="#B0793C" stroke-width="5" opacity="0.4" stroke-linecap="round"/>' +
      /* the knife, clear of the pan, one hard specular down the edge */
      '<g transform="rotate(-19 1420 640)">' +
        '<path d="M1160 618 L1470 600 C1502 600 1502 656 1470 656 L1160 640 Z" fill="url(#g-steel)"/>' +
        '<path d="M1166 622 L1466 606" fill="none" stroke="#FFF3DF" stroke-width="5" opacity="0.85"/>' +
        '<rect x="1000" y="608" width="164" height="44" rx="16" fill="url(#g-walnut)"/>' +
        '<path d="M1006 614 L1158 614" fill="none" stroke="#C79A62" stroke-width="3" opacity="0.4"/>' +
      '</g>' +
      /* salt, fully in frame */
      '<circle cx="286" cy="742" r="112" fill="#0A0908"/>' +
      '<circle cx="286" cy="742" r="98" fill="#1A1614"/>' +
      '<circle cx="286" cy="736" r="76" fill="#E8D9BE" opacity="0.72"/>' +
      '<path d="M188 700 A112 112 0 0 1 300 630" fill="none" stroke="#FFCE8E" stroke-width="6" opacity="0.6" stroke-linecap="round"/>' +
      motes([[452, 812, 6, 0.5], [500, 782, 4, 0.4], [420, 856, 4, 0.32], [536, 838, 5, 0.36], [1180, 300, 4, 0.28], [340, 300, 3, 0.3]]) +
      '<rect width="1600" height="900" fill="url(#g-vignette)"/>' +
    '</g>';

  var SC_LOAF =
    '<g id="sc-loaf">' +
      '<rect width="1600" height="900" fill="#0D0B0A"/>' +
      '<ellipse cx="480" cy="300" rx="820" ry="660" fill="url(#g-pool)"/>' +
      '<path d="M0 0 L520 0 L1180 900 L0 900 Z" fill="url(#g-haze)"/>' +
      '<path d="M300 600 L1420 556 C1470 554 1470 706 1420 706 L300 706 Z" fill="url(#g-walnut)"/>' +
      '<path d="M304 604 L1418 560" fill="none" stroke="#C79A62" stroke-width="4" opacity="0.42"/>' +
      '<ellipse cx="838" cy="612" rx="410" ry="60" fill="url(#g-soft)"/>' +
      /* loaf: one closed silhouette, then light along the top-left only */
      '<path d="M462 600 C462 428 636 336 838 336 C1040 336 1214 428 1214 600 Z" fill="#0A0807"/>' +
      '<path d="M478 598 C478 440 644 354 838 354 C1032 354 1198 440 1198 598 Z" fill="url(#g-crust)"/>' +
      '<path d="M478 598 C478 440 644 354 838 354" fill="none" stroke="#FFD9A0" stroke-width="10" opacity="0.85" stroke-linecap="round"/>' +
      /* the ear — a lifted crescent, lit on its upper lip and dark beneath */
      '<path d="M596 476 C700 402 906 396 1052 448 C1030 494 986 506 942 490 C856 458 706 464 620 514 Z" fill="#0F0B08"/>' +
      '<path d="M600 472 C704 398 908 392 1050 444" fill="none" stroke="#FFE2AE" stroke-width="9" opacity="0.9" stroke-linecap="round"/>' +
      '<path d="M624 512 C716 460 870 452 950 488" fill="none" stroke="#8A4A18" stroke-width="7" opacity="0.55" stroke-linecap="round"/>' +
      /* two more scores and a shadow under the ear: without them the
         silhouette reads as a dome rather than as a scored loaf */
      '<path d="M666 560 C760 520 906 516 1006 546" fill="none" stroke="#4A2207" stroke-width="9" opacity="0.42" stroke-linecap="round"/>' +
      '<path d="M534 552 C570 520 620 502 668 494" fill="none" stroke="#4A2207" stroke-width="7" opacity="0.3" stroke-linecap="round"/>' +
      '<g fill="#3A1A05" opacity="0.4"><ellipse cx="1030" cy="552" rx="128" ry="38"/><ellipse cx="712" cy="578" rx="98" ry="28"/><ellipse cx="880" cy="596" rx="70" ry="18"/></g>' +
      '<g fill="#FFE8BC" opacity="0.28"><ellipse cx="742" cy="426" rx="9" ry="6"/><ellipse cx="820" cy="410" rx="7" ry="5"/><ellipse cx="900" cy="424" rx="8" ry="5"/><ellipse cx="668" cy="454" rx="6" ry="4"/><ellipse cx="972" cy="452" rx="6" ry="4"/></g>' +
      motes([[352, 716, 6, 0.5], [420, 752, 4, 0.38], [1288, 706, 5, 0.34], [1218, 744, 3, 0.3], [1348, 668, 4, 0.26], [520, 250, 4, 0.3], [980, 210, 3, 0.22]]) +
      '<rect width="1600" height="900" fill="url(#g-vignette)"/>' +
    '</g>';

  /* LIVE FLAME. This used to be an ember field with nothing in it, which at
     thumbnail size read as an orange smudge rather than as fire. Fire needs
     something to burn against: a burner ring, a pan bottom, and tongues that
     actually have shape. The heat still owns the frame — it just has a subject
     under it now. */
  var SC_FLAME =
    '<g id="sc-flame">' +
      '<rect width="1600" height="900" fill="#100D0C"/>' +
      '<ellipse cx="800" cy="780" rx="860" ry="470" fill="url(#g-ember)"/>' +
      /* the hob: a dark ring the fire sits on, so the light has an origin */
      '<ellipse cx="800" cy="806" rx="430" ry="106" fill="#0A0807"/>' +
      '<ellipse cx="800" cy="798" rx="404" ry="94" fill="url(#g-iron)"/>' +
      '<path d="M396 790 A404 94 0 0 1 1204 790" fill="none" stroke="#FFCE8E" stroke-width="6" opacity="0.55" stroke-linecap="round"/>' +
      /* the pan bottom, entering from the top and cropped — the fire is
         underneath something, which is the entire point of a flame frame */
      '<path d="M470 0 L1130 0 L1130 372 C1130 442 982 486 800 486 C618 486 470 442 470 372 Z" fill="#0B0A09"/>' +
      '<ellipse cx="800" cy="372" rx="330" ry="112" fill="url(#g-iron)"/>' +
      '<path d="M478 356 A330 112 0 0 0 1122 356" fill="none" stroke="#FF9046" stroke-width="9" opacity="0.75" stroke-linecap="round"/>' +
      '<path d="M540 424 A330 112 0 0 0 1060 424" fill="none" stroke="#FFCE8E" stroke-width="5" opacity="0.35" stroke-linecap="round"/>' +
      /* tongues. Closed shapes with a hot core, not strokes — a stroke bends,
         a flame tapers. */
      '<g fill="url(#g-flame)">' +
        '<path d="M548 806 C500 664 604 596 588 462 C688 556 694 686 664 782 C702 700 714 630 700 566 C778 664 772 782 728 826 Z"/>' +
        '<path d="M952 818 C898 672 1008 600 992 458 C1096 556 1102 690 1070 790 C1108 706 1120 634 1106 570 C1188 670 1180 792 1134 834 Z"/>' +
        '<path d="M752 832 C688 656 812 566 794 404 C912 522 920 686 886 800 C930 700 944 616 928 542 C1020 660 1010 802 962 848 Z"/>' +
      '</g>' +
      /* the hot core, where the gas is actually burning */
      '<g fill="#FFE0A8" opacity="0.62">' +
        '<path d="M592 792 C566 700 616 654 610 574 C660 632 664 720 646 780 Z"/>' +
        '<path d="M996 802 C968 706 1022 660 1016 576 C1068 634 1072 726 1054 788 Z"/>' +
        '<path d="M798 818 C762 690 824 626 814 520 C880 600 886 726 862 802 Z"/>' +
      '</g>' +
      /* and the light that fire throws back up onto the pan it is heating */
      '<ellipse cx="800" cy="470" rx="360" ry="120" fill="url(#g-ember-hot)" opacity="0.5"/>' +
      '<ellipse cx="800" cy="840" rx="330" ry="120" fill="url(#g-ember-hot)"/>' +
      motes([[612, 528, 5, 0.85], [906, 470, 4, 0.6], [760, 402, 4, 0.42], [1024, 560, 5, 0.55], [520, 606, 4, 0.5], [700, 318, 3, 0.3], [880, 280, 3, 0.22], [1140, 450, 3, 0.3], [420, 470, 3, 0.28]]) +
      '<rect width="1600" height="900" fill="url(#g-vignette)"/>' +
    '</g>';

  var SC_KNIFE =
    '<g id="sc-knife">' +
      '<rect width="1600" height="900" fill="#0C0A09"/>' +
      '<ellipse cx="900" cy="380" rx="860" ry="640" fill="url(#g-pool)"/>' +
      '<path d="M0 0 L700 0 L1600 760 L1600 900 L900 900 Z" fill="url(#g-haze)"/>' +
      '<ellipse cx="800" cy="600" rx="520" ry="120" fill="url(#g-soft)"/>' +
      '<g transform="rotate(-14 800 480)">' +
        '<path d="M420 448 L1120 414 C1180 414 1180 528 1120 528 L420 494 Z" fill="url(#g-steel)"/>' +
        '<path d="M430 456 L1112 424" fill="none" stroke="#FFF6E4" stroke-width="8" opacity="0.95" stroke-linecap="round"/>' +
        '<path d="M440 486 L1100 456" fill="none" stroke="#FFCE8E" stroke-width="3" opacity="0.3"/>' +
        '<rect x="150" y="430" width="290" height="82" rx="30" fill="url(#g-walnut)"/>' +
        '<path d="M170 442 L426 442" fill="none" stroke="#C79A62" stroke-width="4" opacity="0.42"/>' +
        '<circle cx="222" cy="472" r="9" fill="#C79A62" opacity="0.5"/><circle cx="330" cy="470" r="9" fill="#C79A62" opacity="0.5"/>' +
      '</g>' +
      '<g fill="#141A0E" opacity="0.92">' +
        '<path d="M1140 660 C1196 620 1276 614 1324 638 C1268 680 1188 686 1140 660 Z"/>' +
        '<path d="M1236 712 C1276 676 1344 668 1386 686 C1344 724 1278 730 1236 712 Z"/>' +
      '</g>' +
      '<path d="M1148 654 C1204 616 1276 612 1320 634" fill="none" stroke="#8FA36A" stroke-width="4" opacity="0.6"/>' +
      motes([[380, 690, 5, 0.4], [520, 730, 4, 0.32], [1420, 300, 4, 0.3], [260, 320, 3, 0.28], [1300, 220, 3, 0.22]]) +
      '<rect width="1600" height="900" fill="url(#g-vignette)"/>' +
    '</g>';

  /* THE FLIP — the only set-up with time in it. The pan is tilted, the food is
     in the air, and three arcs carry it there. Motion is DRAWN, not blurred:
     a blur at 40px is dirt on the lens, an arc at 40px is a flip. */
  var SC_FLIP =
    '<g id="sc-flip">' +
      '<rect width="1600" height="900" fill="#0F0C0B"/>' +
      '<ellipse cx="720" cy="340" rx="900" ry="660" fill="url(#g-pool)"/>' +
      '<path d="M0 900 L0 220 L560 70 L1600 250 L1600 900 Z" fill="url(#g-haze)"/>' +
      '<ellipse cx="700" cy="792" rx="1040" ry="230" fill="#C9772F" opacity="0.1"/>' +
      /* the burner, low and hot, so the throw has a reason to exist */
      '<ellipse cx="690" cy="744" rx="320" ry="76" fill="url(#g-ember)"/>' +
      '<ellipse cx="690" cy="752" rx="150" ry="36" fill="url(#g-ember-hot)"/>' +
      /* the arc the food travelled, drawn behind everything it passed */
      '<g fill="none" stroke="#FFCE8E" stroke-linecap="round">' +
        '<path d="M540 604 C598 372 852 288 1046 396" stroke-width="4" opacity="0.2"/>' +
        '<path d="M576 622 C632 412 856 336 1030 428" stroke-width="3" opacity="0.13"/>' +
        '<path d="M508 590 C572 340 866 246 1074 372" stroke-width="2" opacity="0.1"/>' +
      '</g>' +
      /* airborne. Seven pieces on that arc, each lit on the edge facing the pan */
      '<g>' +
        '<ellipse cx="612" cy="452" rx="62" ry="34" transform="rotate(-24 612 452)" fill="url(#g-crust-2)"/>' +
        '<path d="M556 440 A62 34 0 0 1 664 428" fill="none" stroke="#FFE8BC" stroke-width="5" opacity="0.8" stroke-linecap="round" transform="rotate(-24 612 452)"/>' +
        '<ellipse cx="742" cy="368" rx="54" ry="30" transform="rotate(14 742 368)" fill="url(#g-crust)"/>' +
        '<path d="M692 358 A54 30 0 0 1 790 350" fill="none" stroke="#FFE8BC" stroke-width="5" opacity="0.75" stroke-linecap="round" transform="rotate(14 742 368)"/>' +
        '<ellipse cx="880" cy="342" rx="46" ry="26" transform="rotate(-38 880 342)" fill="url(#g-crust-2)"/>' +
        '<path d="M838 334 A46 26 0 0 1 920 328" fill="none" stroke="#FFE8BC" stroke-width="4" opacity="0.7" stroke-linecap="round" transform="rotate(-38 880 342)"/>' +
        '<ellipse cx="994" cy="404" rx="38" ry="22" transform="rotate(26 994 404)" fill="url(#g-crust)"/>' +
        '<ellipse cx="676" cy="524" rx="34" ry="19" transform="rotate(8 676 524)" fill="url(#g-crust-2)"/>' +
        '<ellipse cx="820" cy="450" rx="27" ry="15" transform="rotate(-12 820 450)" fill="url(#g-crust)"/>' +
        '<ellipse cx="930" cy="470" rx="20" ry="12" fill="#B8701F" opacity="0.8"/>' +
      '</g>' +
      /* the pan, caught at the top of the throw */
      '<g transform="rotate(-27 690 640)">' +
        '<path d="M972 606 C1104 578 1228 558 1364 542 L1378 596 C1248 614 1126 642 996 672 Z" fill="#0C0A09"/>' +
        '<path d="M978 610 C1108 584 1230 564 1360 548" fill="none" stroke="#C79A62" stroke-width="5" opacity="0.5" stroke-linecap="round"/>' +
        '<ellipse cx="690" cy="648" rx="336" ry="122" fill="#0A0908"/>' +
        '<ellipse cx="690" cy="640" rx="318" ry="112" fill="url(#g-iron)"/>' +
        '<ellipse cx="690" cy="648" rx="280" ry="90" fill="#080706"/>' +
        '<ellipse cx="700" cy="654" rx="212" ry="62" fill="#2A1204" opacity="0.9"/>' +
        '<path d="M372 630 A318 112 0 0 1 1008 630" fill="none" stroke="#FFCE8E" stroke-width="8" opacity="0.92" stroke-linecap="round"/>' +
        '<path d="M430 596 A318 112 0 0 1 680 520" fill="none" stroke="#FFF1D6" stroke-width="5" opacity="0.5" stroke-linecap="round"/>' +
      '</g>' +
      /* the hand that threw it, entering low right and lit on the knuckles only */
      '<g>' +
        '<path d="M1600 900 L1230 792 C1150 768 1108 700 1148 654 C1186 610 1268 620 1316 656 L1600 800 Z" fill="url(#g-skin)"/>' +
        '<path d="M1152 656 C1190 614 1266 624 1312 660" fill="none" stroke="#E0A468" stroke-width="6" opacity="0.65" stroke-linecap="round"/>' +
        '<path d="M1198 700 C1236 668 1290 672 1330 700" fill="none" stroke="#C08A52" stroke-width="4" opacity="0.35" stroke-linecap="round"/>' +
      '</g>' +
      '<ellipse cx="620" cy="736" rx="140" ry="30" fill="url(#g-ember-hot)"/>' +
      motes([[420, 300, 5, 0.42], [1160, 230, 4, 0.34], [1300, 470, 3, 0.24], [300, 520, 3, 0.26], [960, 190, 4, 0.24], [530, 250, 3, 0.2]]) +
      '<rect width="1600" height="900" fill="url(#g-vignette)"/>' +
    '</g>';

  /* THE MACRO — seasoning falling. The nearest thing this campaign has to an
     abstract, and the only frame where the subject is smaller than a coin.
     Bokeh does the depth: three out-of-focus discs behind, hard grains in front. */
  var SC_SPICE =
    '<g id="sc-spice">' +
      '<rect width="1600" height="900" fill="#0B0908"/>' +
      '<ellipse cx="820" cy="420" rx="760" ry="620" fill="url(#g-pool)"/>' +
      /* out of focus, behind: the rest of the kitchen reduced to light */
      '<g fill="#FFCE8E">' +
        '<circle cx="300" cy="240" r="96" opacity="0.07"/><circle cx="1330" cy="300" r="120" opacity="0.06"/>' +
        '<circle cx="1180" cy="140" r="64" opacity="0.08"/><circle cx="470" cy="150" r="52" opacity="0.06"/>' +
        '<circle cx="1420" cy="640" r="88" opacity="0.05"/><circle cx="196" cy="600" r="70" opacity="0.05"/>' +
      '</g>' +
      /* the pinch: a thumb and a forefinger, with the gap between them left
         open. The gap is the whole picture — close it and this is a fist. */
      '<g transform="rotate(14 856 150)">' +
        '<path d="M596 -40 L830 -40 L830 96 C830 190 806 250 780 288 C756 262 744 210 744 150 L596 96 Z" fill="url(#g-skin)"/>' +
        '<path d="M900 -40 L1120 -40 L1120 86 C1120 168 986 214 918 262 C884 226 872 176 876 122 Z" fill="url(#g-skin)"/>' +
        '<path d="M748 152 C750 212 760 258 778 284" fill="none" stroke="#E8B27A" stroke-width="9" opacity="0.72" stroke-linecap="round"/>' +
        '<path d="M878 124 C874 176 888 224 918 258" fill="none" stroke="#E8B27A" stroke-width="9" opacity="0.66" stroke-linecap="round"/>' +
        '<path d="M600 60 L826 60" fill="none" stroke="#C08A52" stroke-width="6" opacity="0.35"/>' +
      '</g>' +
      /* the fall. Big and sharp near the pinch, small and soft further down. */
      '<g fill="#FFF3DF">' +
        '<circle cx="852" cy="336" r="11" opacity="0.95"/><circle cx="886" cy="382" r="9" opacity="0.9"/>' +
        '<circle cx="826" cy="404" r="8" opacity="0.85"/><circle cx="874" cy="452" r="10" opacity="0.9"/>' +
        '<circle cx="838" cy="502" r="7" opacity="0.8"/><circle cx="898" cy="524" r="6" opacity="0.7"/>' +
        '<circle cx="812" cy="560" r="8" opacity="0.75"/><circle cx="870" cy="596" r="5" opacity="0.6"/>' +
        '<circle cx="906" cy="446" r="5" opacity="0.6"/><circle cx="800" cy="470" r="5" opacity="0.55"/>' +
        '<circle cx="852" cy="640" r="6" opacity="0.5"/><circle cx="890" cy="672" r="4" opacity="0.4"/>' +
      '</g>' +
      /* chilli flake, one piece of real colour in a frame of neutrals */
      '<g fill="#E2511F"><ellipse cx="920" cy="420" rx="9" ry="5" transform="rotate(28 920 420)" opacity="0.9"/>' +
        '<ellipse cx="796" cy="524" rx="8" ry="4" transform="rotate(-16 796 524)" opacity="0.8"/></g>' +
      /* the dish it is falling into: shallow, wide, catching the pool */
      '<ellipse cx="856" cy="768" rx="430" ry="96" fill="url(#g-soft)"/>' +
      '<ellipse cx="856" cy="742" rx="340" ry="84" fill="#100D0C"/>' +
      '<ellipse cx="856" cy="734" rx="322" ry="76" fill="url(#g-steel)"/>' +
      '<ellipse cx="856" cy="740" rx="268" ry="58" fill="#0A0908"/>' +
      '<ellipse cx="856" cy="742" rx="228" ry="46" fill="#E8D9BE" opacity="0.7"/>' +
      '<ellipse cx="812" cy="734" rx="120" ry="24" fill="#FFF3DF" opacity="0.5"/>' +
      '<path d="M534 726 A322 76 0 0 1 1178 726" fill="none" stroke="#FFCE8E" stroke-width="7" opacity="0.85" stroke-linecap="round"/>' +
      /* grains that already landed, catching the same key */
      '<g fill="#FFF3DF" opacity="0.85"><circle cx="782" cy="736" r="4"/><circle cx="900" cy="744" r="4"/><circle cx="846" cy="730" r="3"/><circle cx="948" cy="738" r="3"/><circle cx="740" cy="746" r="3"/></g>' +
      motes([[1256, 400, 4, 0.3], [420, 420, 4, 0.26], [1360, 220, 3, 0.22], [270, 760, 4, 0.24]]) +
      '<rect width="1600" height="900" fill="url(#g-vignette)"/>' +
    '</g>';

  /* HANDS AT WORK — the only frame with a person in it. No face: a face in
     flat vector is a cartoon, and this campaign is not a cartoon. Forearms,
     knuckles and a board carry the whole idea of somebody actually cooking. */
  var SC_HANDS =
    '<g id="sc-hands">' +
      '<rect width="1600" height="900" fill="#0D0B09"/>' +
      '<ellipse cx="700" cy="300" rx="900" ry="680" fill="url(#g-pool)"/>' +
      '<path d="M0 0 L640 0 L1240 900 L0 900 Z" fill="url(#g-haze)"/>' +
      /* the board, running out of frame both sides */
      '<path d="M0 560 L1600 512 L1600 728 L0 700 Z" fill="url(#g-walnut)"/>' +
      '<path d="M0 566 L1600 518" fill="none" stroke="#C79A62" stroke-width="5" opacity="0.42"/>' +
      '<g opacity="0.2" stroke="#C79A62" stroke-width="3"><path d="M0 620 L1600 578"/><path d="M0 664 L1600 626"/></g>' +
      '<ellipse cx="760" cy="614" rx="520" ry="72" fill="url(#g-soft)"/>' +
      /* what is being worked on: dough, pressed and dusted */
      '<ellipse cx="700" cy="586" rx="212" ry="72" fill="#0A0807"/>' +
      '<ellipse cx="700" cy="576" rx="200" ry="64" fill="url(#g-crust)"/>' +
      '<path d="M500 570 C540 522 630 500 700 500 C776 500 858 524 900 570" fill="none" stroke="#FFD9A0" stroke-width="8" opacity="0.8" stroke-linecap="round"/>' +
      '<g fill="#FFF3DF" opacity="0.4"><circle cx="640" cy="548" r="5"/><circle cx="742" cy="536" r="4"/><circle cx="808" cy="562" r="4"/><circle cx="586" cy="580" r="3"/><circle cx="700" cy="520" r="3"/></g>' +
      /* two hands, reaching in from either side of the piece. The contact
         shadows go down first so they are not sitting on top of their own
         hands, which is how a drawn hand starts to float. */
      '<ellipse cx="470" cy="690" rx="180" ry="46" fill="#050403" opacity="0.5"/>' +
      '<ellipse cx="1120" cy="682" rx="170" ry="44" fill="#050403" opacity="0.5"/>' +
      hand(462, 806, 26, 1.06, false) +
      hand(1146, 798, -24, 1.0, true) +
      /* herbs and a scatter of flour: the detail nobody asked for */
      '<g fill="#141A0E" opacity="0.9">' +
        '<path d="M240 640 C288 606 358 602 400 622 C356 656 288 662 240 640 Z"/>' +
        '<path d="M318 682 C356 652 416 646 452 662 C416 694 358 700 318 682 Z"/>' +
      '</g>' +
      '<path d="M248 634 C296 602 356 598 396 618" fill="none" stroke="#8FA36A" stroke-width="4" opacity="0.6"/>' +
      '<g fill="#FFF3DF" opacity="0.28"><circle cx="960" cy="640" r="5"/><circle cx="1000" cy="668" r="4"/><circle cx="912" cy="676" r="3"/><circle cx="1042" cy="632" r="3"/></g>' +
      motes([[430, 240, 5, 0.4], [1200, 200, 4, 0.3], [1380, 400, 3, 0.24], [260, 380, 3, 0.26], [880, 180, 3, 0.2]]) +
      '<rect width="1600" height="900" fill="url(#g-vignette)"/>' +
    '</g>';

  /* THE PLATE — the finished thing, and deliberately the calmest frame in the
     campaign. It is also the only one built on ivory rather than ink, which is
     what makes it read as an ending rather than as another step. */
  var SC_PLATE =
    '<g id="sc-plate">' +
      '<rect width="1600" height="900" fill="#12100E"/>' +
      '<ellipse cx="900" cy="380" rx="900" ry="700" fill="url(#g-pool)"/>' +
      /* stone, seen from just above: two soft bands, no hard horizon */
      '<ellipse cx="820" cy="740" rx="1200" ry="320" fill="#C9772F" opacity="0.1"/>' +
      '<g opacity="0.12" stroke="#C9772F" stroke-width="4"><path d="M0 300 L1600 262"/><path d="M0 812 L1600 776"/></g>' +
      /* linen, entering bottom left, catching the key */
      '<path d="M0 900 L0 690 C160 656 300 672 392 726 C466 770 452 862 380 900 Z" fill="#2A241E"/>' +
      '<path d="M0 700 C158 666 296 682 386 734" fill="none" stroke="#C0AE92" stroke-width="6" opacity="0.5" stroke-linecap="round"/>' +
      '<path d="M60 790 C160 772 250 782 320 818" fill="none" stroke="#8A7B63" stroke-width="4" opacity="0.35" stroke-linecap="round"/>' +
      /* the plate: wide rim, shallow well, one clean specular on the lit edge */
      '<ellipse cx="900" cy="524" rx="452" ry="326" fill="url(#g-soft)"/>' +
      '<ellipse cx="896" cy="486" rx="424" ry="286" fill="#6E624F"/>' +
      '<ellipse cx="896" cy="478" rx="416" ry="278" fill="url(#g-ceramic)"/>' +
      '<ellipse cx="896" cy="486" rx="306" ry="200" fill="#C6B79C" opacity="0.5"/>' +
      '<ellipse cx="896" cy="480" rx="296" ry="192" fill="url(#g-ceramic)"/>' +
      '<path d="M508 430 A416 278 0 0 1 1000 208" fill="none" stroke="#FFF6E4" stroke-width="9" opacity="0.85" stroke-linecap="round"/>' +
      '<path d="M528 596 A416 278 0 0 0 760 742" fill="none" stroke="#8A7B63" stroke-width="5" opacity="0.4" stroke-linecap="round"/>' +
      /* sauce sweep, then the food ON it, off centre and stacked */
      '<path d="M660 552 C712 606 866 630 1044 592 C1114 576 1140 536 1112 512 C1058 570 810 592 660 552 Z" fill="#5E2E0A" opacity="0.62"/>' +
      '<ellipse cx="900" cy="486" rx="176" ry="86" fill="#2A1204" opacity="0.5"/>' +
      '<path d="M736 486 C736 428 812 396 900 396 C990 396 1064 428 1064 486 C1064 540 986 574 900 574 C816 574 736 540 736 486 Z" fill="url(#g-crust-2)"/>' +
      '<path d="M744 470 C760 424 824 400 898 400" fill="none" stroke="#FFE8BC" stroke-width="7" opacity="0.8" stroke-linecap="round"/>' +
      '<g fill="#3A1A05" opacity="0.45"><ellipse cx="962" cy="512" rx="56" ry="18"/><ellipse cx="838" cy="522" rx="40" ry="13"/></g>' +
      '<path d="M812 430 C876 408 962 412 1012 440" fill="none" stroke="#8A4A18" stroke-width="6" opacity="0.5" stroke-linecap="round"/>' +
      /* one herb and two oil beads, because a plate that is too clean is a render */
      '<g fill="#141A0E" opacity="0.92">' +
        '<path d="M934 396 C968 366 1018 362 1046 376 C1014 404 966 410 934 396 Z"/>' +
      '</g>' +
      '<path d="M940 392 C972 364 1014 360 1040 374" fill="none" stroke="#8FA36A" stroke-width="4" opacity="0.7"/>' +
      '<g fill="#FFE8BC" opacity="0.5"><ellipse cx="1052" cy="546" rx="12" ry="7"/><ellipse cx="1088" cy="524" rx="7" ry="4"/></g>' +
      /* a fork, resting on the rim, entering from the right */
      '<g transform="rotate(-8 1360 640)">' +
        '<rect x="1210" y="630" width="330" height="22" rx="10" fill="url(#g-steel)"/>' +
        '<path d="M1216 636 L1520 636" fill="none" stroke="#FFF3DF" stroke-width="4" opacity="0.7"/>' +
        '<g fill="url(#g-steel)"><rect x="1160" y="608" width="60" height="9" rx="4"/><rect x="1160" y="626" width="60" height="9" rx="4"/><rect x="1160" y="644" width="60" height="9" rx="4"/><rect x="1160" y="662" width="60" height="9" rx="4"/></g>' +
      '</g>' +
      motes([[380, 260, 5, 0.36], [1300, 250, 4, 0.3], [1420, 560, 3, 0.22], [250, 460, 3, 0.24]]) +
      '<rect width="1600" height="900" fill="url(#g-vignette)"/>' +
    '</g>';

  /* THE EDITORIAL PLATE — a frame that is deliberately mostly empty, because a
     campaign that never stops showing food never lets a sentence land. The
     scene supplies the ground and the marks; the `quote` lockup supplies the
     words, sized to whatever crop it is asked for. */
  var SC_QUOTE =
    '<g id="sc-quote">' +
      '<rect width="1600" height="900" fill="#0C0A09"/>' +
      '<ellipse cx="1180" cy="740" rx="820" ry="520" fill="url(#g-ember)" opacity="0.55"/>' +
      '<ellipse cx="1300" cy="860" rx="360" ry="180" fill="url(#g-ember-hot)" opacity="0.5"/>' +
      '<path d="M0 0 L520 0 L1120 900 L0 900 Z" fill="url(#g-haze)"/>' +
      /* the marks of a printed page: a top rule, a measure line, a folio bar */
      /* Hairlines only. The ember rule belongs to the lockup — drawing one here
         too put two orange marks in the same corner. */
      '<g stroke="#C79A62" opacity="0.28"><path d="M96 128 L1504 128" stroke-width="3"/><path d="M96 772 L1504 772" stroke-width="3"/></g>' +
      /* the quotation itself, as a graphic rather than a glyph: two struck
         commas, big enough to be composition and quiet enough to be ground */
      '<g fill="#F0663A" opacity="0.16">' +
        '<path d="M300 300 C300 232 356 184 428 184 L428 268 C400 268 384 286 384 310 L440 310 L440 470 L300 470 Z"/>' +
        '<path d="M492 300 C492 232 548 184 620 184 L620 268 C592 268 576 286 576 310 L632 310 L632 470 L492 470 Z"/>' +
      '</g>' +
      /* a sliver of the shoot at the right edge, so the page belongs to the film */
      '<g opacity="0.5"><ellipse cx="1420" cy="470" rx="230" ry="230" fill="#0A0908"/>' +
        '<ellipse cx="1420" cy="470" rx="210" ry="210" fill="url(#g-iron)"/>' +
        '<ellipse cx="1420" cy="470" rx="168" ry="168" fill="#2A1204"/>' +
        '<ellipse cx="1420" cy="470" rx="160" ry="160" fill="url(#g-crust)"/>' +
        '<path d="M1272 386 A210 210 0 0 1 1500 268" fill="none" stroke="#FFCE8E" stroke-width="8" opacity="0.7" stroke-linecap="round"/>' +
      '</g>' +
      motes([[420, 620, 5, 0.3], [980, 220, 4, 0.24], [700, 700, 3, 0.2], [1180, 180, 3, 0.18]]) +
      '<rect width="1600" height="900" fill="url(#g-vignette)"/>' +
    '</g>';

  /* Injected once. Everything else in the prototype references these by id. */
  function injectScenes() {
    if (document.getElementById('po-scenes')) return;
    var host = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    host.setAttribute('id', 'po-scenes');
    host.setAttribute('width', '0');
    host.setAttribute('height', '0');
    host.setAttribute('aria-hidden', 'true');
    host.setAttribute('focusable', 'false');
    host.style.position = 'absolute';
    host.innerHTML = '<defs>' + DEFS + SC_SEAR + SC_OVER + SC_LOAF + SC_FLAME + SC_KNIFE +
                     SC_FLIP + SC_SPICE + SC_HANDS + SC_PLATE + SC_QUOTE + '</defs>';
    document.body.insertBefore(host, document.body.firstChild);
  }

  /* ---------------------------------------------------------------- crops */

  var ASPECT = {
    '16x9': [1600, 900], '9x16': [506, 900], '1x1': [900, 900],
    '4x5': [720, 900], '21x9': [1600, 686], '3x2': [1350, 900], '2x3': [600, 900],
    /* Paid placements are the same shoot at the sizes the platforms sell.
       Named for what they are rather than for their ratio, because that is
       what a media plan calls them. */
    '8x1': [1600, 198],   /* 728 x 90   leaderboard */
    '6x5': [1080, 900],   /* 300 x 250  medium rectangle */
    '4x15': [240, 900]    /* 160 x 600  wide skyscraper */
  };

  /** The crop rectangle for one scene at one aspect, centred on the focus and
      clamped so it never runs off the canonical frame.

      `seat` is which one of a set this is. A plan that says "six title cards"
      and then draws the same rectangle six times is describing a set it does
      not have; six different frames of one shoot is the whole idea of the
      product, and it costs one offset. */
  var SEATS = [[0, 0], [-0.16, -0.06], [0.17, 0.05], [-0.09, 0.09], [0.11, -0.10],
               [-0.20, 0.02], [0.22, -0.03], [0.04, 0.12], [-0.13, -0.12], [0.14, 0.08],
               [-0.05, -0.04], [0.08, 0.06]];
  function crop(scene, aspect, seat) {
    var box = ASPECT[aspect] || ASPECT['16x9'];
    var w = box[0], h = box[1];
    var f = (SCENE_META[scene] || SCENE_META.sear).focus;
    var off = SEATS[(seat || 0) % SEATS.length];
    var x = Math.max(0, Math.min(1600 - w, Math.round(f[0] + off[0] * w - w / 2)));
    var y = Math.max(0, Math.min(900 - h, Math.round(f[1] + off[1] * h - h / 2)));
    return [x, y, w, h];
  }

  /* ======================================================================
     SETS — what stops a campaign looking like one photograph forty times

     A deliverable with n > 1 used to draw the same descriptor n times and lean
     entirely on the seat offset to tell them apart. A shifted crop of one pan
     is still one pan, which is exactly the flatness this campaign was accused
     of: technically a set, emotionally a repeat.

     A set says what each copy actually IS. Seat 3 of "supporting posts" is a
     different SET-UP, a different lockup and a different line — not the same
     frame nudged 9%. Identity is held by the grade, the palette and the
     narrative, which every entry still shares; variety is spent on subject,
     composition, scale and typography, which is where variety belongs.

     Every word below already exists in this campaign — episode titles,
     techniques, the tagline, the idea. A set recombines the campaign; it does
     not write a new one.
     ====================================================================== */
  var C_ = PO.CAMPAIGN, EP_ = C_.episodes;
  function low(t) { return String(t).toLowerCase(); }

  var SETS = {
    /* The throw, the fire, the result. Three heroes, three different beats of
       the same story — which is what a hero set is for. */
    hero: [
      { scene: 'flip',  lockup: 'title', title: C_.brand,   eyebrow: C_.season },
      { scene: 'flame', lockup: 'end' },
      { scene: 'plate', lockup: 'title', title: C_.tagline, eyebrow: C_.brand }
    ],

    /* Concept directions have to look like alternatives or the word is a lie:
       one on heat, one macro, one plated and calm. */
    concept: [{ scene: 'sear' }, { scene: 'spice' }, { scene: 'plate' }],

    /* One card per episode, so six title cards carry six titles. */
    episode: EP_.map(function (e, i) {
      return { scene: ['sear', 'loaf', 'hands', 'flame', 'knife', 'flip'][i % 6],
               lockup: 'episode', n: String(e.n), title: e.title, eyebrow: e.technique };
    }),

    /* Six vertical teasers, six techniques, six set-ups. */
    vert: EP_.map(function (e, i) {
      return { scene: ['flip', 'loaf', 'hands', 'sear', 'knife', 'flame'][i % 6],
               lockup: 'caption', caption: low(e.technique) };
    }),

    /* Twelve supporting posts. The rotation deliberately includes frames with
       NO type at all — a feed that captions every single post reads as a
       content farm, and silence is a composition choice too. */
    social: [
      /* not `plate`: the Meta feed ad opens on the plated frame, and these two
         sit next to each other on Home and again on the plan. */
      { scene: 'over',  lockup: 'caption', caption: low(EP_[0].technique) },
      { scene: 'spice', lockup: null },
      { scene: 'quote', lockup: 'quote', caption: C_.tagline, eyebrow: C_.season },
      { scene: 'hands', lockup: 'caption', caption: low(EP_[4].technique) },
      { scene: 'flip',  lockup: null },
      { scene: 'loaf',  lockup: 'episode', n: String(EP_[1].n), title: EP_[1].title, eyebrow: EP_[1].technique },
      { scene: 'plate', lockup: 'caption', caption: low(EP_[2].technique) },
      { scene: 'flame', lockup: null },
      { scene: 'quote', lockup: 'quote', caption: C_.idea, eyebrow: C_.brand },
      { scene: 'knife', lockup: 'episode', n: String(EP_[4].n), title: EP_[4].title, eyebrow: EP_[4].technique },
      { scene: 'plate', lockup: null },
      { scene: 'sear',  lockup: 'caption', caption: low(C_.tagline) }
    ],

    /* Thumbnail concepts: big type, strong frames, one per technique. */
    thumb: [
      { scene: 'flip',  lockup: 'title', title: EP_[0].title, eyebrow: C_.brand },
      { scene: 'flame', lockup: 'title', title: EP_[5].title, eyebrow: C_.brand },
      { scene: 'spice', lockup: 'title', title: EP_[2].title, eyebrow: C_.brand },
      { scene: 'hands', lockup: 'title', title: EP_[1].title, eyebrow: C_.brand }
    ],

    /* ---- paid. Each placement gets the set-up that suits how it is watched:
       a feed unit is scrolled past, so it leads with the finished plate; a
       story is full-screen and vertical, so it leads with motion. ---- */
    admeta: [
      { scene: 'plate', ad: 'meta', headline: 'Six techniques. No fear.', cta: 'Watch the trailer' },
      { scene: 'hands', ad: 'meta', headline: C_.tagline, cta: 'See the season' }
    ],
    adstory: [
      { scene: 'flip',  ad: 'story', headline: C_.tagline, cta: 'Watch now' },
      { scene: 'spice', ad: 'story', headline: 'Six techniques. No fear.', cta: 'Watch now' }
    ],
    adtok: [
      { scene: 'hands', ad: 'tiktok', headline: 'Hotter than you think.', cta: 'See the season' },
      { scene: 'flip',  ad: 'tiktok', headline: C_.tagline, cta: 'Watch now' }
    ],
    adpre: [
      { scene: 'flame', ad: 'preroll', headline: 'Season Two. 14 September.', cta: 'Subscribe' },
      { scene: 'sear',  ad: 'preroll', headline: 'Six techniques. No fear.', cta: 'Subscribe' }
    ],
    /* Five real IAB sizes, drawn at their real ratios. */
    addisp: [
      { scene: 'sear',  ad: 'display', unit: [728, 90],  headline: C_.tagline, cta: 'Watch' },
      { scene: 'plate', ad: 'display', unit: [300, 250], headline: C_.tagline, cta: 'Watch' },
      { scene: 'flame', ad: 'display', unit: [160, 600], headline: C_.tagline, cta: 'Watch' },
      { scene: 'spice', ad: 'display', unit: [320, 50],  headline: C_.tagline, cta: 'Watch' },
      { scene: 'flip',  ad: 'display', unit: [970, 250], headline: 'Six techniques. No fear.', cta: 'Watch the trailer' }
    ],
    /* Eight copy tests. The variable under test is the pairing and the button
       position, so both halves are shown at once rather than as eight frames
       that differ by a word nobody can read at this size. */
    adcopy: [
      { scene: 'quote', ad: 'copy', headline: 'Six techniques. No fear.', cta: 'Watch the trailer', headlineB: C_.tagline, ctaB: 'Watch now' },
      { scene: 'sear',  ad: 'copy', headline: C_.tagline, cta: 'Watch now', headlineB: 'Hotter than you think.', ctaB: 'See the season' },
      { scene: 'plate', ad: 'copy', headline: 'Hotter than you think.', cta: 'See the season', headlineB: 'Season Two. 14 September.', ctaB: 'Subscribe' },
      { scene: 'flame', ad: 'copy', headline: 'Season Two. 14 September.', cta: 'Subscribe', headlineB: 'Six techniques. No fear.', ctaB: 'Watch the trailer' },
      { scene: 'hands', ad: 'copy', headline: 'Six techniques. No fear.', cta: 'Watch now', headlineB: 'Six techniques. No fear.', ctaB: 'Subscribe' },
      { scene: 'flip',  ad: 'copy', headline: C_.tagline, cta: 'Watch the trailer', headlineB: C_.tagline, ctaB: 'See the season' },
      { scene: 'spice', ad: 'copy', headline: 'Hotter than you think.', cta: 'Watch now', headlineB: 'Six techniques. No fear.', ctaB: 'See the season' },
      { scene: 'knife', ad: 'copy', headline: 'Season Two. 14 September.', cta: 'Watch the trailer', headlineB: C_.tagline, ctaB: 'Subscribe' }
    ]
  };

  function setEntry(name, seat) {
    var t = SETS[name];
    if (!t || !t.length) return null;
    return t[(seat || 0) % t.length];
  }

  var esc = function (s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  };

  /**
   * One piece of campaign media.
   *
   * @param scene  which set-up: sear | over | loaf | flame
   * @param aspect the crop
   * @param o.lockup   'title' | 'episode' | 'caption' | 'end' | null
   * @param o.title / o.eyebrow / o.caption / o.n
   * @param o.detail   'thumb' skips every overlay — at 40px wide, type is dirt
   */
  function still(scene, aspect, o) {
    o = o || {};
    var c = crop(scene, aspect, o.seat);
    var vb = c.join(' ');
    var body = '<use href="#sc-' + scene + '"/>';
    /* A paid placement keeps its chrome at every size. At contact-sheet scale
       the headline is four illegible pixels and gets dropped, but the furniture
       — segment bars, a skip control, a banner keyline — is exactly what tells
       one placement from another at 90px, so it survives the thumbnail. */
    if (o.lockup === 'ad') body += adUnit(c, o, o.detail === 'thumb');
    else if (o.detail !== 'thumb' && o.lockup) body += lockup(o.lockup, c, o);
    return '<svg class="art" viewBox="' + vb + '" preserveAspectRatio="xMidYMid slice" ' +
      'aria-hidden="true" focusable="false">' + body + '</svg>';
  }

  /* ------------------------------------------------------------ paid units

     A paid pack fails the moment its six placements are one picture wearing
     six crops. What actually separates them in a real media plan is CHROME —
     the furniture each placement is sold inside. A story has segment bars, a
     pre-roll has a skip control, a feed unit has a full-width button under the
     picture, a banner has a keyline and a size.

     So the chrome is drawn, in the campaign's own palette, and it is drawn
     FIRST at thumbnail scale — because at 90px the headline is four illegible
     pixels but the silhouette of the furniture is still completely readable.
     That is what "distinguishable at thumbnail size" has to mean.

     Nothing here reproduces a platform's marks. A segmented progress bar and a
     rail of circles are layout conventions, not trademarks, and no logo, brand
     name or third-party asset appears in any of them.
     ---------------------------------------------------------------------- */

  var CTA_INK = '#E2511F', CTA_ON = '#FFFDF8';

  /* ------------------------------------------------------------ fitting

     Type set into a picture cannot reflow. If it does not fit it runs off the
     edge of the frame, and a wrap that silently truncates instead is worse —
     it drops a word out of the campaign and nobody notices until print.

     A character-count guess cannot solve this, because the two builds of this
     prototype are not set in the same faces: the artifact loads Instrument
     Serif and Inter, the repository copy falls back to Georgia and the system
     sans, and their advances differ by about a quarter. A constant safe for
     one wastes a quarter of the frame on the other.

     So the width is MEASURED, once per string per face, against the fonts that
     actually loaded. Measurement is cached only once the fonts are ready —
     before that the fallback is used, which is the wider of the two and
     therefore the safe direction to be wrong in.
     -------------------------------------------------------------------- */

  var twCache = {}, twHost = null;
  function fontsReady() { return !document.fonts || document.fonts.status === 'loaded'; }
  function measure(str, kind, weight, ls) {
    try {
      if (!twHost) twHost = document.getElementById('po-scenes');
      if (!twHost) return 0;
      var t = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      t.setAttribute('font-family', fam(kind));
      t.setAttribute('font-size', '100');
      t.setAttribute('font-weight', weight);
      t.setAttribute('letter-spacing', (ls * 100).toFixed(1));
      t.textContent = str;
      twHost.appendChild(t);
      var w = t.getComputedTextLength();
      twHost.removeChild(t);
      return w || 0;
    } catch (e) { return 0; }
  }
  /** Width of `str` at `fs`, in the crop's own units. */
  function textW(str, fs, kind, weight, ls) {
    str = String(str);
    var key = kind + '|' + weight + '|' + ls + '|' + str;
    var at100 = twCache[key];
    if (at100 == null) {
      at100 = measure(str, kind, weight, ls);
      if (!at100) return str.length * fs * (kind === 'display' ? 0.48 : 0.62);
      if (fontsReady()) twCache[key] = at100;
    }
    return at100 * fs / 100;
  }

  /** Greedy wrap that never drops a word, measured against a real box. */
  function wrapW(text, boxW, fs, kind, weight, ls) {
    var words = String(text).split(' '), lines = [], cur = '';
    for (var i = 0; i < words.length; i++) {
      var next = cur ? cur + ' ' + words[i] : words[i];
      if (cur && textW(next, fs, kind, weight, ls) > boxW) { lines.push(cur); cur = words[i]; }
      else cur = next;
    }
    if (cur) lines.push(cur);
    return lines;
  }

  /** Lines and a font size that together fit `boxW` in at most `max` lines.
      Shrinks rather than truncates, because losing a word is not a layout. */
  function fitBlock(text, boxW, fs, max, kind, weight, ls) {
    kind = kind || 'display'; weight = weight || 400; ls = ls == null ? -0.01 : ls;
    max = max || 2;
    var size = fs, lines = wrapW(text, boxW, size, kind, weight, ls), guard = 0;
    while (lines.length > max && size > 7 && guard++ < 12) {
      size = Math.max(7, Math.floor(size * 0.88));
      lines = wrapW(text, boxW, size, kind, weight, ls);
    }
    return { lines: lines, fs: size };
  }

  /** A single line, shrunk until it fits. */
  function shrinkTo(text, boxW, fs, kind, weight, ls) {
    kind = kind || 'display'; weight = weight || 400; ls = ls == null ? -0.01 : ls;
    var w = textW(text, fs, kind, weight, ls);
    return w <= boxW ? fs : Math.max(7, Math.floor(fs * boxW / w));
  }

  function pill(x, y, w, h, label, fs, fill) {
    var out = '<rect x="' + Math.round(x) + '" y="' + Math.round(y) + '" width="' + Math.round(w) +
      '" height="' + Math.round(h) + '" rx="' + Math.round(h * 0.24) + '" fill="' + (fill || CTA_INK) + '"/>';
    if (label && fs >= 7) out += txtC(x + w / 2, y + h / 2 + fs * 0.36, esc(label), fs, CTA_ON, 'sans', 600, 0.06);
    return out;
  }
  function box(x, y, w, h, stroke, sw, op) {
    return '<rect x="' + Math.round(x) + '" y="' + Math.round(y) + '" width="' + Math.round(w) + '" height="' +
      Math.round(h) + '" fill="none" stroke="' + stroke + '" stroke-width="' + sw + '" opacity="' + op + '"/>';
  }
  function ctaW(label, fs) { return Math.round(textW(label, fs, 'sans', 600, 0.06)) + fs * 1.9; }

  /** One paid placement, chrome and all.
      @param thumb at contact-sheet scale, chrome only — type is dropped. */
  function adUnit(c, o, thumb) {
    var style = o.ad || 'meta';
    var x = c[0], y = c[1], w = c[2], h = c[3], s = Math.min(w, h);
    var pad = Math.round(s * 0.085);
    var L = x + pad, R = x + w - pad, T = y + pad, B = y + h - pad;
    var cta = String(o.cta || 'Watch the trailer');
    var out = '';

    if (style === 'display') {
      /* A banner is not a still — it is a SIZE. So the unit is drawn at its real
         ratio, floated on a mat that dims whatever the host frame is, with the
         picture cropped inside it. Five banner sizes are then five visibly
         different shapes at any tile size, which is the only way a banner set
         reads as a set rather than as one picture five times. */
      var un = o.unit || [728, 90], ar = un[0] / un[1];
      var fw = w * 0.9, fh = h * 0.9, uw, uh;
      if (fw / fh > ar) { uh = fh; uw = uh * ar; } else { uw = fw; uh = uw / ar; }
      var ux = Math.round(x + (w - uw) / 2), uy = Math.round(y + (h - uh) / 2);
      uw = Math.round(uw); uh = Math.round(uh);
      var mat = '#0B0908';
      out += '<g fill="' + mat + '" opacity="0.74">' +
        '<rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + (uy - y) + '"/>' +
        '<rect x="' + x + '" y="' + (uy + uh) + '" width="' + w + '" height="' + Math.max(0, y + h - uy - uh) + '"/>' +
        '<rect x="' + x + '" y="' + uy + '" width="' + Math.max(0, ux - x) + '" height="' + uh + '"/>' +
        '<rect x="' + (ux + uw) + '" y="' + uy + '" width="' + Math.max(0, x + w - ux - uw) + '" height="' + uh + '"/></g>';
      out += '<rect x="' + ux + '" y="' + uy + '" width="' + uw + '" height="' + uh + '" fill="url(#g-scrim-full)" opacity="0.44"/>';
      out += box(ux, uy, uw, uh, '#FFE9C0', Math.max(1, Math.round(Math.min(w, h) * 0.01)), 0.6);

      var us = Math.min(uw, uh), horiz = ar > 2.2, vert = ar < 0.5;
      var up = Math.round(us * 0.1);
      var dh = Math.max(7, Math.round(us * (horiz ? 0.3 : 0.14)));
      var dch = Math.max(9, Math.round(dh * 1.1)), dcf = Math.max(6, Math.round(dch * 0.44));
      var dcw = Math.min(ctaW(cta, dcf), uw - up * 2);
      if (thumb) {
        out += horiz ? pill(ux + uw - up - Math.round(uw * 0.22), uy + uh / 2 - dch / 2, Math.round(uw * 0.22), dch, '', 0)
                     : pill(ux + up, uy + uh - up - dch, Math.min(uw - up * 2, dcw), dch, '', 0);
        return out;
      }
      if (horiz) {
        out += txt(ux + up, uy + up + dh * 0.4, esc(o.eyebrow || PO.CAMPAIGN.brand), Math.max(6, Math.round(dh * 0.3)), '#FFE9C0', 'sans', 600, 0.14);
        var dhead = String(o.headline || PO.CAMPAIGN.tagline);
        out += txt(ux + up, uy + uh * 0.68, esc(dhead), shrinkTo(dhead, uw - up * 3 - dcw, dh), CTA_ON, 'display', 400, -0.01);
        out += pill(ux + uw - up - dcw, uy + uh / 2 - dch / 2, dcw, dch, cta, dcf);
      } else {
        var db = fitBlock(String(o.headline || PO.CAMPAIGN.tagline), uw - up * 2, dh, vert ? 3 : 2);
        var dl = db.lines; dh = db.fs;
        out += txt(ux + up, uy + up + dh * 0.66, esc(o.eyebrow || PO.CAMPAIGN.brand), Math.max(6, Math.round(dh * 0.34)), '#FFE9C0', 'sans', 600, 0.14);
        for (var di = 0; di < dl.length; di++) {
          out += txt(ux + up, uy + uh * 0.52 + (di - (dl.length - 1) / 2) * dh * 1.16, esc(dl[di]), dh, CTA_ON, 'display', 400, -0.01);
        }
        out += pill(ux + up, uy + uh - up - dch, dcw, dch, cta, dcf);
      }
      if (us > 130) out += txt(ux, uy + uh + Math.round(us * 0.13), esc(un[0] + ' × ' + un[1]), Math.max(7, Math.round(us * 0.1)), '#E4D9C6', 'sans', 500, 0.1);
      return out;
    }

    out += '<rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + h + '" fill="url(#g-scrim-full)" opacity="0.46"/>';

    if (style === 'story') {
      /* Segment bars across the head. Nothing else in the pack has them, so at
         40px this is the placement, read in one glance. */
      var segs = 5, sg = Math.round(s * 0.022);
      var sw2 = (w - pad * 2 - sg * (segs - 1)) / segs, sh = Math.max(3, Math.round(s * 0.014));
      for (var i = 0; i < segs; i++) {
        out += '<rect x="' + Math.round(L + i * (sw2 + sg)) + '" y="' + T + '" width="' + Math.round(sw2) +
          '" height="' + sh + '" rx="' + Math.round(sh / 2) + '" fill="' + (i < 2 ? '#FFE9C0' : '#FFE9C0') +
          '" opacity="' + (i < 2 ? 0.92 : 0.28) + '"/>';
      }
      var sch = Math.max(12, Math.round(s * 0.11)), scf = Math.max(7, Math.round(sch * 0.42));
      var scw = Math.min(ctaW(cta, scf), w - pad * 2);
      if (thumb) return out + pill(x + w / 2 - scw / 2, B - sch, scw, sch, '', 0);
      out += '<rect x="' + x + '" y="' + Math.round(y + h * 0.46) + '" width="' + w + '" height="' + Math.round(h * 0.54) + '" fill="url(#g-scrim)"/>';
      var sb = fitBlock(String(o.headline || PO.CAMPAIGN.tagline), w - pad * 2, Math.max(9, Math.round(s * 0.115)), 3);
      var sl = sb.lines, shf = sb.fs;
      out += txtC(x + w / 2, T + sh + Math.round(s * 0.09), esc(o.eyebrow || PO.CAMPAIGN.brand), Math.max(6, Math.round(s * 0.042)), '#FFE9C0', 'sans', 600, 0.16);
      var stop = B - sch - Math.round(s * 0.13) - (sl.length - 1) * shf * 1.14;
      for (var si = 0; si < sl.length; si++) {
        out += txtC(x + w / 2, stop + si * shf * 1.14, esc(sl[si]), shf, CTA_ON, 'display', 400, -0.01);
      }
      out += pill(x + w / 2 - scw / 2, B - sch, scw, sch, cta, scf);
      return out;
    }

    if (style === 'tiktok') {
      /* A rail of controls down the right, copy hard left. The asymmetry is
         the tell — every other vertical unit in the pack is centred. */
      var rr = Math.max(4, Math.round(s * 0.052)), rx = R - rr;
      var ry0 = y + h * 0.44;
      out += '<g fill="#FFE9C0" opacity="0.82">' +
        '<circle cx="' + Math.round(rx) + '" cy="' + Math.round(ry0) + '" r="' + rr + '"/>' +
        '<circle cx="' + Math.round(rx) + '" cy="' + Math.round(ry0 + rr * 2.9) + '" r="' + rr + '"/>' +
        '<circle cx="' + Math.round(rx) + '" cy="' + Math.round(ry0 + rr * 5.8) + '" r="' + rr + '"/>' +
        '<rect x="' + Math.round(rx - rr * 0.82) + '" y="' + Math.round(ry0 + rr * 7.6) + '" width="' + Math.round(rr * 1.64) +
          '" height="' + Math.round(rr * 1.64) + '" rx="' + Math.round(rr * 0.5) + '"/></g>';
      var tch = Math.max(11, Math.round(s * 0.10)), tcf = Math.max(7, Math.round(tch * 0.42));
      var tcw = Math.min(ctaW(cta, tcf), w - pad * 2 - rr * 2.6);
      if (thumb) return out + pill(L, B - tch, tcw, tch, '', 0);
      var tb = fitBlock(String(o.headline || PO.CAMPAIGN.tagline), w - pad * 2 - rr * 2.6, Math.max(9, Math.round(s * 0.10)), 3);
      var tl = tb.lines, thf = tb.fs;
      var ttop = B - tch - Math.round(s * 0.10) - (tl.length - 1) * thf * 1.14;
      out += txt(L, ttop - thf * 0.95, esc(o.eyebrow || PO.CAMPAIGN.brand), Math.max(6, Math.round(s * 0.04)), '#FFE9C0', 'sans', 600, 0.16);
      for (var ti = 0; ti < tl.length; ti++) out += txt(L, ttop + ti * thf * 1.14, esc(tl[ti]), thf, CTA_ON, 'display', 400, -0.01);
      out += pill(L, B - tch, tcw, tch, cta, tcf);
      return out;
    }

    if (style === 'preroll') {
      /* The skip control and the elapsed bar. Both live at the bottom edge, so
         this is the only unit in the pack with a hard horizontal line at the
         very base of the frame. */
      var pb = Math.max(3, Math.round(s * 0.022));
      out += '<rect x="' + x + '" y="' + (y + h - pb) + '" width="' + w + '" height="' + pb + '" fill="#FFE9C0" opacity="0.24"/>';
      out += '<rect x="' + x + '" y="' + (y + h - pb) + '" width="' + Math.round(w * 0.34) + '" height="' + pb + '" fill="' + CTA_INK + '"/>';
      var kh = Math.max(11, Math.round(s * 0.10)), kf = Math.max(7, Math.round(kh * 0.42));
      var kw = Math.min(ctaW('Skip', kf), Math.round(w * 0.3));
      var ky = y + h - pb - Math.round(s * 0.055) - kh;
      out += '<rect x="' + Math.round(R - kw) + '" y="' + Math.round(ky) + '" width="' + kw + '" height="' + kh +
        '" rx="' + Math.round(kh * 0.18) + '" fill="#0B0908" opacity="0.72"/>';
      out += box(R - kw, ky, kw, kh, '#FFE9C0', Math.max(1, Math.round(s * 0.008)), 0.7);
      if (thumb) return out + '<rect x="' + Math.round(L) + '" y="' + Math.round(T) + '" width="' + Math.round(s * 0.11) +
        '" height="' + Math.round(s * 0.11) + '" rx="' + Math.round(s * 0.026) + '" fill="' + CTA_INK + '"/>';
      out += txtC(R - kw / 2, ky + kh / 2 + kf * 0.36, 'Skip', kf, '#FFE9C0', 'sans', 600, 0.06);
      out += '<rect x="' + x + '" y="' + Math.round(y + h * 0.44) + '" width="' + Math.round(w * 0.68) + '" height="' + Math.round(h * 0.56) + '" fill="url(#g-scrim-left)"/>';
      var pb2 = fitBlock(String(o.headline || PO.CAMPAIGN.tagline), w * 0.62, Math.max(9, Math.round(s * 0.135)), 2);
      var pl = pb2.lines, phf = pb2.fs;
      var pbase = y + h - pb - Math.round(s * 0.055) - kh - Math.round(s * 0.06);
      out += txt(L, pbase - (pl.length) * phf * 1.14 - Math.round(s * 0.02), esc(o.eyebrow || PO.CAMPAIGN.brand), Math.max(6, Math.round(s * 0.04)), '#FFE9C0', 'sans', 600, 0.16);
      for (var pi = 0; pi < pl.length; pi++) out += txt(L, pbase - (pl.length - 1 - pi) * phf * 1.14, esc(pl[pi]), phf, CTA_ON, 'display', 400, -0.01);
      var pch = Math.max(11, Math.round(s * 0.10)), pcf = Math.max(7, Math.round(pch * 0.42));
      out += pill(L, ky, Math.min(ctaW(cta, pcf), Math.round(w * 0.34)), pch, cta, pcf);
      return out;
    }

    if (style === 'copy') {
      /* A copy test is two treatments of one frame, and the thing under test is
         usually WHERE the button sits. So the unit shows both halves at once,
         split by a hairline, marked A and B. */
      var mid = x + w / 2;
      out += '<path d="M' + Math.round(mid) + ' ' + y + ' L' + Math.round(mid) + ' ' + (y + h) + '" stroke="#FFE9C0" stroke-width="' + Math.max(1, Math.round(s * 0.008)) + '" opacity="0.5" stroke-dasharray="' + Math.round(s * 0.05) + ' ' + Math.round(s * 0.035) + '"/>';
      var qh = Math.max(9, Math.round(s * 0.085)), qf = Math.max(6, Math.round(qh * 0.44));
      var half = w / 2 - pad * 1.4;
      var aw = Math.min(ctaW(cta, qf), half), bw = Math.min(ctaW(String(o.ctaB || cta), qf), half);
      if (thumb) {
        return out + pill(L, T + s * 0.10, Math.min(half, s * 0.5), qh, '', 0) +
                     pill(mid + pad * 0.4, B - qh, Math.min(half, s * 0.5), qh, '', 0);
      }
      var qhf0 = Math.max(8, Math.round(s * 0.072));
      var ab = fitBlock(String(o.headline || PO.CAMPAIGN.tagline), half, qhf0, 2);
      var bb = fitBlock(String(o.headlineB || o.headline || PO.CAMPAIGN.tagline), half, qhf0, 2);
      /* One size across both halves. Two headlines set at different sizes is a
         comparison of type scales, not of copy. */
      var qhf = Math.min(ab.fs, bb.fs);
      var al = qhf === ab.fs ? ab.lines : fitBlock(String(o.headline || PO.CAMPAIGN.tagline), half, qhf, 3).lines;
      var bl = qhf === bb.fs ? bb.lines : fitBlock(String(o.headlineB || o.headline || PO.CAMPAIGN.tagline), half, qhf, 3).lines;
      out += txt(L, T + qhf, 'A', Math.max(7, Math.round(s * 0.05)), '#FFE9C0', 'sans', 700, 0.14);
      out += txt(mid + pad * 0.4, T + qhf, 'B', Math.max(7, Math.round(s * 0.05)), '#FFE9C0', 'sans', 700, 0.14);
      for (var ai = 0; ai < al.length; ai++) out += txt(L, T + qhf * 2.6 + ai * qhf * 1.16, esc(al[ai]), qhf, CTA_ON, 'display', 400, -0.01);
      out += pill(L, T + qhf * 2.6 + al.length * qhf * 1.16 + qhf * 0.3, aw, qh, cta, qf);
      for (var bi = 0; bi < bl.length; bi++) out += txt(mid + pad * 0.4, B - qh - qhf * 0.7 - (bl.length - 1 - bi) * qhf * 1.16 - qhf * 0.6, esc(bl[bi]), qhf, CTA_ON, 'display', 400, -0.01);
      out += pill(mid + pad * 0.4, B - qh, bw, qh, String(o.ctaB || cta), qf);
      return out;
    }

    /* meta — the feed unit. Attribution row on top, picture in the middle, one
       full-width button welded to the bottom edge. */
    var av = Math.round(s * 0.105);
    out += '<rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + Math.round(av * 2.1) + '" fill="#0B0908" opacity="0.62"/>';
    out += '<rect x="' + L + '" y="' + Math.round(T * 0.55 + y * 0.45 + av * 0.2) + '" width="' + av + '" height="' + av + '" rx="' + Math.round(av * 0.28) + '" fill="' + CTA_INK + '"/>';
    var mh = Math.max(10, Math.round(s * 0.115));
    var mch = Math.max(12, Math.round(s * 0.125)), mcf = Math.max(7, Math.round(mch * 0.4));
    if (thumb) {
      out += '<rect x="' + Math.round(L + av * 1.35) + '" y="' + Math.round(y + av * 0.55) + '" width="' + Math.round(w * 0.34) + '" height="' + Math.max(2, Math.round(av * 0.2)) + '" rx="2" fill="#FFE9C0" opacity="0.7"/>';
      out += '<rect x="' + Math.round(L + av * 1.35) + '" y="' + Math.round(y + av * 1.0) + '" width="' + Math.round(w * 0.2) + '" height="' + Math.max(2, Math.round(av * 0.18)) + '" rx="2" fill="#FFE9C0" opacity="0.4"/>';
      return out + '<rect x="' + x + '" y="' + (y + h - mch) + '" width="' + w + '" height="' + mch + '" fill="' + CTA_INK + '"/>';
    }
    out += txt(L + av * 1.35, y + av * 0.9 + Math.round(s * 0.012), esc(o.eyebrow || PO.CAMPAIGN.brand), Math.max(7, Math.round(s * 0.042)), CTA_ON, 'sans', 600, 0.02);
    out += txt(L + av * 1.35, y + av * 1.62 + Math.round(s * 0.012), 'Sponsored', Math.max(6, Math.round(s * 0.034)), '#E4D9C6', 'sans', 400, 0.06);
    out += '<rect x="' + x + '" y="' + Math.round(y + h * 0.5) + '" width="' + w + '" height="' + Math.round(h * 0.5) + '" fill="url(#g-scrim)"/>';
    var mb = fitBlock(String(o.headline || PO.CAMPAIGN.tagline), w - pad * 2, mh, 3);
    var ml = mb.lines; mh = mb.fs;
    for (var mi = 0; mi < ml.length; mi++) {
      out += txt(L, y + h - mch - Math.round(s * 0.075) - (ml.length - 1 - mi) * mh * 1.14, esc(ml[mi]), mh, CTA_ON, 'display', 400, -0.01);
    }
    out += '<rect x="' + x + '" y="' + (y + h - mch) + '" width="' + w + '" height="' + mch + '" fill="' + CTA_INK + '"/>';
    out += txtC(x + w / 2, y + h - mch / 2 + mcf * 0.36, esc(cta), mcf, CTA_ON, 'sans', 600, 0.06);
    return out;
  }

  /* Type set INTO the picture. Sized against the crop, not the screen, so a
     vertical teaser and a wide master carry the same optical weight. */
  function lockup(kind, c, o) {
    var x = c[0], y = c[1], w = c[2], h = c[3];
    var pad = Math.round(w * 0.062);
    var L = x + pad, R = x + w - pad, B = y + h - pad, T = y + pad;
    var s = Math.min(w, h);
    var out = '';

    if (kind === 'title') {
      var ttl = String(o.title || PO.CAMPAIGN.brand);
      var fs = shrinkTo(ttl, R - L, Math.round(s * 0.115));
      out += '<rect x="' + x + '" y="' + Math.round(y + h * 0.34) + '" width="' + w + '" height="' + Math.round(h * 0.66) + '" fill="url(#g-scrim)"/>';
      out += txt(L, B - fs * 1.5, esc(o.eyebrow || PO.CAMPAIGN.season), Math.round(s * 0.036), '#FFE9C0', 'sans', 600, 0.14);
      out += txt(L, B - fs * 0.16, esc(ttl), fs, '#FFFDF8', 'display', 400, -0.01);
      out += '<rect x="' + L + '" y="' + (B + fs * 0.28) + '" width="' + Math.round(s * 0.16) + '" height="' + Math.max(3, Math.round(s * 0.011)) + '" fill="#F0663A"/>';
    } else if (kind === 'episode') {
      var ns = Math.round(s * 0.26);
      out += '<rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + h + '" fill="url(#g-scrim-full)"/>';
      out += txt(L, y + h * 0.5 + ns * 0.34, esc(o.n || '1'), ns, '#F0663A', 'display', 400, -0.02);
      out += txt(L + ns * 0.78, y + h * 0.5 - ns * 0.04, esc(o.title || 'The Sear'), shrinkTo(String(o.title || 'The Sear'), R - L - ns * 0.78, Math.round(s * 0.088)), '#FFFDF8', 'display', 400, -0.01);
      out += txt(L + ns * 0.78, y + h * 0.5 + ns * 0.26, esc(o.eyebrow || 'Cast iron, hot and dry'), Math.round(s * 0.036), '#E4D9C6', 'sans', 400, 0.02);
    } else if (kind === 'caption') {
      var cblk = fitBlock(String(o.caption || 'you want the pan hotter than you think'),
                          w - Math.round(w * 0.16), Math.round(s * 0.052), 3, 'sans', 600, 0.01);
      var lines = cblk.lines, cs = cblk.fs;
      var bh = cs * 1.62;
      for (var i = 0; i < lines.length; i++) {
        var ly = B - (lines.length - 1 - i) * bh;
        var lw = Math.round(textW(lines[i], cs, 'sans', 600, 0.01)) + cs;
        out += '<rect x="' + Math.round(x + w / 2 - lw / 2) + '" y="' + Math.round(ly - cs * 1.12) + '" width="' + lw + '" height="' + Math.round(bh * 0.92) + '" rx="' + Math.round(cs * 0.16) + '" fill="#0B0908" opacity="0.82"/>';
        out += txtC(x + w / 2, ly, esc(lines[i]), cs, '#FFFDF8', 'sans', 600, 0.01);
      }
    } else if (kind === 'quote') {
      /* A sentence, given the room a sentence needs. Left-aligned against a
         short ember rule, attribution underneath — the one lockup in the
         system where the type IS the picture rather than sitting on it. */
      var qblk = fitBlock(String(o.caption || PO.CAMPAIGN.idea), R - L, Math.round(s * 0.088), 4);
      var ql = qblk.lines, qs = qblk.fs;
      var qtop = y + h / 2 - (ql.length - 1) * qs * 0.6;
      out += '<rect x="' + L + '" y="' + Math.round(qtop - qs * 2.1) + '" width="' + Math.round(s * 0.13) + '" height="' + Math.max(3, Math.round(s * 0.012)) + '" fill="#F0663A"/>';
      for (var qi = 0; qi < ql.length; qi++) {
        out += txt(L, qtop + qi * qs * 1.24, esc(ql[qi]), qs, '#FFFDF8', 'display', 400, -0.01);
      }
      out += txt(L, qtop + (ql.length - 1) * qs * 1.24 + qs * 1.5, esc(o.eyebrow || PO.CAMPAIGN.brand), Math.round(s * 0.038), '#E4D9C6', 'sans', 600, 0.14);
    } else if (kind === 'end') {
      out += '<rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + h + '" fill="#0A0806" opacity="0.58"/>';
      out += txtC(x + w / 2, y + h * 0.48, esc(PO.CAMPAIGN.tagline), Math.round(s * 0.12), '#FFFDF8', 'display', 400, -0.01);
      out += '<rect x="' + Math.round(x + w / 2 - s * 0.09) + '" y="' + Math.round(y + h * 0.56) + '" width="' + Math.round(s * 0.18) + '" height="' + Math.max(3, Math.round(s * 0.009)) + '" fill="#F0663A"/>';
      out += txtC(x + w / 2, y + h * 0.66, esc(o.eyebrow || ('New season — ' + PO.CAMPAIGN.launch)), Math.round(s * 0.038), '#E4D9C6', 'sans', 500, 0.12);
    }
    return out;
  }

  function fam(k) { return k === 'display' ? 'var(--font-display)' : 'var(--font-sans)'; }
  function txt(x, y, s, size, fill, k, weight, ls) {
    return '<text x="' + Math.round(x) + '" y="' + Math.round(y) + '" font-family="' + fam(k) + '" font-size="' + size +
      '" font-weight="' + weight + '" letter-spacing="' + (ls * size).toFixed(1) + '" fill="' + fill + '">' + s + '</text>';
  }
  function txtC(x, y, s, size, fill, k, weight, ls) {
    return '<text x="' + Math.round(x) + '" y="' + Math.round(y) + '" text-anchor="middle" font-family="' + fam(k) + '" font-size="' + size +
      '" font-weight="' + weight + '" letter-spacing="' + (ls * size).toFixed(1) + '" fill="' + fill + '">' + s + '</text>';
  }
  function wrap(s, per, max) {
    var words = String(s).split(' '), lines = [], cur = '';
    for (var i = 0; i < words.length; i++) {
      if ((cur + ' ' + words[i]).trim().length > per) { lines.push(cur.trim()); cur = words[i]; }
      else cur += ' ' + words[i];
    }
    if (cur.trim()) lines.push(cur.trim());
    return lines.slice(0, max || 2);
  }

  /* ======================================================================
     DOCUMENT ARTEFACTS

     A script is not a video, and it must not look like one. Everything that
     is fundamentally TEXT is drawn on an ivory page with a border; everything
     that is fundamentally an IMAGE is drawn on the ink plane. That one rule
     means a creator can tell a script from a cut at 40px without reading a
     word, which is the whole job of a thumbnail.
     ====================================================================== */

  var PAGE_INK = '#26221E', PAGE_MUTED = '#8A8078', PAGE_RULE = '#DED3C0', PAGE_ACCENT = '#C84016';

  function pageOpen(w, h) {
    return '<svg class="art" viewBox="0 0 ' + w + ' ' + h + '" preserveAspectRatio="xMidYMid slice" ' +
      'aria-hidden="true" focusable="false"><rect width="' + w + '" height="' + h + '" fill="url(#g-page)"/>';
  }
  function bars(x, y, widths, gap, hgt, fill, op) {
    var out = '<g fill="' + fill + '" opacity="' + op + '">', cy = y;
    for (var i = 0; i < widths.length; i++) {
      out += '<rect x="' + x + '" y="' + cy + '" width="' + widths[i] + '" height="' + hgt + '" rx="' + (hgt / 2) + '"/>';
      cy += gap;
    }
    return out + '</g>';
  }

  /* A script page. Real slug lines and a real first phrase, then the body
     falling away into texture — which is exactly how a page reads from across
     a room, and the only honest way to draw type at thumbnail scale. */
  function docScript(o) {
    o = o || {};
    var W = 760, H = 980;
    var s = pageOpen(W, H);
    s += '<rect x="0" y="0" width="' + W + '" height="' + H + '" fill="none" stroke="' + PAGE_RULE + '" stroke-width="3"/>';
    s += '<line x1="132" y1="56" x2="132" y2="' + (H - 92) + '" stroke="' + PAGE_RULE + '" stroke-width="2"/>';
    s += txt(56, 92, 'SC 01', 26, PAGE_MUTED, 'sans', 600, 0.1);
    s += txt(56, 300, '0:00', 24, PAGE_MUTED, 'sans', 400, 0.04);
    s += txt(56, 546, '0:34', 24, PAGE_MUTED, 'sans', 400, 0.04);
    s += txt(56, 790, '1:12', 24, PAGE_MUTED, 'sans', 400, 0.04);
    s += txt(170, 96, esc(o.title || 'COLD OPEN — THE PAN'), 30, PAGE_INK, 'sans', 600, 0.08);
    s += txt(170, 168, esc(o.line || 'Everyone tells you to be gentle.'), 40, PAGE_INK, 'display', 400, -0.01);
    s += txt(170, 224, 'Nobody tells you the pan is the one', 30, PAGE_INK, 'sans', 400, 0);
    s += bars(170, 250, [520, 468, 540, 392], 34, 12, PAGE_INK, 0.2);
    s += txt(170, 466, 'AVERY (V.O.)', 24, PAGE_MUTED, 'sans', 600, 0.1);
    s += bars(212, 496, [420, 372, 448], 34, 12, PAGE_INK, 0.22);
    s += txt(170, 660, 'CUT TO — THE FLIP', 26, PAGE_INK, 'sans', 600, 0.06);
    s += bars(170, 692, [508, 452, 524, 380, 468], 34, 12, PAGE_INK, 0.18);
    if (o.flag) {
      s += '<rect x="152" y="' + (o.flagY || 470) + '" width="6" height="120" fill="' + PAGE_ACCENT + '"/>';
    }
    s += '<line x1="56" y1="' + (H - 68) + '" x2="' + (W - 56) + '" y2="' + (H - 68) + '" stroke="' + PAGE_RULE + '" stroke-width="2"/>';
    s += txt(56, H - 30, esc(o.foot || 'KITCHEN CONFIDENCE — S2 TRAILER'), 22, PAGE_MUTED, 'sans', 500, 0.08);
    s += txtC(W - 76, H - 30, esc(o.page || '3'), 22, PAGE_MUTED, 'sans', 500, 0);
    return s + '</svg>';
  }

  /* An outline: the plan the planning agent actually returns. */
  function docOutline(o) {
    o = o || {};
    var W = 760, H = 980, s = pageOpen(W, H);
    s += '<rect x="0" y="0" width="' + W + '" height="' + H + '" fill="none" stroke="' + PAGE_RULE + '" stroke-width="3"/>';
    s += txt(56, 96, esc(o.eyebrow || 'PRODUCTION OUTLINE'), 24, PAGE_MUTED, 'sans', 600, 0.12);
    s += txt(56, 168, esc(o.title || 'Six techniques, six episodes'), 42, PAGE_INK, 'display', 400, -0.01);
    s += '<rect x="56" y="196" width="96" height="6" fill="' + PAGE_ACCENT + '"/>';
    var y = 268;
    var eps = (PO.CAMPAIGN.episodes || []).slice(0, 6);
    for (var i = 0; i < eps.length; i++) {
      s += txt(56, y + 6, String(i + 1), 30, PAGE_ACCENT, 'display', 400, 0);
      s += txt(104, y, esc(eps[i].title), 30, PAGE_INK, 'sans', 600, 0);
      s += txt(104, y + 38, esc(eps[i].technique), 26, PAGE_MUTED, 'sans', 400, 0);
      s += '<line x1="56" y1="' + (y + 68) + '" x2="' + (W - 56) + '" y2="' + (y + 68) + '" stroke="' + PAGE_RULE + '" stroke-width="2"/>';
      y += 108;
    }
    return s + '</svg>';
  }

  /* A newsletter: masthead, one crop of the master, then body. The crop is
     what proves the email came out of the same shoot. */
  function docEmail(o) {
    o = o || {};
    var W = 760, H = 980, s = pageOpen(W, H);
    s += '<rect x="0" y="0" width="' + W + '" height="' + H + '" fill="none" stroke="' + PAGE_RULE + '" stroke-width="3"/>';
    s += txtC(W / 2, 92, esc(PO.CAMPAIGN.brand.toUpperCase()), 26, PAGE_MUTED, 'sans', 600, 0.24);
    s += '<line x1="56" y1="126" x2="' + (W - 56) + '" y2="126" stroke="' + PAGE_RULE + '" stroke-width="2"/>';
    s += '<svg x="56" y="160" width="648" height="364" viewBox="' + crop('sear', '16x9').join(' ') +
         '" preserveAspectRatio="xMidYMid slice"><use href="#sc-sear"/></svg>';
    s += txt(56, 606, esc(o.title || 'Season two starts 14 September'), 40, PAGE_INK, 'display', 400, -0.01);
    s += bars(56, 646, [608, 566, 624, 498], 36, 13, PAGE_INK, 0.2);
    s += '<rect x="56" y="822" width="268" height="72" rx="6" fill="' + PAGE_ACCENT + '"/>';
    s += txtC(190, 868, 'Watch the trailer', 26, '#FFFDF8', 'sans', 600, 0.02);
    s += bars(56, 926, [520], 30, 11, PAGE_INK, 0.14);
    return s + '</svg>';
  }

  /* A carousel: the deck seen as a deck. Three cards, the front one legible. */
  function docCarousel(o) {
    o = o || {};
    var W = 900, H = 900, s = '<svg class="art" viewBox="0 0 ' + W + ' ' + H +
      '" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">';
    s += '<rect width="' + W + '" height="' + H + '" fill="#F1EADC"/>';
    s += '<rect x="196" y="120" width="510" height="660" rx="10" fill="#D9CDB8"/>';
    s += '<rect x="172" y="98" width="510" height="660" rx="10" fill="#E7DDCA"/>';
    s += '<g><rect x="148" y="76" width="510" height="660" rx="10" fill="#0F0D0C"/>';
    s += '<svg x="148" y="76" width="510" height="410" viewBox="' + crop('over', '4x5').join(' ') +
         '" preserveAspectRatio="xMidYMid slice"><use href="#sc-over"/></svg>';
    s += txt(184, 566, esc(o.n || '04'), 66, PAGE_ACCENT, 'display', 400, -0.02);
    s += txt(184, 636, esc(o.title || 'The Bone'), 44, '#FFFDF8', 'display', 400, -0.01);
    s += txt(184, 676, 'Stock without the fuss.', 26, '#E4D9C6', 'sans', 400, 0);
    s += txt(184, 710, 'Four hours, one pot, no straining.', 26, '#E4D9C6', 'sans', 400, 0);
    s += '</g>';
    s += '<g fill="' + PAGE_ACCENT + '"><circle cx="380" cy="830" r="9"/></g>';
    s += '<g fill="#B6A992"><circle cx="416" cy="830" r="9"/><circle cx="452" cy="830" r="9"/><circle cx="488" cy="830" r="9"/><circle cx="524" cy="830" r="9"/><circle cx="560" cy="830" r="9"/></g>';
    return s + '</svg>';
  }

  /* A contact sheet: the whole set as one object, with the marks a cutting
     room actually makes on one — a ring around the selected frame, a slash
     through the killed one. Index labels, no sprockets, no fake film. */
  function docSheet(o) {
    o = o || {};
    var W = 1200, H = 780, cols = 5, rows = 2;
    var gx = 24, cw = Math.floor((W - gx * (cols + 1)) / cols), ch = Math.round(cw * 9 / 16);
    var s = '<svg class="art" viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">';
    s += '<rect width="' + W + '" height="' + H + '" fill="#0F0D0C"/>';
    /* Ten cells, ten set-ups. A selects sheet that shows the same five frames
       twice is not a sheet of selects, it is a sheet of duplicates — and this
       is the one artefact in the prototype whose entire job is to show how
       much coverage the shoot got. */
    var sc = ['sear', 'flip', 'over', 'spice', 'loaf', 'hands', 'knife', 'plate', 'flame', 'quote'];
    var top = 92, i = 0;
    for (var r = 0; r < rows; r++) {
      for (var c = 0; c < cols; c++) {
        var x = gx + c * (cw + gx), y = top + r * (ch + 78);
        var scene = sc[i % sc.length];
        s += '<svg x="' + x + '" y="' + y + '" width="' + cw + '" height="' + ch + '" viewBox="' +
             crop(scene, '16x9', i).join(' ') + '" preserveAspectRatio="xMidYMid slice"><use href="#sc-' + scene + '"/></svg>';
        var label = String.fromCharCode(65 + r) + (c + 1);
        s += txt(x, y + ch + 30, label, 22, '#FFFDF8', 'sans', 500, 0.1);
        if (i === (o.pick == null ? 2 : o.pick)) {
          s += '<rect x="' + (x - 4) + '" y="' + (y - 4) + '" width="' + (cw + 8) + '" height="' + (ch + 8) + '" fill="none" stroke="' + PAGE_ACCENT + '" stroke-width="5"/>';
        }
        if (i === (o.kill == null ? 6 : o.kill)) {
          s += '<path d="M' + x + ' ' + (y + ch) + ' L' + (x + cw) + ' ' + y + '" stroke="' + PAGE_ACCENT + '" stroke-width="5" opacity="0.75"/>';
        }
        i++;
      }
    }
    s += txt(gx, 52, esc(o.title || 'KITCHEN CONFIDENCE — S2 SELECTS'), 26, '#FFFDF8', 'sans', 600, 0.14);
    s += txt(W - gx - 150, 52, esc(o.roll || 'ROLL 04'), 26, '#FFFDF8', 'sans', 500, 0.14);
    return s + '</svg>';
  }

  var DOCS = { script: docScript, outline: docOutline, email: docEmail, carousel: docCarousel, sheet: docSheet };

  /** The one entry point every screen uses. Give it an asset, get its picture. */
  function of(a, opts) {
    opts = opts || {};
    if (!a) return still('sear', opts.aspect || '16x9', opts);
    if (a.doc) return DOCS[a.doc]({ n: a.slideN, title: a.docTitle || a.name, line: a.docLine, flag: a.docFlag, page: a.page, foot: a.docFoot, eyebrow: a.docEyebrow, pick: a.pick, kill: a.kill, roll: a.roll });
    var seat = opts.seat || a.seat || 0;
    /* A set entry describes THIS copy of a multi-copy deliverable. It wins over
       the descriptor, because the descriptor only knows what the deliverable is
       in general and the entry knows which one this is. */
    var e = (a.set && setEntry(a.set, seat)) || {};
    var pick = function (k, alt) { return e[k] !== undefined ? e[k] : alt; };
    return still(e.scene || a.scene || 'sear', opts.aspect || e.aspect || a.aspect || '16x9', {
      seat: seat,
      lockup: opts.lockup === null ? null
        : (opts.lockup || (a.set ? pick('lockup', a.lockup || null) : (a.lockup || null))),
      title: e.title || a.lockupTitle || a.name,
      eyebrow: e.eyebrow || a.lockupEyebrow,
      caption: e.caption || a.caption,
      n: e.n || a.slideN,
      headline: e.headline || a.headline, cta: e.cta || a.cta,
      headlineB: e.headlineB || a.headlineB, ctaB: e.ctaB || a.ctaB,
      ad: e.ad || a.ad, unit: e.unit || a.unit,
      detail: opts.detail
    });
  }

  PO.art = {
    inject: injectScenes,
    still: still,
    of: of,
    doc: function (kind, o) { return (DOCS[kind] || docScript)(o || {}); },
    scenes: SCENE_META,
    sets: SETS,
    setEntry: setEntry,
    crop: crop,
    esc: esc,
    txt: txt,
    txtC: txtC,
    wrap: wrap
  };

  if (document.body) injectScenes();
  else document.addEventListener('DOMContentLoaded', injectScenes);
})();
